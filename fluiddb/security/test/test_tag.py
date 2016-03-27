from fluiddb.cache.permission import CachingPermissionAPI
from fluiddb.cache.test.test_tag import CachingTagAPITestMixin
from fluiddb.data.permission import Operation, Policy
from fluiddb.data.system import createSystemData
from fluiddb.data.tag import createTag
from fluiddb.model.exceptions import UnknownPathError
from fluiddb.model.test.test_tag import TagAPITestMixin
from fluiddb.model.user import UserAPI, getUser
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.security.tag import SecureTagAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    BrokenCacheResource, CacheResource, ConfigResource, DatabaseResource,
    LoggingResource)


class SecureTagAPITestMixin(object):

    def testCreateWithUnknownParent(self):
        """
        L{SecureTagAPI.create} raises an L{UnknownPathError} exception if an
        attempt to create a L{Tag} with an unknown parent is made.
        """
        values = [(u'unknown/tag', u'An unknown tag.')]
        error = self.assertRaises(UnknownPathError,
                                  self.tags.create, values)
        self.assertEqual([u'unknown'], error.paths)

    def testSetWithUnknownPath(self):
        """
        L{SecureTagAPI.set} raises an L{UnknownPathError} if a path for an
        unknown L{Tag} is specified.
        """
        values = {u'unknown/tag': u'An unknown tag.'}
        error = self.assertRaises(UnknownPathError,
                                  self.tags.set, values)
        self.assertEqual([u'unknown/tag'], error.paths)

    def testDeleteWithUnknownPath(self):
        """
        L{SecureTagAPI.delete} raises an L{UnknownPathError} if a path for an
        unknown L{Tag} is specified.
        """
        error = self.assertRaises(UnknownPathError,
                                  self.tags.delete, [u'unknown/tag'])
        self.assertEqual([u'unknown/tag'], error.paths)


class SecureTagAPITest(TagAPITestMixin, CachingTagAPITestMixin,
                       SecureTagAPITestMixin, FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureTagAPITest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = CachingPermissionAPI(self.user)
        self.tags = SecureTagAPI(self.user)


class SecureTagAPIWithBrokenCacheTest(TagAPITestMixin, SecureTagAPITestMixin,
                                      FluidinfoTestCase):

    resources = [('cache', BrokenCacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureTagAPIWithBrokenCacheTest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = CachingPermissionAPI(self.user)
        self.tags = SecureTagAPI(self.user)


class SecureTagAPIWithAnonymousRoleTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureTagAPIWithAnonymousRoleTest, self).setUp()
        system = createSystemData()
        self.anon = system.users[u'anon']
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.tags = SecureTagAPI(self.anon)

    def testCreateIsDenied(self):
        """
        L{SecureTagAPI.create} raises a L{PermissionDeniedError} if its
        invoked by a L{User} with the L{Role.ANONYMOUS}.
        """
        error = self.assertRaises(PermissionDeniedError, self.tags.create,
                                  [(u'user/foo', 'A foo tag')])
        self.assertEqual(self.anon.username, error.username)
        self.assertEqual([('user', Operation.CREATE_NAMESPACE)],
                         error.pathsAndOperations)

    def testDeleteIsDenied(self):
        """
        L{SecureTagAPI.delete} raises a L{PermissionDeniedError} if its
        invoked by a L{User} with the L{Role.ANONYMOUS}.
        """
        createTag(self.user, self.user.namespace, u'path')
        error = self.assertRaises(PermissionDeniedError, self.tags.delete,
                                  [u'user/path'])
        self.assertEqual(self.anon.username, error.username)
        self.assertEqual([('user/path', Operation.DELETE_TAG)],
                         error.pathsAndOperations)

    def testSetIsDenied(self):
        """
        L{SecureTagAPI.set} raises a L{PermissionDeniedError} if its invoked
        by a L{User} with the L{Role.ANONYMOUS}.
        """
        createTag(self.user, self.user.namespace, u'path')
        error = self.assertRaises(PermissionDeniedError, self.tags.set,
                                  {u'user/path': 'A path tag'})
        self.assertEqual(self.anon.username, error.username)
        self.assertEqual([('user/path', Operation.UPDATE_TAG)],
                         error.pathsAndOperations)


class SecureTagAPIWithNormalUserTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureTagAPIWithNormalUserTest, self).setUp()
        createSystemData()
        UserAPI().create([(u'user', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'user')
        self.permissions = CachingPermissionAPI(self.user)
        self.tags = SecureTagAPI(self.user)

    def testCreateIsAllowed(self):
        """
        L{SecureTagAPI.create} should allow the creation of tags whose parent
        namespace has open C{Operation.CREATE_NAMESPACE} permissions.
        """
        result = self.tags.create([(u'user/test', u'description')])
        self.assertEqual(1, len(result))

    def testCreateIsDenied(self):
        """
        L{SecureTagAPI.create} should raise L{PermissonDeniedError} if
        the user doesn't have C{Operation.CREATE_NAMESPACE} permissions on the
        parent namespace.
        """
        values = [(u'user', Operation.CREATE_NAMESPACE, Policy.CLOSED, [])]
        self.permissions.set(values)
        error = self.assertRaises(PermissionDeniedError,
                                  self.tags.create,
                                  [(u'user/test', u'description')])
        self.assertEqual([(u'user', Operation.CREATE_NAMESPACE)],
                         sorted(error.pathsAndOperations))

    def testDeleteIsAllowed(self):
        """
        L{SecureTagAPI.delete} should allow the deletion of a tag if the user
        has C{Operation.DELETE_TAG} permissions.
        """
        result1 = self.tags.create([(u'user/test', u'description')])
        result2 = self.tags.delete([u'user/test'])
        self.assertEqual(result1, result2)

    def testDeleteIsDenied(self):
        """
        L{SecureTagAPI.delete} should raise L{PermissonDeniedError} if the
        user doesn't have C{Operation.DELETE_TAG} permissions.
        """
        self.tags.create([(u'user/test', u'description')])
        values = [(u'user/test', Operation.DELETE_TAG, Policy.OPEN, [u'user'])]
        self.permissions.set(values)
        error = self.assertRaises(PermissionDeniedError,
                                  self.tags.delete, [(u'user/test')])
        self.assertEqual([(u'user/test', Operation.DELETE_TAG)],
                         sorted(error.pathsAndOperations))

    def testSetIsAllowed(self):
        """
        L{SecureTagAPI.get} should allow updating the description of a tag if
        the user has permissions.
        """
        [(objectID, _)] = self.tags.create([(u'user/test', u'A description')])
        self.tags.set({u'user/test': u'A new description'})
        result = self.tags.get([u'user/test'], withDescriptions=True)
        expected = {u'user/test': {'id': objectID,
                                   'description': u'A new description'}}
        self.assertEqual(expected, result)

    def testSetIsDenied(self):
        """
        L{SecureTagAPI.get} should raise L{PermissonDeniedError} if the user
        doesn't have C{Operation.UPDATE_TAG} permissions when trying to update
        a tag's description.
        """
        self.tags.create([(u'user/test', u'description')])
        values = [(u'user/test', Operation.UPDATE_TAG, Policy.CLOSED, [])]
        self.permissions.set(values)
        error = self.assertRaises(PermissionDeniedError,
                                  self.tags.set,
                                  {u'user/test': u'description'})
        self.assertEqual([(u'user/test', Operation.UPDATE_TAG)],
                         sorted(error.pathsAndOperations))


class SecureTagAPIWithSuperuserTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureTagAPIWithSuperuserTest, self).setUp()
        system = createSystemData()
        user = system.users[u'fluiddb']
        self.tags = SecureTagAPI(user)
        self.permissions = CachingPermissionAPI(user)

    def testCreateIsAllowed(self):
        """
        Creating a new L{Tag} should be allowed if we're a user with a
        L{Role.SUPERUSER} no matter what permissions we have.
        """
        values = [(u'fluiddb', Operation.CREATE_NAMESPACE, Policy.CLOSED, [])]
        self.permissions.set(values)
        result = self.tags.create([(u'fluiddb/test', u'description')])
        self.assertEqual(1, len(result))

    def testDeleteIsAllowed(self):
        """
        Deleting a L{Tag} should be allowed if we're a user with a
        L{Role.SUPERUSER} no matter what permissions we have.
        """
        result1 = self.tags.create([(u'fluiddb/test', u'description')])
        values = [(u'fluiddb/test', Operation.DELETE_TAG, Policy.CLOSED, [])]
        self.permissions.set(values)
        result2 = self.tags.delete([u'fluiddb/test'])
        self.assertEqual(result1, result2)

    def testSetIsAllowed(self):
        """
        Updating a L{Tag} should be allowed if we're a user with a
        L{Role.SUPERUSER} no matter what permissions we have.
        """
        result = self.tags.create([(u'fluiddb/test', u'A description')])
        [(objectID, _)] = result
        values = [(u'fluiddb/test', Operation.UPDATE_TAG, Policy.CLOSED, [])]
        self.permissions.set(values)
        self.tags.set({u'fluiddb/test': u'A new description'})

        result = self.tags.get([u'fluiddb/test'], withDescriptions=True)
        expected = {u'fluiddb/test': {'id': objectID,
                                      'description': u'A new description'}}
        self.assertEqual(expected, result)
