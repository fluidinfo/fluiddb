from fluiddb.cache.namespace import CachingNamespaceAPI
from fluiddb.cache.permission import CachingPermissionAPI, PermissionCache
from fluiddb.data.namespace import getNamespaces
from fluiddb.data.system import createSystemData
from fluiddb.model.test.test_namespace import NamespaceAPITestMixin
from fluiddb.model.user import UserAPI, getUser
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    BrokenCacheResource, CacheResource, ConfigResource, DatabaseResource,
    LoggingResource)


class CachingNamespaceAPITestMixin(object):

    def testDeleteInvalidatesCachedNamespacePermissions(self):
        """
        L{CachingNamespaceAPI.delete} invalidates L{NamespacePermission}s to
        ensure the cache is always fresh.
        """
        self.namespaces.create([(u'username/namespace', u'A namespace')])
        namespace = getNamespaces(paths=[u'username/namespace']).one()
        cache = PermissionCache()
        cache.saveNamespacePermissions(
            {u'username/namespace': namespace.permission})

        self.namespaces.delete([u'username/namespace'])
        cached = cache.getNamespacePermissions([u'username/namespace'])
        self.assertEqual({}, cached.results)
        self.assertEqual([u'username/namespace'], cached.uncachedValues)


class CachingNamespaceAPITest(NamespaceAPITestMixin,
                              CachingNamespaceAPITestMixin, FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(CachingNamespaceAPITest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.namespaces = CachingNamespaceAPI(self.user)
        self.permissions = CachingPermissionAPI(self.user)


class CachingNamespaceAPIWithBrokenCacheTest(NamespaceAPITestMixin,
                                             FluidinfoTestCase):

    resources = [('cache', BrokenCacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(CachingNamespaceAPIWithBrokenCacheTest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.namespaces = CachingNamespaceAPI(self.user)
        self.permissions = CachingPermissionAPI(self.user)
