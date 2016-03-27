from fluiddb.data.exceptions import UnknownUserError
from fluiddb.data.permission import (
    Operation, Policy, createTagPermission, getNamespacePermissions)
from fluiddb.data.system import createSystemData
from fluiddb.data.tag import createTag
from fluiddb.data.user import createUser
from fluiddb.exceptions import FeatureError
from fluiddb.model.exceptions import UserNotAllowedInExceptionError
from fluiddb.model.permission import PermissionAPI, PermissionCheckerAPI
from fluiddb.model.tag import TagAPI
from fluiddb.model.user import UserAPI, getUser
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import ConfigResource, DatabaseResource


class PermissionAPITestMixin(object):

    def testSet(self):
        """
        L{PermissionAPI.set} updates existing permissions for the given values.
        """
        user1 = createUser(u'user1', u'secret', u'User1', u'user1@example.com')
        user2 = createUser(u'user2', u'secret', u'User2', u'user2@example.com')
        self.permissions.set([(u'username', Operation.CREATE_NAMESPACE,
                               Policy.OPEN, [u'user1', u'user2'])])
        namespace, permission = getNamespacePermissions([u'username']).one()
        self.assertEqual(Policy.OPEN, permission.createPolicy)
        self.assertEqual([user1.id, user2.id], permission.createExceptions)

    def testSetWithUnknownUser(self):
        """
        L{PermissionAPI.set} raises L{UknownUserError} if a username
        specified in the C{exceptions} list does not exist.
        """
        tag = createTag(self.user, self.user.namespace, u'tag')
        createTagPermission(tag)
        values = [(u'username/tag', Operation.DELETE_TAG,
                   Policy.OPEN, [u'unknown'])]
        error = self.assertRaises(UnknownUserError, self.permissions.set,
                                  values)
        self.assertEqual([u'unknown'], error.usernames)

    def testSetWithSuperuserInExceptions(self):
        """
        L{PermissionAPI.set} raises L{UserNotAllowedInExceptionError} if a
        superuser is given in one of the exceptions lists.
        """
        superuser = self.system.users['fluiddb']
        values = [(u'username', Operation.CREATE_NAMESPACE,
                   Policy.OPEN, [u'fluiddb'])]
        self.assertRaises(UserNotAllowedInExceptionError,
                          PermissionAPI(superuser).set, values)

    def testSetWithAnonymousUserAndForbiddenOperation(self):
        """
        L{PermissionAPI.set} raises L{UserNotAllowedInExceptionError} if an
        anonymous user is given in one of the exceptions list and the operation
        is forbidden for anonymous users.
        """
        anon = self.system.users[u'anon']
        values = [(u'username', Operation.CREATE_NAMESPACE,
                   Policy.OPEN, [u'anon'])]
        self.assertRaises(UserNotAllowedInExceptionError,
                          PermissionAPI(anon).set, values)

    def testSetWithAnonymousUserAndPermittedOperation(self):
        """
        L{PermissionAPI.set} updates existing permissions for the anonymous
        user if the operation is allowed for anonymous users.
        """
        anon = self.system.users[u'anon']
        values = [(u'username', Operation.LIST_NAMESPACE,
                   Policy.OPEN, [u'anon'])]
        PermissionAPI(anon).set(values)
        namespace, permission = getNamespacePermissions([u'username']).one()
        self.assertEqual(Policy.OPEN, permission.listPolicy)
        self.assertEqual([anon.id], permission.listExceptions)

    def testSetWithInvalidOperation(self):
        """
        L{PermissionAPI.set} raises a C{RuntimeError} if an invalid
        L{Operation} is used when storing values.
        """
        self.assertRaises(
            RuntimeError, self.permissions.set,
            [(u'username', Operation.CREATE_USER, Policy.OPEN, [])])

    def testGetWithoutDataRaisesFeatureError(self):
        """
        L{PermissionAPI.get} raises a L{FeatureError} if no values are
        provided.
        """
        self.assertRaises(FeatureError, self.permissions.get, [])

    def testGet(self):
        """
        L{PermissionAPI.get} returns a C{dict} of permissions for the
        specified path and L{Operation}.
        """
        tag = createTag(self.user, self.user.namespace, u'tag')
        createTagPermission(tag)
        action = (u'username/tag', Operation.UPDATE_TAG)
        permissions = self.permissions.get([action])
        self.assertEqual({action: (Policy.CLOSED, [u'username'])}, permissions)


class PermissionAPITest(PermissionAPITestMixin, FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(PermissionAPITest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = PermissionAPI(self.user)


class PermissionCheckerAPITestMixin(object):

    def testGetNamespacePermissions(self):
        """
        L{PermissionCheckerAPI.getNamespacePermissions} returns a C{dict}
        mapping requested L{Namespace.path}s to L{NamespacePermission}
        instances.
        """
        result = self.api.getNamespacePermissions([u'username'])
        permission = result[u'username']
        self.assertEqual(Policy.CLOSED, permission.createPolicy)
        self.assertEqual([self.user.id], permission.createExceptions)
        self.assertEqual(Policy.CLOSED, permission.updatePolicy)
        self.assertEqual([self.user.id], permission.updateExceptions)
        self.assertEqual(Policy.CLOSED, permission.deletePolicy)
        self.assertEqual([self.user.id], permission.deleteExceptions)
        self.assertEqual(Policy.OPEN, permission.listPolicy)
        self.assertEqual([], permission.listExceptions)
        self.assertEqual(Policy.CLOSED, permission.controlPolicy)
        self.assertEqual([self.user.id], permission.controlExceptions)

    def testGetUnknownNamespacePermissions(self):
        """
        L{PermissionCheckerAPI.getNamespacePermissions} ignores unknown
        L{Namespace.path}s.
        """
        self.assertEqual({}, self.api.getNamespacePermissions([u'unknown']))

    def testGetTagPermissions(self):
        """
        L{PermissionCheckerAPI.getTagPermissions} returns a C{dict} mapping
        requested L{Tag.path}s to L{TagPermission} instances.
        """
        TagAPI(self.user).create([(u'username/tag', u'A tag')])
        result = self.api.getTagPermissions([u'username/tag'])
        permission = result[u'username/tag']
        self.assertEqual(Policy.CLOSED, permission.updatePolicy)
        self.assertEqual([self.user.id], permission.updateExceptions)
        self.assertEqual(Policy.CLOSED, permission.deletePolicy)
        self.assertEqual([self.user.id], permission.deleteExceptions)
        self.assertEqual(Policy.CLOSED, permission.controlPolicy)
        self.assertEqual([self.user.id], permission.controlExceptions)
        self.assertEqual(Policy.CLOSED, permission.writeValuePolicy)
        self.assertEqual([self.user.id], permission.writeValueExceptions)
        self.assertEqual(Policy.OPEN, permission.readValuePolicy)
        self.assertEqual([], permission.readValueExceptions)
        self.assertEqual(Policy.CLOSED, permission.deleteValuePolicy)
        self.assertEqual([self.user.id], permission.deleteValueExceptions)
        self.assertEqual(Policy.CLOSED, permission.controlValuePolicy)
        self.assertEqual([self.user.id], permission.controlValueExceptions)

    def testGetUnknownTagPermissions(self):
        """
        L{PermissionCheckerAPI.getTagPermissions} ignores unknown
        L{Tag.path}s.
        """
        self.assertEqual({}, self.api.getTagPermissions([u'unknown']))

    def testGetUnknownNamespacePaths(self):
        """
        L{PermissionCheckerAPI.getUnknownPaths} returns a C{set} of unknown
        L{Namespace} paths.
        """
        values = [(u'unknown', Operation.CREATE_NAMESPACE)]
        self.assertEqual(set([u'unknown']), self.api.getUnknownPaths(values))

    def testGetUnknownTagPaths(self):
        """
        L{PermissionCheckerAPI.getUnknownPaths} returns a C{set} of unknown
        L{Tag} paths.
        """
        values = [(u'unknown/tag', Operation.UPDATE_TAG)]
        self.assertEqual(set([u'unknown/tag']),
                         self.api.getUnknownPaths(values))

    def testGetUnknownNamespaceAndTagPaths(self):
        """
        L{PermissionCheckerAPI.getUnknownPaths} returns a C{set} of unknown
        L{Namespace} and L{Tag} paths.
        """
        values = [(u'unknown', Operation.CREATE_NAMESPACE),
                  (u'unknown/tag', Operation.UPDATE_TAG)]
        self.assertEqual(set([u'unknown', u'unknown/tag']),
                         self.api.getUnknownPaths(values))

    def testGetUnknownPathsWithExistingPaths(self):
        """
        L{PermissionCheckerAPI.getUnknownPaths} returns an empty C{set} if the
        specified paths exist.
        """
        values = [(u'username', Operation.CREATE_NAMESPACE)]
        self.assertEqual(set(), self.api.getUnknownPaths(values))

    def testGetUnknownPathsIgnoresVirtualFluidDBSlashIDTag(self):
        """
        L{PermissionCheckerAPI.getUnknownPaths} always ignores the special
        virtual C{fluiddb/id} tag.
        """
        values = [(u'fluiddb/id', Operation.UPDATE_TAG)]
        self.assertEqual(set(), self.api.getUnknownPaths(values))

    def testGetUnknownPathsWithInvalidPath(self):
        """
        L{PermissionCheckerAPI.getUnknownPaths} raises a L{FeatureError} when
        an invalid path is provided.
        """
        self.assertRaises(FeatureError, self.api.getUnknownPaths,
                          [(None, Operation.UPDATE_TAG)])

    def testGetUnknownPathsWithInvalidOperation(self):
        """
        L{PermissionCheckerAPI.getUnknownPaths} raises a L{FeatureError} when
        an invalid L{Operation} is provided.
        """
        self.assertRaises(FeatureError, self.api.getUnknownPaths,
                          [(u'username', Operation.CREATE_OBJECT)])

    def testGetUnknownParentPathsWithoutUnknownPaths(self):
        """
        L{PermissionCheckerAPI.getUnknownParentPaths} is a no-op if no paths
        are provided.
        """
        self.assertEqual({}, self.api.getUnknownParentPaths(set()))

    def testGetUnknownParentPathsWithExistingPaths(self):
        """
        L{PermissionCheckerAPI.getUnknownParentPaths} is effectively a no-op
        if the provided paths exist.
        """
        values = set([u'username'])
        self.assertEqual({}, self.api.getUnknownParentPaths(values))

    def testGetUnkownParentPaths(self):
        """
        L{PermissionCheckerAPI.getUnknownParentPaths} returns a C{dict} that
        maps unknown paths to their closest existing L{Namespace} parent.
        """
        values = set([u'username/unknown/path'])
        self.assertEqual({u'username/unknown/path': u'username'},
                         self.api.getUnknownParentPaths(values))


class PermissionCheckerAPITest(PermissionCheckerAPITestMixin,
                               FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(PermissionCheckerAPITest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.api = PermissionCheckerAPI()
