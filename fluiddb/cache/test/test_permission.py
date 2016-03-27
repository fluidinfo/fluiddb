import json

from fluiddb.cache.permission import (
    CachingPermissionAPI, CachingPermissionCheckerAPI, PermissionCache)
from fluiddb.data.permission import (
    Operation, Policy, TagPermission, NamespacePermission, getTagPermissions)
from fluiddb.data.system import createSystemData
from fluiddb.model.tag import TagAPI
from fluiddb.model.test.test_permission import (
    PermissionAPITestMixin, PermissionCheckerAPITestMixin)
from fluiddb.model.user import UserAPI, getUser
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    BrokenCacheResource, CacheResource, ConfigResource, DatabaseResource,
    LoggingResource)


class CachingPermissionAPITestMixin(object):

    def testSetInvalidatesCachedNamespacePermissions(self):
        """
        L{CachingPermissionAPI.set} invalidates L{NamespacePermission}s to
        ensure the cache is always fresh.
        """
        cache = PermissionCache()
        cache.saveNamespacePermissions(
            {u'username': self.user.namespace.permission})
        self.permissions.set([
            (u'username', Operation.CREATE_NAMESPACE, Policy.OPEN, [])])
        cached = cache.getNamespacePermissions([u'username'])
        self.assertEqual({}, cached.results)
        self.assertEqual([u'username'], cached.uncachedValues)

    def testSetInvalidatesCachedTagPermissions(self):
        """
        L{CachingPermissionAPI.set} invalidates L{TagPermission}s to ensure
        the cache is always fresh.
        """
        TagAPI(self.user).create([(u'username/tag', u'A tag')])
        _, permission = getTagPermissions(paths=[u'username/tag']).one()
        cache = PermissionCache()
        cache.saveTagPermissions({u'username/tag': permission})
        self.permissions.set([
            (u'username/tag', Operation.UPDATE_TAG, Policy.OPEN, [])])
        cached = cache.getTagPermissions([u'username/tag'])
        self.assertEqual({}, cached.results)
        self.assertEqual([u'username/tag'], cached.uncachedValues)


class CachingPermissionAPITest(PermissionAPITestMixin,
                               CachingPermissionAPITestMixin,
                               FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(CachingPermissionAPITest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = CachingPermissionAPI(self.user)


class CachingPermissionAPIWithBrokenCacheTest(PermissionAPITestMixin,
                                              FluidinfoTestCase):

    resources = [('cache', BrokenCacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(CachingPermissionAPIWithBrokenCacheTest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = CachingPermissionAPI(self.user)


class CachingPermissionCheckerAPITest(PermissionCheckerAPITestMixin,
                                      FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(CachingPermissionCheckerAPITest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.api = CachingPermissionCheckerAPI()

    def testGetNamespacePermissionsCachesMisses(self):
        """
        L{CachingPermissionCheckerAPI.getNamespacePermissions} adds missing
        L{NamespacePermission}s to the cache.
        """
        result = self.api.getNamespacePermissions([u'username'])
        permission = result[u'username']
        self.assertTrue(isinstance(permission, NamespacePermission))

        # Go behind everyone's back and kill the NamespacePermission.
        self.store.find(NamespacePermission).remove()
        result = self.api.getNamespacePermissions([u'username'])
        permission = result[u'username']
        self.assertTrue(isinstance(permission, NamespacePermission))

    def testGetTagPermissionsCachesMisses(self):
        """
        L{CachingPermissionCheckerAPI.getTagPermissions} adds missing
        L{TagPermission}s to the cache.
        """
        TagAPI(self.user).create([(u'username/tag', u'A tag')])
        result = self.api.getTagPermissions([u'username/tag'])
        permission = result[u'username/tag']
        self.assertTrue(isinstance(permission, TagPermission))

        # Go behind everyone's back and kill the TagPermission.
        self.store.find(TagPermission).remove()
        result = self.api.getTagPermissions([u'username/tag'])
        permission = result[u'username/tag']
        self.assertTrue(isinstance(permission, TagPermission))


class PermissionCacheTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource(format='%(message)s'))]

    def setUp(self):
        super(PermissionCacheTest, self).setUp()
        self.permissionCache = PermissionCache()

    def setList(self, name, values):
        """Small helper method to put a C{list} in the cache."""
        for item in values:
            self.cache.rpush(name, item)

    def testGetTagPermissions(self):
        """
        L{PermissionCache.getTagPermissions} returns L{TagPermission}s stored
        in the cache.
        """
        permissionDict = {
            Operation.UPDATE_TAG.id: [Policy.OPEN.id, [1, 2, 3]],
            Operation.DELETE_TAG.id: [Policy.CLOSED.id, [4, 5, 6]],
            Operation.CONTROL_TAG.id: [Policy.OPEN.id, [7, 8, 9]],
            Operation.WRITE_TAG_VALUE.id: [Policy.CLOSED.id, [10, 11, 12]],
            Operation.READ_TAG_VALUE.id: [Policy.OPEN.id, [13, 14, 15]],
            Operation.DELETE_TAG_VALUE.id: [Policy.CLOSED.id, [16, 17, 18]],
            Operation.CONTROL_TAG_VALUE.id: [Policy.OPEN.id, [19, 20, 21]]
        }
        self.cache.set('permission:tag:test/tag1', json.dumps(permissionDict))

        permissionDict = {
            Operation.UPDATE_TAG.id: [Policy.CLOSED.id, [10, 15, 20]],
            Operation.DELETE_TAG.id: [Policy.OPEN.id, [25, 30, 35]],
            Operation.CONTROL_TAG.id: [Policy.CLOSED.id, [40, 45, 50]],
            Operation.WRITE_TAG_VALUE.id: [Policy.OPEN.id, [55, 60, 65]],
            Operation.READ_TAG_VALUE.id: [Policy.CLOSED.id, [70, 75, 80]],
            Operation.DELETE_TAG_VALUE.id: [Policy.OPEN.id, [85, 90, 95]],
            Operation.CONTROL_TAG_VALUE.id: [Policy.CLOSED.id, [100, 105, 110]]
        }
        self.cache.set('permission:tag:test/tag2', json.dumps(permissionDict))

        result = self.permissionCache.getTagPermissions([u'test/tag1',
                                                         u'test/tag2'])
        self.assertEqual([], result.uncachedValues)
        permission1 = result.results[u'test/tag1']
        self.assertEqual((Policy.OPEN, [1, 2, 3]),
                         permission1.get(Operation.UPDATE_TAG))
        self.assertEqual((Policy.CLOSED, [4, 5, 6]),
                         permission1.get(Operation.DELETE_TAG))
        self.assertEqual((Policy.OPEN, [7, 8, 9]),
                         permission1.get(Operation.CONTROL_TAG))
        self.assertEqual((Policy.CLOSED, [10, 11, 12]),
                         permission1.get(Operation.WRITE_TAG_VALUE))
        self.assertEqual((Policy.OPEN, [13, 14, 15]),
                         permission1.get(Operation.READ_TAG_VALUE))
        self.assertEqual((Policy.CLOSED, [16, 17, 18]),
                         permission1.get(Operation.DELETE_TAG_VALUE))
        self.assertEqual((Policy.OPEN, [19, 20, 21]),
                         permission1.get(Operation.CONTROL_TAG_VALUE))

        permission2 = result.results[u'test/tag2']
        self.assertEqual((Policy.CLOSED, [10, 15, 20]),
                         permission2.get(Operation.UPDATE_TAG))
        self.assertEqual((Policy.OPEN, [25, 30, 35]),
                         permission2.get(Operation.DELETE_TAG))
        self.assertEqual((Policy.CLOSED, [40, 45, 50]),
                         permission2.get(Operation.CONTROL_TAG))
        self.assertEqual((Policy.OPEN, [55, 60, 65]),
                         permission2.get(Operation.WRITE_TAG_VALUE))
        self.assertEqual((Policy.CLOSED, [70, 75, 80]),
                         permission2.get(Operation.READ_TAG_VALUE))
        self.assertEqual((Policy.OPEN, [85, 90, 95]),
                         permission2.get(Operation.DELETE_TAG_VALUE))
        self.assertEqual((Policy.CLOSED, [100, 105, 110]),
                         permission2.get(Operation.CONTROL_TAG_VALUE))

    def testGetTagPermissionsReturnsUncachedValues(self):
        """
        L{PermissionCache.getTagPermissions} returns the paths of
        L{TagPermission}s not found in the cache.
        """
        permissionDict = {
            Operation.UPDATE_TAG.id: [Policy.OPEN.id, [1, 2, 3]],
            Operation.DELETE_TAG.id: [Policy.CLOSED.id, [4, 5, 6]],
            Operation.CONTROL_TAG.id: [Policy.OPEN.id, [7, 8, 9]],
            Operation.WRITE_TAG_VALUE.id: [Policy.CLOSED.id, [10, 11, 12]],
            Operation.READ_TAG_VALUE.id: [Policy.OPEN.id, [13, 14, 15]],
            Operation.DELETE_TAG_VALUE.id: [Policy.CLOSED.id, [16, 17, 18]],
            Operation.CONTROL_TAG_VALUE.id: [Policy.OPEN.id, [19, 20, 21]]
        }
        self.cache.set('permission:tag:test/tag1', json.dumps(permissionDict))

        result = self.permissionCache.getTagPermissions([u'test/tag1',
                                                         u'test/tag2'])

        self.assertEqual([u'test/tag2'], result.uncachedValues)
        self.assertIn(u'test/tag1', result.results)

    def testGetTagPermissionsWithEmptyPaths(self):
        """
        L{PermissionCache.getTagPermissions} returns an empty L{CacheResult}
        if no paths are provided.
        """
        cached = self.permissionCache.getTagPermissions([])
        self.assertEqual({}, cached.results)
        self.assertEqual([], cached.uncachedValues)

    def testGetNamespacePermissions(self):
        """
        L{PermissionCache.getNamespacePermissions} returns
        L{NamespacePermission}s stored in the cache.
        """
        permissionDict = {
            Operation.CREATE_NAMESPACE.id: [Policy.OPEN.id, [1, 2, 3]],
            Operation.UPDATE_NAMESPACE.id: [Policy.CLOSED.id, [4, 5, 6]],
            Operation.DELETE_NAMESPACE.id: [Policy.OPEN.id, [7, 8, 9]],
            Operation.LIST_NAMESPACE.id: [Policy.CLOSED.id, [10, 11, 12]],
            Operation.CONTROL_NAMESPACE.id: [Policy.OPEN.id, [13, 14, 15]],
        }
        self.cache.set('permission:namespace:test/namespace1',
                       json.dumps(permissionDict))

        permissionDict = {
            Operation.CREATE_NAMESPACE.id: [Policy.CLOSED.id, [5, 10, 15]],
            Operation.UPDATE_NAMESPACE.id: [Policy.OPEN.id, [20, 25, 30]],
            Operation.DELETE_NAMESPACE.id: [Policy.CLOSED.id, [35, 40, 45]],
            Operation.LIST_NAMESPACE.id: [Policy.OPEN.id, [50, 55, 60]],
            Operation.CONTROL_NAMESPACE.id: [Policy.CLOSED.id, [65, 70, 75]],
        }
        self.cache.set('permission:namespace:test/namespace2',
                       json.dumps(permissionDict))

        result = self.permissionCache.getNamespacePermissions(
            [u'test/namespace1', u'test/namespace2'])

        permission1 = result.results[u'test/namespace1']

        self.assertEqual((Policy.OPEN, [1, 2, 3]),
                         permission1.get(Operation.CREATE_NAMESPACE))
        self.assertEqual((Policy.CLOSED, [4, 5, 6]),
                         permission1.get(Operation.UPDATE_NAMESPACE))
        self.assertEqual((Policy.OPEN, [7, 8, 9]),
                         permission1.get(Operation.DELETE_NAMESPACE))
        self.assertEqual((Policy.CLOSED, [10, 11, 12]),
                         permission1.get(Operation.LIST_NAMESPACE))
        self.assertEqual((Policy.OPEN, [13, 14, 15]),
                         permission1.get(Operation.CONTROL_NAMESPACE))

        permission2 = result.results[u'test/namespace2']
        self.assertEqual((Policy.CLOSED, [5, 10, 15]),
                         permission2.get(Operation.CREATE_NAMESPACE))
        self.assertEqual((Policy.OPEN, [20, 25, 30]),
                         permission2.get(Operation.UPDATE_NAMESPACE))
        self.assertEqual((Policy.CLOSED, [35, 40, 45]),
                         permission2.get(Operation.DELETE_NAMESPACE))
        self.assertEqual((Policy.OPEN, [50, 55, 60]),
                         permission2.get(Operation.LIST_NAMESPACE))
        self.assertEqual((Policy.CLOSED, [65, 70, 75]),
                         permission2.get(Operation.CONTROL_NAMESPACE))

    def testGetNamespacePermissionsReturnsUncachedValues(self):
        """
        L{PermissionCache.getNamespacePermissions} returns the paths of
        L{NamespacePermission}s not found in the cache.
        """
        permissionDict = {
            Operation.CREATE_NAMESPACE.id: [Policy.OPEN.id, [1, 2, 3]],
            Operation.UPDATE_NAMESPACE.id: [Policy.CLOSED.id, [4, 5, 6]],
            Operation.DELETE_NAMESPACE.id: [Policy.OPEN.id, [7, 8, 9]],
            Operation.LIST_NAMESPACE.id: [Policy.CLOSED.id, [10, 11, 12]],
            Operation.CONTROL_NAMESPACE.id: [Policy.OPEN.id, [13, 14, 15]],
        }
        self.cache.set('permission:namespace:test/namespace1',
                       json.dumps(permissionDict))

        result = self.permissionCache.getNamespacePermissions(
            [u'test/namespace1', u'test/namespace2'])

        self.assertEqual([u'test/namespace2'], result.uncachedValues)
        self.assertIn(u'test/namespace1', result.results)

    def testGetNamespacePermissionsWithEmptyPaths(self):
        """
        L{PermissionCache.getNamespacePermissions} returns an empty
        L{CacheResult} if no paths are provided.
        """
        cached = self.permissionCache.getNamespacePermissions([])
        self.assertEqual({}, cached.results)
        self.assertEqual([], cached.uncachedValues)

    def testClearTagPermissionsRemovesTagPermissions(self):
        """
        L{PermissionCache.clearTagPermissions} removes L{TagPermission}s from
        the cache, leaving L{NamespacePermission} for the same paths.
        """
        permissionDict = {
            Operation.UPDATE_TAG.id: [Policy.OPEN.id, [1, 2, 3]],
            Operation.DELETE_TAG.id: [Policy.CLOSED.id, [4, 5, 6]],
            Operation.CONTROL_TAG.id: [Policy.OPEN.id, [7, 8, 9]],
            Operation.WRITE_TAG_VALUE.id: [Policy.CLOSED.id, [10, 11, 12]],
            Operation.READ_TAG_VALUE.id: [Policy.OPEN.id, [13, 14, 15]],
            Operation.DELETE_TAG_VALUE.id: [Policy.CLOSED.id, [16, 17, 18]],
            Operation.CONTROL_TAG_VALUE.id: [Policy.OPEN.id, [19, 20, 21]]
        }
        self.cache.set('permission:tag:test/test', json.dumps(permissionDict))

        self.permissionCache.clearTagPermissions([u'test/test'])
        self.assertIdentical(None, self.cache.get('permission:tag:test/test'))

    def testClearNamespacePermissionsRemovesNamespacePermissions(self):
        """
        L{PermissionCache.clearNamespacePermissions} removes
        L{NamespacePermission}s from the cache, leaving L{TagPermission} for
        the same paths.
        """
        permissionDict = {
            Operation.CREATE_NAMESPACE.id: [Policy.OPEN.id, [1, 2, 3]],
            Operation.UPDATE_NAMESPACE.id: [Policy.CLOSED.id, [4, 5, 6]],
            Operation.DELETE_NAMESPACE.id: [Policy.OPEN.id, [7, 8, 9]],
            Operation.LIST_NAMESPACE.id: [Policy.CLOSED.id, [10, 11, 12]],
            Operation.CONTROL_NAMESPACE.id: [Policy.OPEN.id, [13, 14, 15]],
        }
        self.cache.set('permission:namespace:test/test',
                       json.dumps(permissionDict))

        self.permissionCache.clearNamespacePermissions([u'test/test'])
        self.assertIdentical(None,
                             self.cache.get('permission:namespace:test/test'))

    def testSaveTagPermissions(self):
        """
        L{PermissionCache.saveTagPermissions} store L{TagPermission}s in the
        cache.
        """
        permissions = {
            'test/tag1': TagPermission(userID=1, tagID=1),
            'test/tag2': TagPermission(userID=2, tagID=2)}

        self.permissionCache.saveTagPermissions(permissions)

        expected = {
            str(Operation.UPDATE_TAG.id): [False, [1]],
            str(Operation.DELETE_TAG.id): [False, [1]],
            str(Operation.CONTROL_TAG.id): [False, [1]],
            str(Operation.WRITE_TAG_VALUE.id): [False, [1]],
            str(Operation.READ_TAG_VALUE.id): [True, []],
            str(Operation.DELETE_TAG_VALUE.id): [False, [1]],
            str(Operation.CONTROL_TAG_VALUE.id): [False, [1]]
        }
        self.assertEqual(
            expected, json.loads(self.cache.get('permission:tag:test/tag1')))

        expected = {
            str(Operation.UPDATE_TAG.id): [False, [2]],
            str(Operation.DELETE_TAG.id): [False, [2]],
            str(Operation.CONTROL_TAG.id): [False, [2]],
            str(Operation.WRITE_TAG_VALUE.id): [False, [2]],
            str(Operation.READ_TAG_VALUE.id): [True, []],
            str(Operation.DELETE_TAG_VALUE.id): [False, [2]],
            str(Operation.CONTROL_TAG_VALUE.id): [False, [2]]
        }
        self.assertEqual(
            expected, json.loads(self.cache.get('permission:tag:test/tag2')))

    def testSaveNamespacePermissions(self):
        """
        L{PermissionCache.saveNamespacePermissions} store
        L{NamespacePermission}s in the cache.
        """
        permissions = {
            'test/ns1': NamespacePermission(userID=1, namespaceID=1),
            'test/ns2': NamespacePermission(userID=2, namespaceID=2)}

        self.permissionCache.saveNamespacePermissions(permissions)
        expected = {
            str(Operation.CREATE_NAMESPACE.id): [False, [1]],
            str(Operation.UPDATE_NAMESPACE.id): [False, [1]],
            str(Operation.DELETE_NAMESPACE.id): [False, [1]],
            str(Operation.LIST_NAMESPACE.id): [True, []],
            str(Operation.CONTROL_NAMESPACE.id): [False, [1]]
        }
        self.assertEqual(
            expected,
            json.loads(self.cache.get('permission:namespace:test/ns1')))

        expected = {
            str(Operation.CREATE_NAMESPACE.id): [False, [2]],
            str(Operation.UPDATE_NAMESPACE.id): [False, [2]],
            str(Operation.DELETE_NAMESPACE.id): [False, [2]],
            str(Operation.LIST_NAMESPACE.id): [True, []],
            str(Operation.CONTROL_NAMESPACE.id): [False, [2]]
        }
        self.assertEqual(
            expected,
            json.loads(self.cache.get('permission:namespace:test/ns2')))


class CachingPermissionCheckerAPIWithBrokenCacheTest(
        PermissionCheckerAPITestMixin, FluidinfoTestCase):

    resources = [('cache', BrokenCacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(CachingPermissionCheckerAPIWithBrokenCacheTest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.api = CachingPermissionCheckerAPI()
