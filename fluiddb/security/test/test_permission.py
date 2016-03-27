from fluiddb.cache.test.test_permission import CachingPermissionAPITestMixin
from fluiddb.data.permission import Operation, Policy, getTagPermissions
from fluiddb.data.system import createSystemData
from fluiddb.data.user import Role
from fluiddb.exceptions import FeatureError
from fluiddb.model.exceptions import UnknownPathError
from fluiddb.model.namespace import NamespaceAPI
from fluiddb.model.permission import PermissionAPI
from fluiddb.model.tag import TagAPI
from fluiddb.model.test.test_permission import PermissionAPITestMixin
from fluiddb.model.user import UserAPI, getUser
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.security.permission import SecurePermissionAPI, checkPermissions
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    BrokenCacheResource, CacheResource, ConfigResource, DatabaseResource,
    LoggingResource)


class SecurePermissionAPITestMixin(object):

    def testGetWithUnknownPaths(self):
        """
        L{SecurePermissionAPI.get} raises an L{UnknownPathError} if a path for
        unknown L{Namespace}s or L{Tag}s is specified.
        """
        values = [(u'unknown/namespace', Operation.CREATE_NAMESPACE)]
        error = self.assertRaises(UnknownPathError,
                                  self.permissions.get, values)
        self.assertEqual([u'unknown/namespace'], error.paths)

        error = self.assertRaises(UnknownPathError, self.permissions.get,
                                  [(u'unknown/tag', Operation.UPDATE_TAG)])
        self.assertEqual([u'unknown/tag'], error.paths)

    def testSetWithUnknownPaths(self):
        """
        L{PermissionAPI.set} raises an L{UnknownPathError} if a path for
        unknown L{Namespace}s or L{Tag}s is specified.
        """
        values = [(u'unknown/namespace', Operation.CREATE_NAMESPACE,
                   Policy.OPEN, [])]
        error = self.assertRaises(UnknownPathError,
                                  self.permissions.set, values)
        self.assertEqual([u'unknown/namespace'], error.paths)

        values = [(u'unknown/tag', Operation.UPDATE_TAG,
                   Policy.OPEN, [])]
        error = self.assertRaises(UnknownPathError,
                                  self.permissions.set, values)
        self.assertEqual([u'unknown/tag'], error.paths)


class SecurePermissionAPITest(PermissionAPITestMixin,
                              CachingPermissionAPITestMixin,
                              SecurePermissionAPITestMixin,
                              FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecurePermissionAPITest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = SecurePermissionAPI(self.user)


class SecurePermissionAPIWithBrokenCacheTest(PermissionAPITestMixin,
                                             SecurePermissionAPITestMixin,
                                             FluidinfoTestCase):

    resources = [('cache', BrokenCacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecurePermissionAPIWithBrokenCacheTest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = SecurePermissionAPI(self.user)


class SecurePermissionAPIWithAnonymousRoleTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecurePermissionAPIWithAnonymousRoleTest, self).setUp()
        system = createSystemData()
        user = system.users[u'anon']
        self.permissions = SecurePermissionAPI(user)
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        user = getUser(u'username')
        TagAPI(user).create([(u'username/tag', u'description')])

    def testGetNamespacePermissionsIsAlwaysDenied(self):
        """
        L{SecurePermissionAPI.get} always denies access to get namespace
        permissions for the anonymous user.
        """
        for operation in Operation.NAMESPACE_OPERATIONS:
            error = self.assertRaises(PermissionDeniedError,
                                      self.permissions.get,
                                      [(u'username', operation)])
            self.assertEqual([(u'username', Operation.CONTROL_NAMESPACE)],
                             sorted(error.pathsAndOperations))

    def testGetTagPermissionsIsAlwaysDenied(self):
        """
        L{SecurePermissionAPI.get} always denies access to get tag permissions
        for the anonymous user.
        """
        for operation in [Operation.UPDATE_TAG, Operation.DELETE_TAG,
                          Operation.CONTROL_TAG]:
            error = self.assertRaises(PermissionDeniedError,
                                      self.permissions.get,
                                      [(u'username/tag', operation)])
            self.assertEqual([(u'username/tag', Operation.CONTROL_TAG)],
                             sorted(error.pathsAndOperations))

    def testGetTagValuePermissionsIsAlwaysDenied(self):
        """
        L{SecurePermissionAPI.get} always denies access to get tag value
        permissions for the anonymous user.
        """
        for operation in [Operation.READ_TAG_VALUE, Operation.WRITE_TAG_VALUE,
                          Operation.DELETE_TAG_VALUE,
                          Operation.CONTROL_TAG_VALUE]:
            error = self.assertRaises(PermissionDeniedError,
                                      self.permissions.get,
                                      [(u'username/tag', operation)])
            self.assertEqual([(u'username/tag', Operation.CONTROL_TAG_VALUE)],
                             sorted(error.pathsAndOperations))

    def testSetNamespacePermissionsIsAlwaysDenied(self):
        """
        L{SecurePermissionAPI.set} always denies changes to namespace
        permissions for the anonymous user.
        """
        for operation in Operation.NAMESPACE_OPERATIONS:
            values = [(u'username', operation, Policy.OPEN, [])]
            error = self.assertRaises(PermissionDeniedError,
                                      self.permissions.set, values)
            self.assertEqual([(u'username', Operation.CONTROL_NAMESPACE)],
                             sorted(error.pathsAndOperations))

    def testSetTagPermissionsIsAlwaysDenied(self):
        """
        L{SecurePermissionAPI.set} always denies changes to tag permissions for
        the anonymous user.
        """
        for operation in [Operation.UPDATE_TAG, Operation.DELETE_TAG,
                          Operation.CONTROL_TAG]:
            values = [(u'username/tag', operation, Policy.OPEN, [])]
            error = self.assertRaises(PermissionDeniedError,
                                      self.permissions.set, values)
            self.assertEqual([(u'username/tag', Operation.CONTROL_TAG)],
                             sorted(error.pathsAndOperations))

    def testSetTagValuePermissionsIsAlwaysDenied(self):
        """
        L{SecurePermissionAPI.set} always denies changes to tag permissions for
        the anonymous user.
        """
        for operation in [Operation.READ_TAG_VALUE, Operation.WRITE_TAG_VALUE,
                          Operation.DELETE_TAG_VALUE,
                          Operation.CONTROL_TAG_VALUE]:
            values = [(u'username/tag', operation, Policy.OPEN, [])]
            error = self.assertRaises(PermissionDeniedError,
                                      self.permissions.set, values)
            self.assertEqual([(u'username/tag', Operation.CONTROL_TAG_VALUE)],
                             sorted(error.pathsAndOperations))


class SecurePermissionAPIWithNormalUserTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecurePermissionAPIWithNormalUserTest, self).setUp()
        createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        user = getUser(u'username')
        TagAPI(user).create([(u'username/tag', u'description')])
        self.permissions = SecurePermissionAPI(user)

    def testGetNamespacePermissionsIsAllowed(self):
        """
        Getting namespace permissions is allowed if the user has
        C{Operation.CONTROL_NAMESPACE} permissions.
        """
        self.permissions.set([(u'username', Operation.CONTROL_NAMESPACE,
                               Policy.OPEN, [])])
        result = self.permissions.get([(u'username',
                                        Operation.CREATE_NAMESPACE)])
        self.assertEqual(1, len(result))

    def testGetNamespacePermissionsIsDenied(self):
        """
        L{SecurePermissionAPI.set} should raise a L{PermissionDeniedError} if
        the user doesn't have C{Operation.CONTROL_NAMESPACE} permissions on the
        given path.
        """
        self.permissions.set([(u'username', Operation.CONTROL_NAMESPACE,
                               Policy.CLOSED, [])])
        values = [(u'username', Operation.DELETE_NAMESPACE)]
        error = self.assertRaises(PermissionDeniedError,
                                  self.permissions.get, values)
        self.assertEqual([(u'username', Operation.CONTROL_NAMESPACE)],
                         sorted(error.pathsAndOperations))

    def testGetTagPermissionsIsAllowed(self):
        """
        Getting tag permissions is allowed if the user has
        C{Operation.CONTROL_TAG} permissions.
        """
        self.permissions.set([(u'username/tag', Operation.CONTROL_TAG,
                               Policy.OPEN, [])])
        result = self.permissions.get([(u'username/tag',
                                        Operation.UPDATE_TAG)])
        self.assertEqual(1, len(result))

    def testGetTagPermissionsIsDenied(self):
        """
        L{SecurePermissionAPI.set} should raise a L{PermissionDeniedError} if
        the user doesn't have C{Operation.CONTROL_TAG} permissions on the
        given path.
        """
        self.permissions.set([(u'username/tag', Operation.CONTROL_TAG,
                               Policy.CLOSED, [])])
        values = [(u'username/tag', Operation.DELETE_TAG)]
        error = self.assertRaises(PermissionDeniedError,
                                  self.permissions.get, values)
        self.assertEqual([(u'username/tag', Operation.CONTROL_TAG)],
                         sorted(error.pathsAndOperations))

    def testGetTagValuePermissionsIsAllowed(self):
        """
        Getting tag value permissions is allowed if the user has
        C{Operation.CONTROL_TAG_VALUE} permissions.
        """
        self.permissions.set([(u'username/tag', Operation.CONTROL_TAG_VALUE,
                               Policy.OPEN, [])])
        result = self.permissions.get([(u'username/tag',
                                        Operation.READ_TAG_VALUE)])
        self.assertEqual(1, len(result))

    def testGetTagValuePermissionsIsDenied(self):
        """
        L{SecurePermissionAPI.get} should raise a L{PermissionDeniedError} if
        the user doesn't have C{Operation.CONTROL_TAG_VALUE} permissions on the
        given path.
        """
        self.permissions.set([(u'username/tag', Operation.CONTROL_TAG_VALUE,
                               Policy.CLOSED, [])])
        values = [(u'username/tag', Operation.WRITE_TAG_VALUE)]
        error = self.assertRaises(PermissionDeniedError,
                                  self.permissions.get, values)
        self.assertEqual([(u'username/tag', Operation.CONTROL_TAG_VALUE)],
                         sorted(error.pathsAndOperations))

    def testSetNamespacePermissionsIsAllowed(self):
        """
        Updating namespace permissions is allowed if the user has
        C{Operation.CONTROL_NAMESPACE} permissions.
        """
        self.permissions.set([(u'username', Operation.CONTROL_NAMESPACE,
                               Policy.OPEN, [])])
        values = [(u'username', Operation.CREATE_NAMESPACE, Policy.CLOSED, [])]
        self.permissions.set(values)
        pathAndOperations = [(u'username', Operation.CREATE_NAMESPACE)]
        expected = {
            (u'username', Operation.CREATE_NAMESPACE): (Policy.CLOSED, [])}
        self.assertEqual(expected, self.permissions.get(pathAndOperations))

    def testSetNamespacePermissionsIsDenied(self):
        """
        L{SecurePermissionAPI.set} should raise a L{PermissionDeniedError} if
        the user doesn't have C{Operation.CONTROL_NAMESPACE} permissions on the
        given path.
        """
        self.permissions.set([(u'username', Operation.CONTROL_NAMESPACE,
                               Policy.CLOSED, [])])
        values = [(u'username', Operation.DELETE_NAMESPACE, Policy.OPEN, [])]
        error = self.assertRaises(PermissionDeniedError,
                                  self.permissions.set, values)
        self.assertEqual([(u'username', Operation.CONTROL_NAMESPACE)],
                         sorted(error.pathsAndOperations))

    def testSetTagPermissionsIsAllowed(self):
        """
        Updating tag permissions is allowed if the user has
        C{Operation.CONTROL_TAG} permissions.
        """
        self.permissions.set([(u'username/tag', Operation.CONTROL_TAG,
                               Policy.OPEN, [])])
        values = [(u'username/tag', Operation.UPDATE_TAG, Policy.CLOSED, [])]
        self.permissions.set(values)
        pathAndOperations = [(u'username/tag', Operation.UPDATE_TAG)]
        expected = {
            (u'username/tag', Operation.UPDATE_TAG): (Policy.CLOSED, [])}
        self.assertEqual(expected, self.permissions.get(pathAndOperations))

    def testSetTagPermissionsIsDenied(self):
        """
        L{SecurePermissionAPI.set} should raise a L{PermissionDeniedError} if
        the user doesn't have C{Operation.CONTROL_TAG} permissions on the
        given path.
        """
        self.permissions.set([(u'username/tag', Operation.CONTROL_TAG,
                               Policy.CLOSED, [])])
        values = [(u'username/tag', Operation.DELETE_TAG,
                  Policy.OPEN, [])]
        error = self.assertRaises(PermissionDeniedError,
                                  self.permissions.set, values)
        self.assertEqual([(u'username/tag', Operation.CONTROL_TAG)],
                         sorted(error.pathsAndOperations))

    def testSetTagValuePermissionsIsAllowed(self):
        """
        Updating tag value permissions is allowed if the user has
        C{Operation.CONTROL_TAG_VALUE} permissions.
        """
        self.permissions.set([(u'username/tag', Operation.CONTROL_TAG_VALUE,
                               Policy.OPEN, [])])
        values = [(u'username/tag', Operation.READ_TAG_VALUE,
                   Policy.CLOSED, [])]
        self.permissions.set(values)
        pathAndOperations = [(u'username/tag', Operation.READ_TAG_VALUE)]
        expected = {
            (u'username/tag', Operation.READ_TAG_VALUE): (Policy.CLOSED, [])}
        self.assertEqual(expected, self.permissions.get(pathAndOperations))

    def testSetTagValuePermissionsIsDenied(self):
        """
        L{SecurePermissionAPI.set} should raise a L{PermissionDeniedError} if
        the user doesn't have C{Operation.CONTROL_TAG_VALUE} permissions on the
        given path.
        """
        self.permissions.set([(u'username/tag', Operation.CONTROL_TAG_VALUE,
                               Policy.CLOSED, [])])
        values = [(u'username/tag', Operation.WRITE_TAG_VALUE,
                   Policy.CLOSED, [])]
        error = self.assertRaises(PermissionDeniedError,
                                  self.permissions.set, values)
        self.assertEqual([(u'username/tag', Operation.CONTROL_TAG_VALUE)],
                         sorted(error.pathsAndOperations))


class SecurePermissionAPIWithSuperUserRoleTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecurePermissionAPIWithSuperUserRoleTest, self).setUp()
        system = createSystemData()
        user = system.users[u'fluiddb']
        self.permissions = SecurePermissionAPI(user)
        TagAPI(user).create([(u'fluiddb/tag', u'description')])

    def testGetNamespacePermissionsIsAlwaysAllowed(self):
        """
        Getting namespace permissions is always allowed for the superuser.
        """
        self.permissions.set([(u'fluiddb', Operation.CONTROL_NAMESPACE,
                               Policy.CLOSED, [])])
        result = self.permissions.get([(u'fluiddb',
                                        Operation.CREATE_NAMESPACE)])
        self.assertEqual(1, len(result))

    def testGetTagPermissionsIsAllowed(self):
        """
        Getting tag permissions is always allowed for the superuser.
        """
        self.permissions.set([(u'fluiddb/tag', Operation.CONTROL_TAG,
                               Policy.CLOSED, [])])
        result = self.permissions.get([(u'fluiddb/tag',
                                        Operation.UPDATE_TAG)])
        self.assertEqual(1, len(result))

    def testGetTagValuePermissionsIsAllowed(self):
        """
        Getting tag-value permissions is always allowed for the superuser.
        """
        self.permissions.set([(u'fluiddb/tag', Operation.CONTROL_TAG_VALUE,
                               Policy.CLOSED, [])])
        result = self.permissions.get([(u'fluiddb/tag',
                                        Operation.READ_TAG_VALUE)])
        self.assertEqual(1, len(result))

    def testSetNamespacePermissionsIsAlwaysAllowed(self):
        """
        Updating namespace permissions is always allowed for the superuser.
        """
        self.permissions.set([(u'fluiddb', Operation.CONTROL_NAMESPACE,
                               Policy.CLOSED, [])])
        values = [(u'fluiddb', Operation.CREATE_NAMESPACE, Policy.OPEN, [])]
        self.permissions.set(values)
        pathAndOperations = [(u'fluiddb', Operation.CREATE_NAMESPACE)]
        expected = {
            (u'fluiddb', Operation.CREATE_NAMESPACE): (Policy.OPEN, [])}
        self.assertEqual(expected, self.permissions.get(pathAndOperations))

    def testSetTagPermissionsIsAllowed(self):
        """
        Updating tag permissions is always allowed for the superuser.
        """
        self.permissions.set([(u'fluiddb/tag', Operation.CONTROL_TAG,
                               Policy.CLOSED, [])])
        values = [(u'fluiddb/tag', Operation.UPDATE_TAG, Policy.OPEN, [])]
        self.permissions.set(values)
        pathAndOperations = [(u'fluiddb/tag', Operation.UPDATE_TAG)]
        expected = {
            (u'fluiddb/tag', Operation.UPDATE_TAG): (Policy.OPEN, [])}
        self.assertEqual(expected, self.permissions.get(pathAndOperations))

    def testSetTagValuePermissionsIsAllowed(self):
        """
        Updating tag-value permissions is always allowed for the superuser.
        """
        self.permissions.set([(u'fluiddb/tag', Operation.CONTROL_TAG_VALUE,
                               Policy.CLOSED, [])])
        values = [(u'fluiddb/tag', Operation.READ_TAG_VALUE, Policy.OPEN, [])]
        self.permissions.set(values)
        pathAndOperations = [(u'fluiddb/tag', Operation.READ_TAG_VALUE)]
        expected = {
            (u'fluiddb/tag', Operation.READ_TAG_VALUE): (Policy.OPEN, [])}
        self.assertEqual(expected, self.permissions.get(pathAndOperations))


class CheckPermissionsTestMixin(object):

    def testCheckRaisesFeatureErrorIfValuesIsEmpty(self):
        """
        L{checkPermissions} returns an empty list of values if a list of values
        is empty.
        """
        self.assertEqual([], checkPermissions(self.user, []))

    def testCheckRaisesFeatureErrorIfPathIsNone(self):
        """
        L{checkPermissions} raises L{FeatureError} if one of the given paths is
        None.
        """
        values = [(None, Operation.WRITE_TAG_VALUE)]
        self.assertRaises(FeatureError, checkPermissions, self.user, values)

    def testCheckRaisesFeatureErrorIfOperationIsInvalid(self):
        """
        L{checkPermissions} raises L{FeatureError} if one of the given
        operations is invalid.
        """
        values = [(u'username', None)]
        self.assertRaises(FeatureError, checkPermissions, self.user, values)


class UserPermissionCheckerTest(CheckPermissionsTestMixin, FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('cache', CacheResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(UserPermissionCheckerTest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = PermissionAPI(self.user)

    def testCheckOpenPermission(self):
        """
        L{checkPermissions} grants access when the policy is C{Policy.OPEN}
        and the L{User.id} is not in the exceptions list.
        """
        TagAPI(self.user).create([(u'username/tag', u'description')])
        self.permissions.set([(u'username/tag', Operation.UPDATE_TAG,
                               Policy.OPEN, [])])

        values = [(u'username/tag', Operation.UPDATE_TAG)]
        deniedOperations = checkPermissions(self.user, values)
        self.assertEqual([], deniedOperations)

    def testCheckOpenPermissionWithException(self):
        """
        L{checkPermissions} denies access when the policy is C{Policy.OPEN}
        and the L{User.id} is in the exceptions list.
        """
        TagAPI(self.user).create([(u'username/tag', u'description')])
        self.permissions.set([(u'username/tag', Operation.UPDATE_TAG,
                               Policy.OPEN, [u'username'])])

        values = [(u'username/tag', Operation.UPDATE_TAG)]
        deniedOperations = checkPermissions(self.user, values)
        self.assertEqual([(u'username/tag', Operation.UPDATE_TAG)],
                         list(deniedOperations))

    def testCheckClosedPermission(self):
        """
        L{checkPermissions} denies access when the policy is
        C{Policy.CLOSED} and the L{User.id} is not in the exceptions list.
        """
        TagAPI(self.user).create([(u'username/tag', u'description')])
        self.permissions.set([(u'username/tag', Operation.UPDATE_TAG,
                               Policy.CLOSED, [])])

        values = [(u'username/tag', Operation.UPDATE_TAG)]
        deniedOperations = checkPermissions(self.user, values)
        self.assertEqual([(u'username/tag', Operation.UPDATE_TAG)],
                         deniedOperations)

    def testCheckClosedPermissionWithException(self):
        """
        L{checkPermissions} grants access when the policy is C{Policy.OPEN}
        and the L{User.id} is in the exceptions list.
        """
        TagAPI(self.user).create([(u'username/tag', u'description')])
        self.permissions.set([(u'username/tag', Operation.UPDATE_TAG,
                               Policy.CLOSED, [u'username'])])

        values = [(u'username/tag', Operation.UPDATE_TAG)]
        deniedOperations = checkPermissions(self.user, values)
        self.assertEqual([], deniedOperations)

    def testCheckMultipleOpenPermissions(self):
        """L{checkPermissions} can check multiple permissions."""
        UserAPI().create([(u'user1', 'hash', u'User', u'user@example.com')])
        UserAPI().create([(u'user2', 'hash', u'User', u'user@example.com')])
        user1 = getUser(u'user1')
        user2 = getUser(u'user2')

        TagAPI(user1).create([(u'user1/tag', u'description')])
        self.permissions.set([(u'user1/tag', Operation.UPDATE_TAG,
                               Policy.OPEN, [u'user1', u'user2'])])

        TagAPI(user2).create([(u'user2/tag', u'description')])
        self.permissions.set([(u'user2/tag', Operation.WRITE_TAG_VALUE,
                               Policy.CLOSED, [u'username'])])

        values = [(u'user1/tag', Operation.UPDATE_TAG),
                  (u'user2/tag', Operation.WRITE_TAG_VALUE)]

        deniedOperations = checkPermissions(self.user, values)
        self.assertEqual([], deniedOperations)

    def testCheckUserWithUnknownPath(self):
        """
        L{checkPermissions} raises L{UnknownPathError} if a given path does
        not exist.
        """
        values = [(u'unknown/path', Operation.LIST_NAMESPACE)]
        error = self.assertRaises(UnknownPathError, checkPermissions,
                                  self.user, values)
        self.assertEqual([u'unknown/path'], error.paths)

    def testCheckUserWithImplicitTagPath(self):
        """
        L{checkPermissions} ignores an unknown path when a
        L{Operation.WRITE_TAG_VALUE} operation is requested and when the user
        has L{Operation.CREATE_NAMESPACE} access on the parent L{Namespace}.
        """
        values = [(u'username/unknown', Operation.WRITE_TAG_VALUE)]
        self.assertEqual([], checkPermissions(self.user, values))

    def testCheckUserWithImplicitNamespacePath(self):
        """
        L{checkPermissions} ignores an unknown path when a
        L{Operation.CREATE_NAMESPACE} operation is requested and when the user
        has L{Operation.CREATE_NAMESPACE} access on the final existing
        parent's L{Namespace}.
        """
        values = [(u'username/namespace', Operation.CREATE_NAMESPACE)]
        self.assertEqual([], checkPermissions(self.user, values))

    def testCheckUserWithImplicitTagAndNamespace(self):
        """
        L{checkPermissions} ignores an unknown path when a
        L{Operation.WRITE_TAG_VALUE} operation is requested and when the user
        has L{Operation.CREATE_NAMESPACE} access on the final existing
        parent's L{Namespace}.
        """
        values = set([(u'username/tag', Operation.WRITE_TAG_VALUE),
                      (u'username/namespace/tag', Operation.WRITE_TAG_VALUE)])
        self.assertEqual([], checkPermissions(self.user, values))

    def testCheckUserWithImplicitNestedNamespacePath(self):
        """
        L{checkPermissions} does a recursive check to find the parent
        L{Namespace} when a path includes many unknown segments.
        """
        values = [(u'username/nested/namespace', Operation.CREATE_NAMESPACE)]
        self.assertEqual([], checkPermissions(self.user, values))

    def testCheckUserWithFluidDBSlashIDVirtualPath(self):
        """
        An L{UnknownPathError} is not raised when the special C{fluiddb/id}
        virtual tag is encountered and L{Tag}-related permission checks always
        succeed.
        """
        values = [(u'fluiddb/id', Operation.READ_TAG_VALUE)]
        self.assertEqual([], checkPermissions(self.user, values))

    def testCheckUserWithMissingPermission(self):
        """
        L{checkPermissions} denies the operation if, for some
        reason, a permission is not available for the entity being requested.
        """
        TagAPI(self.user).create([(u'username/tag', u'description')])
        # FIXME: don't use data functions here.
        [(tag, permission)] = getTagPermissions([u'username/tag'])
        self.store.remove(permission)
        values = [(u'username/tag', Operation.UPDATE_TAG)]
        deniedOperations = checkPermissions(self.user, values)
        self.assertEqual([(u'username/tag', Operation.UPDATE_TAG)],
                         deniedOperations)

    def testCheckReturnsMultipleDeniedPermissions(self):
        """
        L{checkPermissions} returns a C{list} of all denied paths and
        L{Operation}s for the requested actions.
        """
        UserAPI().create([(u'user1', 'hash', u'User', u'user@example.com')])
        UserAPI().create([(u'user2', 'hash', u'User', u'user@example.com')])
        user1 = getUser(u'user1')
        user2 = getUser(u'user2')

        TagAPI(user1).create([(u'user1/tag', u'description')])
        self.permissions.set([(u'user1/tag', Operation.UPDATE_TAG,
                               Policy.OPEN, [u'user1', u'user2'])])

        TagAPI(user2).create([(u'user2/tag', u'description')])
        self.permissions.set([(u'user2/tag', Operation.WRITE_TAG_VALUE,
                               Policy.OPEN, [u'username'])])

        values = [(u'user1/tag', Operation.UPDATE_TAG),
                  (u'user2/tag', Operation.WRITE_TAG_VALUE)]
        deniedOperations = checkPermissions(self.user, values)
        expected = [(u'user2/tag', Operation.WRITE_TAG_VALUE)]
        self.assertEqual(sorted(expected), sorted(deniedOperations))

    def testCheckUserManagerHasAccessToPerformUserOperations(self):
        """
        L{checkPermissions} always allows user L{Operation}s for
        L{Role.USER_MANAGER} users.
        """
        self.user.role = Role.USER_MANAGER
        values = [(u'username', Operation.CREATE_USER),
                  (u'username', Operation.UPDATE_USER),
                  (u'username', Operation.DELETE_USER)]
        deniedOperations = checkPermissions(self.user, values)
        self.assertEqual([], deniedOperations)

    def testCheckCreateRootNamespaceIsAlwaysDeniedForNormalUser(self):
        """
        L{checkPermissions} always denies C{CREATE_NAMESPACE} access on the
        root namespace for normal users.
        """
        values = [(None, Operation.CREATE_NAMESPACE)]
        deniedOperations = checkPermissions(self.user, values)
        self.assertEqual([(None, Operation.CREATE_NAMESPACE)],
                         deniedOperations)

    def testCheckDeleteRootNamespaceIsAlwaysDeniedForNormalUser(self):
        """
        L{checkPermissions} always denies C{DELETE_NAMESPACE} access on the
        root namespace for normal users.
        """
        values = [(u'username', Operation.DELETE_NAMESPACE)]
        deniedOperations = checkPermissions(self.user, values)
        self.assertEqual([(u'username', Operation.DELETE_NAMESPACE)],
                         deniedOperations)

    def testCheckCreateObjectIsAlwaysGrantedForNormalUser(self):
        """
        L{checkPermissions} always grants C{CREATE_OBJECT} access for
        normal users.
        """
        values = [(u'', Operation.CREATE_OBJECT)]
        deniedOperations = checkPermissions(self.user, values)
        self.assertEqual([], deniedOperations)

    def testCheckCreateUserIsAlwaysDeniedForNormalUser(self):
        """
        L{checkPermissions} always denies C{CREATE_USER} access for normal
        users.
        """
        values = [(u'username', Operation.CREATE_USER)]
        deniedOperations = checkPermissions(self.user, values)
        self.assertEqual([(u'username', Operation.CREATE_USER)],
                         deniedOperations)

    def testCheckUpdateUserIsDeniedForOtherNormalUsers(self):
        """
        L{checkPermissions} denies C{UPDATE_USER} access for normal
        users except the own user.
        """
        UserAPI().create([(u'otheruser', u'password', u'User',
                           u'user@example.com')])
        values = [(u'otheruser', Operation.UPDATE_USER)]
        deniedOperations = checkPermissions(self.user, values)
        self.assertEqual([(u'otheruser', Operation.UPDATE_USER)],
                         deniedOperations)

    def testCheckUpdateUserIsAllowedForTheOwnUser(self):
        """
        L{checkPermissions} allows C{UPDATE_USER} access for normal
        users if the requesting user is the same modified user.
        """
        values = [(u'username', Operation.UPDATE_USER)]
        deniedOperations = checkPermissions(self.user, values)
        self.assertEqual([], deniedOperations)


class AnonymousPermissionCheckerTest(CheckPermissionsTestMixin,
                                     FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('cache', CacheResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(AnonymousPermissionCheckerTest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')

    def testCheckAnonymousWithUnknownPath(self):
        """
        L{checkPermissions} raises L{UnknownPathError} if a given path does
        not exist.
        """
        anonymous = self.system.users[u'anon']
        values = [(u'unknown/path', Operation.LIST_NAMESPACE)]
        error = self.assertRaises(UnknownPathError, checkPermissions,
                                  anonymous, values)
        self.assertEqual([u'unknown/path'], error.paths)

    def testCheckAnonymousWithImplicitPath(self):
        """
        L{checkPermissions} denies prevents L{Role.ANONYMOUS} L{User}s from
        implicitly creating tags because the anoymous user is not allowed to
        perform L{Operation.WRITE_TAG_VALUE} operations.
        """
        anonymous = self.system.users[u'anon']
        values = [(u'anon/path', Operation.WRITE_TAG_VALUE)]
        self.assertEqual([(u'anon/path', Operation.WRITE_TAG_VALUE)],
                         checkPermissions(anonymous, values))

    def testCheckAnonymousWithFluidDBSlashIDVirtualPath(self):
        """
        An L{UnknownPathError} is not raised when the special C{fluiddb/id}
        virtual tag is encountered and L{Tag}-related permission checks always
        succeed.
        """
        anonymous = self.system.users[u'anon']
        values = [(u'fluiddb/id', Operation.READ_TAG_VALUE)]
        self.assertEqual([], checkPermissions(anonymous, values))

    def testCheckAnonymousWithMissingPermission(self):
        """
        L{checkPermissions} denies the operations, for some
        reason, a permission is not available for the entity being requested.
        """
        anonymous = self.system.users[u'anon']
        TagAPI(self.user).create([(u'username/tag', u'description')])

        values = [(u'username/tag', Operation.READ_TAG_VALUE)]
        # FIXME: don't use data functions here.
        [(tag, permission)] = getTagPermissions([u'username/tag'])
        self.store.remove(permission)
        deniedOperations = checkPermissions(anonymous, values)
        self.assertEqual([(u'username/tag', Operation.READ_TAG_VALUE)],
                         deniedOperations)

    def testCheckAnonymousForbiddenOperations(self):
        """
        L{checkPermissions} always denies C{CREATE}, C{UPDATE}, or
        C{DELETE} operations if the user is anonymous.
        """
        TagAPI(self.user).create([(u'username/path', u'description')])
        NamespaceAPI(self.user).create([(u'username/path', u'description')])
        anonymous = self.system.users[u'anon']
        forbiddenOperations = (
            Operation.TAG_OPERATIONS + Operation.NAMESPACE_OPERATIONS +
            Operation.USER_OPERATIONS + Operation.CONTROL_OPERATIONS +
            [Operation.CREATE_OBJECT])
        for operation in Operation.ALLOWED_ANONYMOUS_OPERATIONS:
            forbiddenOperations.remove(operation)
        values = [(u'username/path', operation)
                  for operation in forbiddenOperations]
        deniedOperations = checkPermissions(anonymous, values)
        self.assertEqual(sorted(values),
                         sorted(deniedOperations))

    def testCheckCreateRootNamespaceIsAlwaysDeniedForAnonymous(self):
        """
        L{checkPermissions} always denies C{CREATE_NAMESPACE} access on the
        root namespace for anonymous users.
        """
        anonymous = self.system.users[u'anon']
        values = [(None, Operation.CREATE_NAMESPACE)]
        deniedOperations = checkPermissions(anonymous, values)
        self.assertEqual([(None, Operation.CREATE_NAMESPACE)],
                         deniedOperations)

    def testCheckDeleteRootNamespaceIsAlwaysDeniedForAnonymous(self):
        """
        L{checkPermissions} always denies C{DELETE_NAMESPACE} access on the
        root namespace for anonymous users.
        """
        anonymous = self.system.users[u'anon']
        values = [(u'anon', Operation.DELETE_NAMESPACE)]
        deniedOperations = checkPermissions(anonymous, values)
        self.assertEqual([(u'anon', Operation.DELETE_NAMESPACE)],
                         deniedOperations)

    def testCheckCreateUserIsAlwaysDeniedForAnonymousUser(self):
        """
        L{checkPermissions} always denies C{CREATE_USER} access for
        anonymous users.
        """
        anonymous = self.system.users[u'anon']
        values = [(u'anon', Operation.CREATE_USER)]
        deniedOperations = checkPermissions(anonymous, values)
        self.assertEqual([(u'anon', Operation.CREATE_USER)],
                         deniedOperations)


class SuperuserPermissionCheckerTest(CheckPermissionsTestMixin,
                                     FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('cache', CacheResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SuperuserPermissionCheckerTest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = PermissionAPI(self.user)

    def testCheckWithSuperuser(self):
        """
        L{checkPermissions} always grants access if the user is superuser.
        """
        TagAPI(self.user).create([(u'username/path', u'description')])
        NamespaceAPI(self.user).create([(u'username/path', u'description')])
        superuser = self.system.users[u'fluiddb']
        # Close all permissions for the tag
        values = [(u'username/path', operation, Policy.CLOSED, [])
                  for operation in Operation.PATH_OPERATIONS]
        self.permissions.set(values)

        values = [(u'username/path', operation)
                  for operation in Operation.PATH_OPERATIONS]
        deniedOperations = checkPermissions(superuser, values)
        self.assertEqual([], deniedOperations)

    def testCheckWithSuperuserUnknownPaths(self):
        """
        L{checkPermissions} raises L{UnknownPathError} if a superuser checks
        permissions for nonexistent tags.
        """
        superuser = self.system.users[u'fluiddb']
        values = [(u'unknown/path', operation)
                  for operation in Operation.PATH_OPERATIONS]
        self.assertRaises(UnknownPathError,
                          checkPermissions, superuser, values)

    def testCheckWithSuperuserWithImplicitPaths(self):
        """
        L{checkPermissions} raises L{UnknownPathError} if a superuser
        checks permissions for nonexistent tags, even if it might be possible
        to create them implicitly.
        """
        superuser = self.system.users[u'fluiddb']
        values = [(u'fluiddb/path', operation)
                  for operation in Operation.PATH_OPERATIONS]
        self.assertRaises(UnknownPathError,
                          checkPermissions, superuser, values)

    def testCheckWithSuperuserWithMissingPermission(self):
        """
        L{checkPermissions} always grants access if the user is superuser,
        even if there is no permission defined for the entity for which access
        is requested.
        """
        TagAPI(self.user).create([(u'username/path', u'description')])
        NamespaceAPI(self.user).create([(u'username/path', u'description')])
        superuser = self.system.users[u'fluiddb']
        # Close all permissions for the tag
        values = [(u'username/path', operation, Policy.CLOSED, [])
                  for operation in Operation.NAMESPACE_OPERATIONS]
        self.permissions.set(values)

        values = [(u'username/path', operation)
                  for operation in Operation.NAMESPACE_OPERATIONS]
        deniedOperations = checkPermissions(superuser, values)
        self.assertEqual([], deniedOperations)

    def testCheckSuperuserWithFluidDBSlashIDVirtualPath(self):
        """
        An L{UnknownPathError} is not raised when the special C{fluiddb/id}
        virtual tag is encountered and L{Tag}-related permission checks always
        succeed.
        """
        superuser = self.system.users[u'fluiddb']
        values = [(u'fluiddb/id', Operation.READ_TAG_VALUE)]
        self.assertEqual([], checkPermissions(superuser, values))
