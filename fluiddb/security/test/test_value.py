from uuid import uuid4

from fluiddb.cache.permission import CachingPermissionAPI
from fluiddb.cache.test.test_value import CachingTagValueAPITestMixin
from fluiddb.data.permission import Operation, Policy
from fluiddb.data.system import createSystemData
from fluiddb.model.exceptions import UnknownPathError
from fluiddb.model.tag import TagAPI
from fluiddb.model.test.test_value import TagValueAPITestMixin
from fluiddb.model.user import UserAPI, getUser
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.security.value import SecureTagValueAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    BrokenCacheResource, CacheResource, ConfigResource, DatabaseResource,
    LoggingResource)


class SecureTagValueAPITestMixin(object):

    def testSetWithUnknownPath(self):
        """
        L{SecureTagValueAPI.set} raises an L{UnknownPathError} if a path for
        an unknown L{Tag} is specified and the L{User} making the request
        doesn't have permission to create the missing path.
        """
        values = {uuid4(): {u'unknown/path': 256}}
        error = self.assertRaises(UnknownPathError, self.tagValues.set,
                                  values)
        self.assertEqual([u'unknown/path'], error.paths)

    def testGetWithUnknownPath(self):
        """
        L{SecureTagValueAPI.get} raises an L{UnknownPathError} if a path for
        an unknown L{Tag} is specified.
        """
        error = self.assertRaises(UnknownPathError,
                                  self.tagValues.get, objectIDs=[uuid4()],
                                  paths=[u'username/unknowntag'])
        self.assertEqual([u'username/unknowntag'], error.paths)

    def testGetWithoutPathsOnlyReturnsAccessibleValues(self):
        """
        When L{SecureTagValueAPI.get} is called without an explicit list of
        L{Tag.path}s it only returns values that the user has
        L{Operation.READ_TAG_VALUE} permissions for.
        """
        objectID = uuid4()
        TagAPI(self.user).create([(u'username/open', u'An accessible tag'),
                                  (u'username/closed', u'A denied tag')])
        self.tagValues.set({objectID: {u'username/open': 13,
                                       u'username/closed': 17}})
        self.permissions.set([(u'username/closed', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, [])])
        result = self.tagValues.get([objectID])
        self.assertEqual(1, len(result))
        self.assertIn(objectID, result)
        self.assertEqual(1, len(result[objectID]))
        self.assertIn(u'username/open', result[objectID])

    def testDeleteWithUnknownPath(self):
        """
        L{SecureTagValueAPI.delete} raises an L{UnknownPathError} if a path for
        an unknown L{Tag} is specified.
        """
        values = [(uuid4(), u'username/unknowntag')]
        error = self.assertRaises(UnknownPathError,
                                  self.tagValues.delete, values)
        self.assertEqual([u'username/unknowntag'], error.paths)


class SecureTagValueAPITest(TagValueAPITestMixin, CachingTagValueAPITestMixin,
                            SecureTagValueAPITestMixin, FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureTagValueAPITest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = CachingPermissionAPI(self.user)
        self.tagValues = SecureTagValueAPI(self.user)


class SecureTagValueAPIWithBrokenCacheTest(TagValueAPITestMixin,
                                           SecureTagValueAPITestMixin,
                                           FluidinfoTestCase):

    resources = [('cache', BrokenCacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureTagValueAPIWithBrokenCacheTest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = CachingPermissionAPI(self.user)
        self.tagValues = SecureTagValueAPI(self.user)


class SecureTagValueAPIWithAnonymousRoleTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureTagValueAPIWithAnonymousRoleTest, self).setUp()
        system = createSystemData()
        self.anon = system.users[u'anon']
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = CachingPermissionAPI(self.user)
        TagAPI(self.user).create([(u'username/tag', u'description')])
        self.tagValues = SecureTagValueAPI(self.anon)

    def testGetIsAllowed(self):
        """
        L{SecureTagAPI.get} is allowed if the anonymous user has
        C{Operation.READ_TAG_VALUE} permissions.
        """
        objectID = uuid4()
        values = {objectID: {u'username/tag': 16}}
        SecureTagValueAPI(self.user).set(values)
        self.permissions.set([(u'username/tag', Operation.READ_TAG_VALUE,
                               Policy.OPEN, [])])
        result = self.tagValues.get(objectIDs=[objectID],
                                    paths=[u'username/tag'])
        self.assertEqual(16, result[objectID][u'username/tag'].value)

    def testGetIsDenied(self):
        """
        L{SecureTagAPI.get} raises L{PermissionDeniedError} if the anonymous
        user doesn't have C{Operation.READ_TAG_VALUE} permissions.
        """
        objectID = uuid4()
        values = {objectID: {u'username/tag': 16}}
        SecureTagValueAPI(self.user).set(values)
        self.permissions.set([(u'username/tag', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, [])])
        error = self.assertRaises(PermissionDeniedError,
                                  self.tagValues.get, objectIDs=[objectID],
                                  paths=[u'username/tag'])
        self.assertEqual([(u'username/tag', Operation.READ_TAG_VALUE)],
                         error.pathsAndOperations)

    def testSetIsAlwaysDenied(self):
        """L{SecureTagAPI.set} is always denied for the anonymous user."""
        values = {uuid4(): {u'username/tag': 16}}
        error = self.assertRaises(PermissionDeniedError,
                                  self.tagValues.set, values)
        self.assertEqual([(u'username/tag', Operation.WRITE_TAG_VALUE)],
                         error.pathsAndOperations)

    def testDeleteIsAlwaysDenied(self):
        """L{SecureTagAPI.delete} is always denied for the anonymous user."""
        error = self.assertRaises(PermissionDeniedError,
                                  self.tagValues.delete,
                                  [(uuid4(), u'username/tag')])
        self.assertEqual([(u'username/tag', Operation.DELETE_TAG_VALUE)],
                         error.pathsAndOperations)


class SecureTagValueAPIWithUserRoleTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureTagValueAPIWithUserRoleTest, self).setUp()
        createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = CachingPermissionAPI(self.user)
        TagAPI(self.user).create([(u'username/tag', u'description')])
        self.tagValues = SecureTagValueAPI(self.user)

    def testGetIsAllowed(self):
        """
        L{SecureTagAPI.get} is allowed if the user has
        C{Operation.READ_TAG_VALUE} permissions.
        """
        objectID = uuid4()
        values = {objectID: {u'username/tag': 16}}
        self.tagValues.set(values)
        self.permissions.set([(u'username/tag', Operation.READ_TAG_VALUE,
                               Policy.OPEN, [])])
        result = self.tagValues.get(objectIDs=[objectID],
                                    paths=[u'username/tag'])
        self.assertEqual(16, result[objectID][u'username/tag'].value)

    def testGetIsDenied(self):
        """
        L{SecureTagAPI.get} raises L{PermissionDeniedError} if the user doesn't
        have C{Operation.READ_TAG_VALUE} permissions.
        """
        objectID = uuid4()
        values = {objectID: {u'username/tag': 16}}
        self.tagValues.set(values)
        self.permissions.set([(u'username/tag', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, [])])
        error = self.assertRaises(PermissionDeniedError,
                                  self.tagValues.get, objectIDs=[objectID],
                                  paths=[u'username/tag'])
        self.assertEqual([(u'username/tag', Operation.READ_TAG_VALUE)],
                         error.pathsAndOperations)

    def testSetIsAllowed(self):
        """
        L{SecureTagAPI.set} is allowed if the user has
        C{Operation.WRITE_TAG_VALUE} permissions.
        """
        self.permissions.set([(u'username/tag', Operation.WRITE_TAG_VALUE,
                               Policy.OPEN, [])])
        objectID = uuid4()
        values = {objectID: {u'username/tag': 16}}
        self.tagValues.set(values)
        result = self.tagValues.get(objectIDs=[objectID],
                                    paths=[u'username/tag'])
        self.assertEqual(16, result[objectID][u'username/tag'].value)

    def testSetIsDenied(self):
        """
        L{SecureTagAPI.set} raises L{PermissionDeniedError} if the user doesn't
        have C{Operation.WRITE_TAG_VALUE} permissions.
        """
        self.permissions.set([(u'username/tag', Operation.WRITE_TAG_VALUE,
                               Policy.CLOSED, [])])
        values = {uuid4(): {u'username/tag': 16}}
        error = self.assertRaises(PermissionDeniedError,
                                  self.tagValues.set, values)
        self.assertEqual([(u'username/tag', Operation.WRITE_TAG_VALUE)],
                         error.pathsAndOperations)

    def testDeleteIsAllowed(self):
        """
        L{SecureTagAPI.delete} is allowed if the user has
        C{Operation.DELETE_TAG_VALUE} permissions.
        """
        self.permissions.set([(u'username/tag', Operation.DELETE_TAG_VALUE,
                               Policy.OPEN, [])])
        objectID = uuid4()
        values = {objectID: {u'username/tag': 16}}
        self.tagValues.set(values)
        self.tagValues.delete([(objectID, u'username/tag')])
        result = self.tagValues.get(objectIDs=[objectID],
                                    paths=[u'username/tag'])
        self.assertEqual({}, result)

    def testDeleteIsDenied(self):
        """
        L{SecureTagAPI.delete} raises L{PermissionDeniedError} if the user
        doesn't have C{Operation.DELETE_TAG_VALUE} permissions.
        """
        objectID = uuid4()
        values = {objectID: {u'username/tag': 16}}
        self.tagValues.set(values)
        self.permissions.set([(u'username/tag', Operation.DELETE_TAG_VALUE,
                               Policy.CLOSED, [])])
        error = self.assertRaises(PermissionDeniedError,
                                  self.tagValues.delete,
                                  [(objectID, u'username/tag')])
        self.assertEqual([(u'username/tag', Operation.DELETE_TAG_VALUE)],
                         error.pathsAndOperations)


class SecureTagValueAPIWithSuperuserRoleTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureTagValueAPIWithSuperuserRoleTest, self).setUp()
        system = createSystemData()
        self.superuser = system.users[u'fluiddb']
        TagAPI(self.superuser).create([(u'fluiddb/tag', u'description')])
        self.tagValues = SecureTagValueAPI(self.superuser)
        self.permissions = CachingPermissionAPI(self.superuser)

    def testGetIsAllowed(self):
        """L{SecureTagValueAPI.get} is always allowed for the superuser."""
        objectID = uuid4()
        values = {objectID: {u'fluiddb/tag': 16}}
        self.tagValues.set(values)
        self.permissions.set([(u'fluiddb/tag', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, [])])
        result = self.tagValues.get(objectIDs=[objectID],
                                    paths=[u'fluiddb/tag'])
        self.assertEqual(16, result[objectID][u'fluiddb/tag'].value)

    def testSetIsAllowed(self):
        """L{SecureTagValueAPI.set} is always allowed for the superuser."""
        self.permissions.set([(u'fluiddb/tag', Operation.WRITE_TAG_VALUE,
                               Policy.CLOSED, [])])
        objectID = uuid4()
        values = {objectID: {u'fluiddb/tag': 16}}
        self.tagValues.set(values)
        result = self.tagValues.get(objectIDs=[objectID],
                                    paths=[u'fluiddb/tag'])
        self.assertEqual(16, result[objectID][u'fluiddb/tag'].value)

    def testDeleteIsAllowed(self):
        """L{SecureTagValueAPI.delete} is always allowed for the superuser."""
        self.permissions.set([(u'fluiddb/tag', Operation.DELETE_TAG_VALUE,
                               Policy.CLOSED, [])])
        objectID = uuid4()
        values = {objectID: {u'fluiddb/tag': 16}}
        self.tagValues.set(values)
        self.tagValues.delete([(objectID, u'fluiddb/tag')])
        result = self.tagValues.get(objectIDs=[objectID],
                                    paths=[u'fluiddb/tag'])
        self.assertEqual({}, result)
