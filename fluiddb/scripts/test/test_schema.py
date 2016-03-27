from textwrap import dedent

from storm.exceptions import OperationalError
from storm.schema.schema import Schema
from storm.zope.interfaces import IZStorm
from storm.zope.zstorm import ZStorm
from zope.component import getUtility, provideUtility

from fluiddb.data.permission import Policy, Operation
from fluiddb.data.system import createSystemData
from fluiddb.data.user import Role
from fluiddb.model.user import getUser
from fluiddb.model.tag import TagAPI
from fluiddb.model.permission import PermissionAPI
from fluiddb.scripts.schema import (
    patchDatabase, getPatchStatus, bootstrapWebAdminData)
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    PythonPackageBuilderResource, TemporaryDirectoryResource, DatabaseResource,
    ConfigResource)


def createSchema(patches):
    """Create a L{Schema} instance for use in schema management tests."""
    return Schema(['CREATE TABLE person (name TEXT NOT NULL)'],
                  ['DROP TABLE person'],
                  ['DELETE FROM person'],
                  patches)


class TemporaryDatabaseMixin(object):

    def setUp(self):
        super(TemporaryDatabaseMixin, self).setUp()
        self.uri = 'sqlite:///%s' % self.fs.makePath()
        self.zstorm = ZStorm()
        self.zstorm.set_default_uri('main', self.uri)
        provideUtility(self.zstorm)
        self.store = self.zstorm.get('main')

    def tearDown(self):
        self.zstorm = getUtility(IZStorm)
        self.zstorm.remove(self.zstorm.get('main'))
        super(TemporaryDatabaseMixin, self).tearDown()


class PatchDatabaseTest(TemporaryDatabaseMixin, FluidinfoTestCase):

    resources = [('fs', TemporaryDirectoryResource()),
                 ('python', PythonPackageBuilderResource())]

    def setUp(self):
        super(PatchDatabaseTest, self).setUp()
        self.packageBuilder = self.python.createPackage('sample_schema')

        import sample_schema

        self.patchPackage = sample_schema

    def testPatchDatabaseWithoutSchema(self):
        """L{patchDatabase} creates a schema if one isn't already in place."""
        schema = createSchema(self.patchPackage)
        self.assertRaises(OperationalError, self.store.execute,
                          'SELECT * FROM patch')
        patchDatabase(self.store, schema)
        self.assertEqual([], list(self.store.execute('SELECT * FROM patch')))

    def testPatchDatabaseWithoutPatches(self):
        """
        L{patchDatabase} is basically a no-op if no patches are available.
        """
        schema = createSchema(self.patchPackage)
        patchDatabase(self.store, schema)
        self.assertEqual([], list(self.store.execute('SELECT * FROM patch')))
        patchDatabase(self.store, schema)
        self.assertEqual([], list(self.store.execute('SELECT * FROM patch')))

    def testPatchDatabase(self):
        """
        L{patchDatabase} applies all outstanding patches.  The C{patch} table
        contains a row for every patch version that has been applied to the
        database.
        """
        schema = createSchema(self.patchPackage)
        patchDatabase(self.store, schema)
        self.packageBuilder.createModule('patch_1', dedent("""\
            def apply(store):
                store.execute('INSERT INTO person (name) VALUES (\\'Bob\\')')
            """))
        patchDatabase(self.store, schema)
        self.assertEqual([(1,)],
                         list(self.store.execute('SELECT * FROM patch')))
        self.assertEqual([('Bob',)],
                         list(self.store.execute('SELECT * FROM person')))

    def testPatchDatabaseWithoutUnappliedPatches(self):
        """L{patchDatabase} only applies unapplied patches."""
        schema = createSchema(self.patchPackage)
        patchDatabase(self.store, schema)
        self.packageBuilder.createModule('patch_1', dedent("""\
            def apply(store):
                store.execute('INSERT INTO person (name) VALUES (\\'Bob\\')')
            """))
        self.store.execute('INSERT INTO patch (version) VALUES (1)')
        patchDatabase(self.store, schema)
        self.assertEqual([(1,)],
                         list(self.store.execute('SELECT * FROM patch')))
        self.assertEqual([], list(self.store.execute('SELECT * FROM person')))


class GetPatchStatusTest(TemporaryDatabaseMixin, FluidinfoTestCase):

    resources = [('fs', TemporaryDirectoryResource()),
                 ('python', PythonPackageBuilderResource())]

    def setUp(self):
        super(GetPatchStatusTest, self).setUp()
        self.packageBuilder = self.python.createPackage('sample_schema')

        import sample_schema

        self.patchPackage = sample_schema

    def testGetPatchStatusWithoutSchema(self):
        """
        L{getPatchStatus} raises an C{OperationalError} exception if the
        database being checked doesn't have a schema in place.
        """
        schema = createSchema(self.patchPackage)
        self.assertRaises(OperationalError, getPatchStatus, self.store, schema)

    def testGetPatchStatus(self):
        """
        L{getPatchStatus} returns a L{PatchStatus} with information about
        outstanding and unknown patches.  If the database is up-to-date and no
        unknown patches have been applied to it, both of these values are
        empty C{list}s.
        """
        schema = createSchema(self.patchPackage)
        patchDatabase(self.store, schema)
        status = getPatchStatus(self.store, schema)
        self.assertEqual([], status.unappliedPatches)
        self.assertEqual([], status.unknownPatches)

    def testGetPatchStatusWithUnappliedPatches(self):
        """
        L{getPatchStatus} returns information about patch versions that need
        to be applied to a database to make it up-to-date with the code base.
        """
        schema = createSchema(self.patchPackage)
        patchDatabase(self.store, schema)
        self.packageBuilder.createModule('patch_1', dedent("""\
            def apply(store):
                store.execute('INSERT INTO person (name) VALUES (\\'Bob\\')')
            """))
        status = getPatchStatus(self.store, schema)
        self.assertEqual([1], status.unappliedPatches)
        self.assertEqual([], status.unknownPatches)

    def testGetPatchStatusWithUnknownPatches(self):
        """
        L{getPatchStatus} returns information about patch versions that exist
        in the database, but not in the code base.
        """
        schema = createSchema(self.patchPackage)
        patchDatabase(self.store, schema)
        self.store.execute('INSERT INTO patch (version) VALUES (1)')
        status = getPatchStatus(self.store, schema)
        self.assertEqual([], status.unappliedPatches)
        self.assertEqual([1], status.unknownPatches)


class BootstrapWebAdminDataTest(FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def testCreateFluidinfoUser(self):
        """L{bootstrapWebAdminData} creates a C{fluidinfo.com} user."""
        createSystemData()
        bootstrapWebAdminData()
        webuser = getUser(u'fluidinfo.com')
        self.assertNotIdentical(None, webuser)
        self.assertEqual(u'Fluidinfo website', webuser.fullname)
        self.assertEqual(Role.USER_MANAGER, webuser.role)

    def testCreateActivationTokenTag(self):
        """
        L{bootstrapWebAdminData} creates a C{fluiddb/users/activation-token}
        tag.
        """
        createSystemData()
        bootstrapWebAdminData()
        superuser = getUser(u'fluiddb')
        result = TagAPI(superuser).get([u'fluiddb/users/activation-token'])
        self.assertIn(u'fluiddb/users/activation-token', result)

    def testActivationTokenTagPermission(self):
        """
        L{bootstrapWebAdminData} creates a C{fluiddb/users/activation-token}
        tag with write permissions for the C{fluidinfo.com} user.
        """
        createSystemData()
        bootstrapWebAdminData()
        superuser = getUser(u'fluiddb')
        pathAndOperation = (u'fluiddb/users/activation-token',
                            Operation.WRITE_TAG_VALUE)
        result = PermissionAPI(superuser).get([pathAndOperation])
        policy, exceptions = result[pathAndOperation]
        self.assertEqual(Policy.CLOSED, policy)
        self.assertEqual([u'fluidinfo.com'], exceptions)
