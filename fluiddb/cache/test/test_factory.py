from fluiddb.data.system import createSystemData
from fluiddb.cache.factory import CachingAPIFactory
from fluiddb.cache.namespace import CachingNamespaceAPI
from fluiddb.cache.object import CachingObjectAPI
from fluiddb.cache.permission import (
    CachingPermissionAPI, CachingPermissionCheckerAPI)
from fluiddb.cache.recentactivity import CachingRecentActivityAPI
from fluiddb.cache.tag import CachingTagAPI
from fluiddb.cache.user import CachingUserAPI, cachingGetUser
from fluiddb.cache.value import CachingTagValueAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    CacheResource, ConfigResource, DatabaseResource)


class CachingAPIFactoryTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(CachingAPIFactoryTest, self).setUp()
        self.system = createSystemData()
        CachingUserAPI().create(
            [(u'user', u'secret', u'User', u'user@example.com')])
        self.user = cachingGetUser(u'user')
        self.factory = CachingAPIFactory()

    def testUsers(self):
        """
        L{CachingAPIFactory.users} returns a usable L{CachingUserAPI}
        instance.
        """
        self.assertIsInstance(self.factory.users(), CachingUserAPI)

    def testObjects(self):
        """
        L{CachingAPIFactory.objects} returns a usable L{CachingObjectAPI}
        instance.
        """
        self.assertIsInstance(self.factory.objects(self.user),
                              CachingObjectAPI)

    def testNamespaces(self):
        """
        L{CachingAPIFactory.namespaces} returns a usable
        L{CachingNamespaceAPI} instance.
        """
        self.assertIsInstance(self.factory.namespaces(self.user),
                              CachingNamespaceAPI)

    def testTags(self):
        """
        L{CachingAPIFactory.tags} returns a usable L{CachingTagAPI} instance.
        """
        self.assertIsInstance(self.factory.tags(self.user), CachingTagAPI)

    def testTagValues(self):
        """
        L{CachingAPIFactory.tagValues} returns a usable L{CachingTagValueAPI}
        instance.
        """
        self.assertIsInstance(self.factory.tagValues(self.user),
                              CachingTagValueAPI)

    def testPermissions(self):
        """
        L{CachingAPIFactory.permissions} returns a usable
        L{CachingPermissionAPI} instance.
        """
        self.assertIsInstance(self.factory.permissions(self.user),
                              CachingPermissionAPI)

    def testPermissionCheckers(self):
        """
        L{CachingAPIFactory.permissionCheckers} returns a usable
        L{CachingPermissionCheckerAPI} instance.
        """
        self.assertIsInstance(self.factory.permissionCheckers(),
                              CachingPermissionCheckerAPI)

    def testRecentActivity(self):
        """
        L{CachingAPIFactory.recentActivity} returns a usable
        L{CachingRecentActivityAPI} instance.
        """
        self.assertIsInstance(self.factory.recentActivity(),
                              CachingRecentActivityAPI)
