from uuid import uuid4

from psycopg2.extras import register_uuid
from storm.locals import Count

from fluiddb.data.namespace import createNamespace
from fluiddb.data.permission import (
    createNamespacePermission, getNamespacePermissions)
from fluiddb.data.user import User, createUser
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import DatabaseResource
from fluiddb.util.readonly import readonly


register_uuid()


class ReadonlyTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testReadonlyWithEmptyResult(self):
        """
        L{readonly} returns an empty C{list} if the C{ResultSet} is empty.
        """
        result = self.store.find(User)
        self.assertEqual([], list(readonly(result)))

    def testReadonly(self):
        """
        L{readonly} returns readonly objects using data from a C{ResultSet}.
        """
        user = createUser(u'username', u'secret', u'name', u'name@example.com')
        readonlyUser = readonly(self.store.find(User)).one()
        self.assertNotIdentical(user, readonlyUser)
        self.assertEqual(user.id, readonlyUser.id)
        self.assertEqual(user.objectID, readonlyUser.objectID)
        self.assertEqual(user.username, readonlyUser.username)
        self.assertEqual(user.passwordHash, readonlyUser.passwordHash)
        self.assertEqual(user.fullname, readonlyUser.fullname)
        self.assertEqual(user.email, readonlyUser.email)
        self.assertEqual(user.namespaceID, readonlyUser.namespaceID)
        self.assertEqual(user.creationTime, readonlyUser.creationTime)

    def testReadonlyWithTupleResult(self):
        """L{readonly} correctly handles tuple results."""
        user = createUser(u'username', u'secret', u'name', u'name@example.com')
        namespace = createNamespace(user, u'username')
        permission = createNamespacePermission(namespace)
        result = getNamespacePermissions([u'username'])
        readonlyNamespace, readonlyPermission = readonly(result).one()
        self.assertNotIdentical(namespace, readonlyNamespace)
        self.assertEqual(namespace.id, readonlyNamespace.id)
        self.assertEqual(namespace.objectID, readonlyNamespace.objectID)
        self.assertEqual(namespace.parentID, readonlyNamespace.parentID)
        self.assertEqual(namespace.creatorID, readonlyNamespace.creatorID)
        self.assertEqual(namespace.path, readonlyNamespace.path)
        self.assertEqual(namespace.name, readonlyNamespace.name)
        self.assertEqual(namespace.creationTime,
                         readonlyNamespace.creationTime)
        self.assertNotIdentical(permission, readonlyPermission)
        self.assertEqual(permission.createPolicy,
                         readonlyPermission.createPolicy)
        self.assertEqual(permission.createExceptions,
                         readonlyPermission.createExceptions)
        self.assertEqual(permission.updatePolicy,
                         readonlyPermission.updatePolicy)
        self.assertEqual(permission.updateExceptions,
                         readonlyPermission.updateExceptions)
        self.assertEqual(permission.deletePolicy,
                         readonlyPermission.deletePolicy)
        self.assertEqual(permission.deleteExceptions,
                         readonlyPermission.deleteExceptions)
        self.assertEqual(permission.listPolicy,
                         readonlyPermission.listPolicy)
        self.assertEqual(permission.listExceptions,
                         readonlyPermission.listExceptions)
        self.assertEqual(permission.controlPolicy,
                         readonlyPermission.controlPolicy)
        self.assertEqual(permission.controlExceptions,
                         readonlyPermission.controlExceptions)

    def testReadonlyWithNonObjectResult(self):
        """
        A readonly C{ResultSet} correctly handles non-object result values,
        such as a count in a C{GROUP BY} query.
        """
        user = createUser(u'username', u'secret', u'name', u'name@example.com')
        result = readonly(self.store.find((Count(), User.username)))
        result.group_by(User.username)
        count, readonlyUser = result.one()
        self.assertEqual(1, count)
        readonlyUser = readonly(self.store.find(User)).one()
        self.assertNotIdentical(user, readonlyUser)
        self.assertEqual(user.id, readonlyUser.id)
        self.assertEqual(user.objectID, readonlyUser.objectID)
        self.assertEqual(user.username, readonlyUser.username)
        self.assertEqual(user.passwordHash, readonlyUser.passwordHash)
        self.assertEqual(user.fullname, readonlyUser.fullname)
        self.assertEqual(user.email, readonlyUser.email)
        self.assertEqual(user.namespaceID, readonlyUser.namespaceID)
        self.assertEqual(user.creationTime, readonlyUser.creationTime)

    def testLiveObjectIsCached(self):
        """Live objects are cached and tracked by Storm."""
        createUser(u'username', u'secret', u'name', u'name@example.com')
        self.store.flush()
        self.assertNotEqual([], self.store._cache.get_cached())

    def testReadonlyObjectIsNotCached(self):
        """Readonly objects are not cached or tracked by Storm."""
        self.store.execute(
            """
            INSERT INTO users (object_id, role, username, password_hash,
                               fullname, email)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
            (uuid4(), 1, u'username', u'secret', u'name', u'name@example.com'))
        readonly(self.store.find(User)).one()
        self.store.flush()
        self.assertEqual([], self.store._cache.get_cached())

    def testSet(self):
        """
        C{ResultSet.set} raises a C{RuntimeError} if its been put in readonly
        mode.
        """
        result = readonly(self.store.find(User))
        self.assertRaises(RuntimeError, result.set, username=u'hello')
