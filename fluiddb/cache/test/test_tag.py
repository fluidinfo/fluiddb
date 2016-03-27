from uuid import uuid4

from fluiddb.cache.permission import CachingPermissionAPI, PermissionCache
from fluiddb.cache.recentactivity import (
    CachingRecentActivityAPI, RecentObjectActivityCache,
    RecentUserActivityCache)
from fluiddb.cache.tag import CachingTagAPI
from fluiddb.cache.value import CachingTagValueAPI
from fluiddb.data.system import createSystemData
from fluiddb.data.tag import getTags
from fluiddb.model.test.test_tag import TagAPITestMixin
from fluiddb.model.user import UserAPI, getUser
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    BrokenCacheResource, CacheResource, ConfigResource, DatabaseResource,
    LoggingResource)


class CachingTagAPITestMixin(object):

    def testDeleteInvalidatesCachedTagPermissions(self):
        """
        L{CachingTagAPI.delete} invalidates L{TagPermission}s to ensure the
        cache is always fresh.
        """
        self.tags.create([(u'username/tag', u'A tag')])
        tag = getTags(paths=[u'username/tag']).one()
        cache = PermissionCache()
        cache.saveTagPermissions({u'username/tag': tag.permission})

        self.tags.delete([u'username/tag'])
        cached = cache.getTagPermissions([u'username/tag'])
        self.assertEqual({}, cached.results)
        self.assertEqual([u'username/tag'], cached.uncachedValues)

    def testDeleteInvalidatesCachedRecentObjectActivity(self):
        """
        L{CachingTagAPI.delete} invalidates recent activity for objects that
        had a L{TagValue} associated with the removed L{Tag}.
        """
        objectID = uuid4()
        self.tags.create([(u'username/tag', u'A tag')])
        CachingTagValueAPI(self.user).set({objectID: {u'username/tag': 42}})
        CachingRecentActivityAPI().getForObjects([objectID])
        self.tags.delete([u'username/tag'])
        result = RecentObjectActivityCache().get(objectID)
        self.assertEqual({}, result.results)
        self.assertEqual([objectID], result.uncachedValues)

    def testDeleteInvalidatesCachedRecentUserActivity(self):
        """
        L{CachingTagAPI.delete} invalidates recent activity for L{User}s that
        had a L{TagValue} associated with the removed L{Tag}.
        """
        objectID = uuid4()
        self.tags.create([(u'username/tag', u'A tag')])
        CachingTagValueAPI(self.user).set({objectID: {u'username/tag': 42}})
        CachingRecentActivityAPI().getForUsers([u'username'])
        self.tags.delete([u'username/tag'])
        result = RecentUserActivityCache().get(u'username')
        self.assertEqual({}, result.results)
        self.assertEqual(['username'], result.uncachedValues)


class CachingTagAPITest(TagAPITestMixin, CachingTagAPITestMixin,
                        FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(CachingTagAPITest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.tags = CachingTagAPI(self.user)
        self.permissions = CachingPermissionAPI(self.user)


class CachingTagAPIWithBrokenCacheTest(TagAPITestMixin, FluidinfoTestCase):

    resources = [('cache', BrokenCacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(CachingTagAPIWithBrokenCacheTest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.tags = CachingTagAPI(self.user)
        self.permissions = CachingPermissionAPI(self.user)
