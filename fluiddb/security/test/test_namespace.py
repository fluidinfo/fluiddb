from fluiddb.cache.permission import CachingPermissionAPI
from fluiddb.cache.test.test_namespace import CachingNamespaceAPITestMixin
from fluiddb.data.permission import Operation, Policy
from fluiddb.data.system import createSystemData
from fluiddb.model.exceptions import UnknownPathError
from fluiddb.model.test.test_namespace import NamespaceAPITestMixin
from fluiddb.model.user import UserAPI, getUser
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.security.namespace import SecureNamespaceAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    BrokenCacheResource, CacheResource, ConfigResource, DatabaseResource,
    LoggingResource)


class SecureNamespaceAPITestMixin(object):

    def testCreateWithUnknownParent(self):
        """
        L{SecureNamespaceAPI.create} raises an L{UnknownPathError} exception if
        an attempt to create a L{Namespace} with an unknown parent is made.
        """
        values = [(u'unknown/namespace', u'An unknown namespace.')]
        error = self.assertRaises(UnknownPathError,
                                  self.namespaces.create, values)
        self.assertEqual([u'unknown'], error.paths)

    def testDeleteWithUnknownPath(self):
        """
        L{SecureNamespaceAPI.delete} raises an L{UnknownPathError} if a path
        for an unknown L{Namespace} is specified.
        """
        error = self.assertRaises(UnknownPathError,
                                  self.namespaces.delete,
                                  [u'unknown/namespace'])
        self.assertEqual([u'unknown/namespace'], error.paths)

    def testSetWithUnknownPath(self):
        """
        L{SecureNamespaceAPI.set} raises an L{UnknownPathError} if a path for
        an unknown L{Namespace} is specified.
        """
        values = {u'unknown/namespace': u'An unknown namespace.'}
        error = self.assertRaises(UnknownPathError,
                                  self.namespaces.set, values)
        self.assertEqual([u'unknown/namespace'], error.paths)


class SecureNamespaceAPITest(NamespaceAPITestMixin,
                             CachingNamespaceAPITestMixin,
                             SecureNamespaceAPITestMixin,
                             FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureNamespaceAPITest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.namespaces = SecureNamespaceAPI(self.user)
        self.permissions = CachingPermissionAPI(self.user)


class SecureNamespaceAPIWithBrokenCacheTest(NamespaceAPITestMixin,
                                            SecureNamespaceAPITestMixin,
                                            FluidinfoTestCase):

    resources = [('cache', BrokenCacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureNamespaceAPIWithBrokenCacheTest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.namespaces = SecureNamespaceAPI(self.user)
        self.permissions = CachingPermissionAPI(self.user)


class SecureNamespaceAPIWithAnonymousRoleTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureNamespaceAPIWithAnonymousRoleTest, self).setUp()
        self.system = createSystemData()
        self.user = self.system.users[u'anon']
        self.namespaces = SecureNamespaceAPI(self.user)

    def testCreateIsDenied(self):
        """
        L{SecureNamespaceAPI.create} raises a L{PermissionDeniedError} if its
        invoked by a L{User} with the L{Role.ANONYMOUS}.
        """
        error = self.assertRaises(PermissionDeniedError,
                                  self.namespaces.create,
                                  [(u'anon/test', u'description')])
        self.assertEqual(self.user.username, error.username)
        self.assertEqual([(u'anon', Operation.CREATE_NAMESPACE)],
                         sorted(error.pathsAndOperations))

    def testDeleteIsDenied(self):
        """
        L{SecureNamespaceAPI.delete} raises a L{PermissionDeniedError} if its
        invoked by a L{User} with the L{Role.ANONYMOUS}.
        """
        error = self.assertRaises(PermissionDeniedError,
                                  self.namespaces.delete,
                                  [u'anon'])
        self.assertEqual(self.user.username, error.username)
        self.assertEqual([(u'anon', Operation.DELETE_NAMESPACE)],
                         sorted(error.pathsAndOperations))

    def testSetIsDenied(self):
        """
        L{SecureNamespaceAPI.set} raises a L{PermissionDeniedError} if its
        invoked by a L{User} with the L{Role.ANONYMOUS}.
        """
        error = self.assertRaises(PermissionDeniedError,
                                  self.namespaces.set,
                                  {u'anon': u'new description'})
        self.assertEqual(self.user.username, error.username)
        self.assertEqual([(u'anon', Operation.UPDATE_NAMESPACE)],
                         sorted(error.pathsAndOperations))

    def testGetChildNamespacesIsAllowed(self):
        """
        L{SecureNamespaceAPI.get} should allow getting a list of child
        namespaces if the I{anon} user has permissions.
        """
        admin = self.system.users[u'fluiddb']
        SecureNamespaceAPI(admin).create([(u'fluiddb/test', u'description')])
        values = [(u'fluiddb', Operation.LIST_NAMESPACE, Policy.OPEN, [])]
        CachingPermissionAPI(admin).set(values)
        result = self.namespaces.get([u'fluiddb'], withNamespaces=True)
        self.assertEqual(1, len(result))

    def testGetChildNamespacesIsDenied(self):
        """
        L{SecureNamespaceAPI.get} should raise L{PermissonDeniedError} if the
        I{anon} user doesn't have LIST permissions when trying to get the child
        namespaces.
        """
        admin = self.system.users[u'fluiddb']
        SecureNamespaceAPI(admin).create([(u'fluiddb/test', u'description')])
        values = [(u'fluiddb', Operation.LIST_NAMESPACE, Policy.CLOSED, [])]
        CachingPermissionAPI(admin).set(values)
        error = self.assertRaises(PermissionDeniedError,
                                  self.namespaces.get,
                                  [(u'fluiddb')], withNamespaces=True)
        self.assertEqual([(u'fluiddb', Operation.LIST_NAMESPACE)],
                         sorted(error.pathsAndOperations))

    def testGetChildTagsIsAllowed(self):
        """
        L{SecureNamespaceAPI.get} should allow getting a list of child tags if
        the I{anon} user has permissions.
        """
        admin = self.system.users[u'fluiddb']
        SecureNamespaceAPI(admin).create([(u'fluiddb/test', u'description')])
        values = [(u'fluiddb', Operation.LIST_NAMESPACE,
                   Policy.CLOSED, [u'anon'])]
        CachingPermissionAPI(admin).set(values)
        result = self.namespaces.get([u'fluiddb'], withTags=True)
        self.assertEqual(1, len(result))

    def testGetChildTagsIsDenied(self):
        """
        L{SecureNamespaceAPI.get} should raise L{PermissonDeniedError} if the
        L{anon} user doesn't have LIST permissions when trying to get the
        child tags.
        """
        admin = self.system.users[u'fluiddb']
        SecureNamespaceAPI(admin).create([(u'fluiddb/test', u'description')])
        values = [(u'fluiddb', Operation.LIST_NAMESPACE,
                   Policy.OPEN, [u'anon'])]
        CachingPermissionAPI(admin).set(values)
        error = self.assertRaises(PermissionDeniedError,
                                  self.namespaces.get,
                                  [(u'fluiddb')], withTags=True)
        self.assertEqual([(u'fluiddb', Operation.LIST_NAMESPACE)],
                         sorted(error.pathsAndOperations))


class SecureNamespaceAPIWithNormalUserTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureNamespaceAPIWithNormalUserTest, self).setUp()
        createSystemData()

        UserAPI().create([(u'user', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'user')
        self.permissions = CachingPermissionAPI(self.user)
        self.namespaces = SecureNamespaceAPI(self.user)

    def testCreateIsAllowed(self):
        """
        L{SecureNamespaceAPI.create} should allow the creation of namespaces
        whose parent has open CREATE permissions.
        """
        values = [(u'user', Operation.CREATE_NAMESPACE, Policy.OPEN, [])]
        self.permissions.set(values)
        result = self.namespaces.create([(u'user/test', u'description')])
        self.assertEqual(1, len(result))

    def testCreateIsDenied(self):
        """
        L{SecureNamespaceAPI.create} should raise L{PermissonDeniedError} if
        the user doesn't have CREATE permissions on the parent namespace.
        """
        values = [(u'user', Operation.CREATE_NAMESPACE, Policy.CLOSED, [])]
        self.permissions.set(values)
        error = self.assertRaises(PermissionDeniedError,
                                  self.namespaces.create,
                                  [(u'user/test', u'description')])
        self.assertEqual([(u'user', Operation.CREATE_NAMESPACE)],
                         sorted(error.pathsAndOperations))

    def testDeleteIsAllowed(self):
        """
        {SecureNamespaceAPI.delete} should allow the deletion of a namespace
        if the user has DELETE permissions.
        """
        result1 = self.namespaces.create([(u'user/test', u'description')])
        values = [(u'user/test', Operation.DELETE_NAMESPACE, Policy.OPEN, [])]
        self.permissions.set(values)
        result2 = self.namespaces.delete([u'user/test'])
        self.assertEqual(result1, result2)

    def testDeleteIsDenied(self):
        """
        L{SecureNamespaceAPI.delete} should raise L{PermissonDeniedError} if
        the user doesn't have DELETE permissions.
        """
        self.namespaces.create([(u'user/test', u'description')])
        values = [(u'user/test', Operation.DELETE_NAMESPACE,
                   Policy.OPEN, [u'user'])]
        self.permissions.set(values)
        error = self.assertRaises(PermissionDeniedError,
                                  self.namespaces.delete, [(u'user/test')])
        self.assertEqual([(u'user/test', Operation.DELETE_NAMESPACE)],
                         sorted(error.pathsAndOperations))

    def testGetChildNamespacesIsAllowed(self):
        """
        L{SecureNamespaceAPI.get} should allow getting a list of child
        namespaces if the user has permissions.
        """
        self.namespaces.create([(u'user/test', u'description')])
        values = [(u'user', Operation.LIST_NAMESPACE, Policy.OPEN, [])]
        self.permissions.set(values)
        result = self.namespaces.get([u'user'], withNamespaces=True)
        self.assertEqual(1, len(result))

    def testGetChildNamespacesIsDenied(self):
        """
        L{SecureNamespaceAPI.get} should raise L{PermissonDeniedError} if the
        user doesn't have LIST permissions when trying to get the child
        namespaces.
        """
        self.namespaces.create([(u'user/test', u'description')])
        values = [(u'user', Operation.LIST_NAMESPACE, Policy.CLOSED, [])]
        self.permissions.set(values)
        error = self.assertRaises(PermissionDeniedError,
                                  self.namespaces.get,
                                  [(u'user')], withNamespaces=True)
        self.assertEqual([(u'user', Operation.LIST_NAMESPACE)],
                         sorted(error.pathsAndOperations))

    def testGetChildTagsIsAllowed(self):
        """
        L{SecureNamespaceAPI.get} should allow getting a list of child tags if
        the user has permissions.
        """
        self.namespaces.create([(u'user/test', u'description')])
        values = [(u'user', Operation.LIST_NAMESPACE,
                   Policy.CLOSED, [u'user'])]
        self.permissions.set(values)
        result = self.namespaces.get([u'user'], withTags=True)
        self.assertEqual(1, len(result))

    def testGetChildTagsIsDenied(self):
        """
        L{SecureNamespaceAPI.get} should raise L{PermissonDeniedError} if the
        user doesn't have LIST permissions when trying to get the child
        tags.
        """
        self.namespaces.create([(u'user/test', u'description')])
        values = [(u'user', Operation.LIST_NAMESPACE, Policy.OPEN, [u'user'])]
        self.permissions.set(values)
        error = self.assertRaises(PermissionDeniedError,
                                  self.namespaces.get,
                                  [(u'user')], withTags=True)
        self.assertEqual([(u'user', Operation.LIST_NAMESPACE)],
                         sorted(error.pathsAndOperations))

    def testSetIsAllowed(self):
        """
        L{SecureNamespaceAPI.get} should allow updating the description of a
        namespace if the user has permissions.
        """
        self.namespaces.create([(u'user/test', u'description')])
        values = [(u'user/test', Operation.UPDATE_NAMESPACE, Policy.OPEN, [])]
        self.permissions.set(values)
        self.namespaces.set({u'user/test': u'description'})

    def testSetIsDenied(self):
        """
        L{SecureNamespaceAPI.get} should raise L{PermissonDeniedError} if the
        user doesn't have UPDATE permissions when trying to update a
        namespace's description.
        """
        self.namespaces.create([(u'user/test', u'description')])
        values = [(u'user/test', Operation.UPDATE_NAMESPACE,
                   Policy.CLOSED, [])]
        self.permissions.set(values)
        error = self.assertRaises(PermissionDeniedError,
                                  self.namespaces.set,
                                  {u'user/test': u'description'})
        self.assertEqual([(u'user/test', Operation.UPDATE_NAMESPACE)],
                         sorted(error.pathsAndOperations))


class SecureNamespaceAPIWithSuperuserTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureNamespaceAPIWithSuperuserTest, self).setUp()
        system = createSystemData()
        user = system.users[u'fluiddb']
        self.namespaces = SecureNamespaceAPI(user)
        self.permissions = CachingPermissionAPI(user)

    def testCreateIsAllowed(self):
        """
        Creating a new L{Namespace} should be allowed if we're a user with a
        L{Role.SUPERUSER} no matter what permissions we have.
        """
        values = [(u'fluiddb', Operation.CREATE_NAMESPACE, Policy.CLOSED, [])]
        self.permissions.set(values)
        result = self.namespaces.create([(u'fluiddb/test', u'description')])
        self.assertEqual(1, len(result))

    def testDeleteIsAllowed(self):
        """
        Deleting a L{Namespace} should be allowed if we're a user with a
        L{Role.SUPERUSER} no matter what permissions we have.
        """
        result1 = self.namespaces.create([(u'fluiddb/test', u'description')])
        values = [(u'fluiddb/test', Operation.DELETE_NAMESPACE,
                   Policy.CLOSED, [])]
        self.permissions.set(values)
        result2 = self.namespaces.delete([u'fluiddb/test'])
        self.assertEqual(result1, result2)

    def testSetIsAllowed(self):
        """
        Updating a L{Namespace} should be allowed if we're a user with a
        L{Role.SUPERUSER} no matter what permissions we have.
        """
        self.namespaces.create([(u'fluiddb/test', u'description')])
        values = [(u'fluiddb/test', Operation.UPDATE_NAMESPACE,
                   Policy.CLOSED, [])]
        self.permissions.set(values)
        self.namespaces.set({u'fluiddb/test': u'new description'})

    def testGetIsAllowed(self):
        """
        Getting information about a L{Namespace} should be allowed if we're a
        user with a L{Role.SUPERUSER} no matter what permissions we have.
        """
        self.namespaces.create([(u'fluiddb/test', u'description')])
        values = [(u'fluiddb/test', Operation.LIST_NAMESPACE,
                   Policy.CLOSED, [])]
        self.permissions.set(values)
        result = self.namespaces.get([u'fluiddb'], withDescriptions=False,
                                     withTags=True, withNamespaces=True)
        self.assertEqual(1, len(result))
