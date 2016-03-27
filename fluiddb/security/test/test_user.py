from fluiddb.cache.test.test_user import CachingUserAPITestMixin
from fluiddb.data.permission import Operation
from fluiddb.data.system import createSystemData
from fluiddb.model.test.test_user import UserAPITestMixin
from fluiddb.model.user import UserAPI, getUser
from fluiddb.security.namespace import SecureNamespaceAPI
from fluiddb.security.user import SecureUserAPI
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    BrokenCacheResource, CacheResource, ConfigResource, DatabaseResource,
    LoggingResource)


class SecureUserAPITest(UserAPITestMixin, CachingUserAPITestMixin,
                        FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureUserAPITest, self).setUp()
        self.system = createSystemData()
        user = self.system.users[u'fluiddb']
        self.users = SecureUserAPI(user)


class SecureUserAPIWithBrokenCacheTest(UserAPITestMixin, FluidinfoTestCase):

    resources = [('cache', BrokenCacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureUserAPIWithBrokenCacheTest, self).setUp()
        self.system = createSystemData()
        user = self.system.users[u'fluiddb']
        self.users = SecureUserAPI(user)


class SecureUserAPIWithAnonymousRoleTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureUserAPIWithAnonymousRoleTest, self).setUp()
        system = createSystemData()
        self.user = system.users[u'anon']
        self.users = SecureUserAPI(self.user)

    def testCreateIsDenied(self):
        """
        L{SecureUserAPI.create} raises a L{PermissionDeniedError} if it's
        invoked by a L{User} with the L{Role.ANONYMOUS}.
        """
        values = [(u'user', u'secret', u'User', u'user@example.com')]
        error = self.assertRaises(PermissionDeniedError, self.users.create,
                                  values)
        self.assertEqual(self.user.username, error.username)
        self.assertEqual([(u'user', Operation.CREATE_USER)],
                         error.pathsAndOperations)

    def testDeleteIsDenied(self):
        """
        L{SecureUserAPI.delete} raises a L{PermissionDeniedError} if it's
        invoked by a L{User} with the L{Role.ANONYMOUS}.
        """
        error = self.assertRaises(PermissionDeniedError, self.users.delete,
                                  [u'user'])
        self.assertEqual(self.user.username, error.username)
        self.assertEqual([(u'user', Operation.DELETE_USER)],
                         error.pathsAndOperations)

    def testGetIsAllowed(self):
        """
        L{SecureUserAPI.get} can always be invoked by a L{User} with the
        L{Role.ANONYMOUS}.
        """
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        result = self.users.get([u'user'])
        self.assertIn(u'user', result)

    def testSetIsDenied(self):
        """
        L{SecureUserAPI.set} raises a L{PermissionDeniedError} if it's invoked
        by a L{User} with the L{Role.ANONYMOUS}.
        """
        values = [(u'user', u'secret', u'User', u'user@example.com', None)]
        error = self.assertRaises(PermissionDeniedError, self.users.set,
                                  values)
        self.assertEqual(self.user.username, error.username)
        self.assertEqual([(u'user', Operation.UPDATE_USER)],
                         error.pathsAndOperations)


class SecureUserAPIWithNormalUserRoleTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureUserAPIWithNormalUserRoleTest, self).setUp()
        createSystemData()
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        self.user = getUser(u'user')
        self.users = SecureUserAPI(self.user)

    def testCreateIsDenied(self):
        """
        L{SecureUserAPI.create} raises a L{PermissionDeniedError} if it's
        invoked by a L{User} with the L{Role.USER}.
        """
        values = [(u'user', u'secret', u'User', u'user@example.com')]
        error = self.assertRaises(PermissionDeniedError, self.users.create,
                                  values)
        self.assertEqual(self.user.username, error.username)
        self.assertEqual([(u'user', Operation.CREATE_USER)],
                         error.pathsAndOperations)

    def testDeleteIsDenied(self):
        """
        L{SecureUserAPI.delete} raises a L{PermissionDeniedError} if it's
        invoked by a L{User} with the L{Role.USER}.
        """
        error = self.assertRaises(PermissionDeniedError, self.users.delete,
                                  [u'user'])
        self.assertEqual(self.user.username, error.username)
        self.assertEqual([(u'user', Operation.DELETE_USER)],
                         error.pathsAndOperations)

    def testGetIsAllowed(self):
        """
        L{SecureUserAPI.get} can always be invoked by a L{User} with the
        L{Role.USER}.
        """
        UserAPI().create([(u'username', u'secret', u'Username',
                           u'user@example.com')])
        result = self.users.get([u'username'])
        self.assertIn(u'username', result)

    def testSetIsDenied(self):
        """
        L{SecureUserAPI.set} raises a L{PermissionDeniedError} if it's invoked
        by a L{User} with the L{Role.USER} different than the own user.
        """
        UserAPI().create([(u'other', u'secret', u'User', u'user@example.com')])
        values = [(u'other', u'secret', u'User', u'user@example.com', None)]
        error = self.assertRaises(PermissionDeniedError, self.users.set,
                                  values)
        self.assertEqual(self.user.username, error.username)
        self.assertEqual([(u'other', Operation.UPDATE_USER)],
                         error.pathsAndOperations)

    def testSetIsAllowed(self):
        """
        L{SecureUserAPI.set} is allowed for the own L{User}.
        """
        self.users.set([(u'user', u'secret', u'New', u'new@example.com',
                         None)])
        self.assertEqual(u'new@example.com', self.user.email)
        self.assertEqual(u'New', self.user.fullname)


class SecureUserAPIWithSuperuserRoleTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureUserAPIWithSuperuserRoleTest, self).setUp()
        self.system = createSystemData()
        self.users = SecureUserAPI(self.system.users[u'fluiddb'])

    def testCreateIsAllowed(self):
        """
        L{SecureUserAPI.create} can always be invoked by a L{User} with the
        L{Role.SUPERUSER}.
        """
        self.users.create([(u'user', u'secret', u'User', u'user@example.com')])
        user = getUser(u'user')
        self.assertEqual(u'user', user.username)

    def testDeleteIsAllowed(self):
        """
        L{SecureUserAPI.delete} can always be invoked by a L{User} with the
        L{Role.SUPERUSER}.
        """
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        namespaces = SecureNamespaceAPI(self.system.users['fluiddb'])
        namespaces.delete([u'user/private'])
        self.users.delete([u'user'])
        self.assertIdentical(None, getUser(u'user'))

    def testGetIsAllowed(self):
        """
        L{SecureUserAPI.get} can always be invoked by a L{User} with the
        L{Role.SUPERUSER}.
        """
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        result = self.users.get([u'user'])
        self.assertIn(u'user', result)

    def testSetIsAllowed(self):
        """
        L{SecureUserAPI.set} can always be invoked by a L{User} with the
        L{Role.SUPERUSER}.
        """
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        user = getUser(u'user')
        self.users.set([(u'user', u'secret', u'User', u'other@example.com',
                         None)])
        self.assertEqual(u'other@example.com', user.email)
