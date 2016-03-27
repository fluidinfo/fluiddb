from datetime import datetime
from uuid import uuid4

from fluiddb.cache.permission import CachingPermissionAPI
from fluiddb.cache.recentactivity import (
    RecentObjectActivityCache, RecentUserActivityCache)
from fluiddb.cache.tag import CachingTagAPI
from fluiddb.cache.value import CachingTagValueAPI
from fluiddb.data.system import createSystemData
from fluiddb.model.test.test_value import TagValueAPITestMixin
from fluiddb.model.user import UserAPI, getUser
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    BrokenCacheResource, CacheResource, ConfigResource, DatabaseResource,
    LoggingResource)


class CachingTagValueAPITestMixin(object):

    def testSetInvalidatesRecentObjectActivity(self):
        """
        L{CachingTagValueAPI.set} invalidates cached recent activity data for
        the object IDs that have been modified.
        """
        objectID = uuid4()
        CachingTagAPI(self.user).create([(u'username/tag', u'A tag')])
        cache = RecentObjectActivityCache()
        cache.save(objectID, [(u'username/tag', objectID, u'about-value',
                               u'tag-value', u'username', datetime.utcnow())])
        self.tagValues.set({objectID: {u'username/tag': 42}})
        result = cache.get(objectID)
        self.assertEqual({}, result.results)
        self.assertEqual([objectID], result.uncachedValues)

    def testSetInvalidatesRecentUserActivity(self):
        """
        L{CachingTagValueAPI.set} invalidates cached recent activity data for
        the L{User} that's modified data.
        """
        objectID = uuid4()
        CachingTagAPI(self.user).create([(u'username/tag', u'A tag')])
        cache = RecentUserActivityCache()
        cache.save(
            u'username', [(u'username/tag', objectID, u'about-value',
                           u'tag-value', u'username', datetime.utcnow())])
        self.tagValues.set({objectID: {u'username/tag': 42}})
        result = cache.get(u'username')
        self.assertEqual({}, result.results)
        self.assertEqual([u'username'], result.uncachedValues)

    def testDeleteInvalidatesRecentObjectActivity(self):
        """
        L{CachingTagValueAPI.delete} invalidates cache recent activity for the
        object IDs that have been modified.
        """
        objectID = uuid4()
        CachingTagAPI(self.user).create([(u'username/tag', u'A tag')])
        cache = RecentObjectActivityCache()
        cache.save(objectID, [(u'username/tag', objectID, u'about-value',
                               u'tag-value', u'username', datetime.utcnow())])
        self.tagValues.delete([(objectID, u'username/tag')])
        result = cache.get(objectID)
        self.assertEqual({}, result.results)
        self.assertEqual([objectID], result.uncachedValues)

    def testDeleteInvalidatesRecentUserActivity(self):
        """
        L{CachingTagValueAPI.delete} invalidates cached recent activity data
        for the L{User} that's removed data.
        """
        objectID = uuid4()
        CachingTagAPI(self.user).create([(u'username/tag', u'A tag')])
        cache = RecentUserActivityCache()
        cache.save(
            u'username', [(u'username/tag', objectID, u'about-value',
                           u'tag-value', u'username', datetime.utcnow())])
        self.tagValues.delete([(objectID, u'username/tag')])
        result = cache.get(u'username')
        self.assertEqual({}, result.results)
        self.assertEqual([u'username'], result.uncachedValues)


class CachingTagValueAPITest(TagValueAPITestMixin, CachingTagValueAPITestMixin,
                             FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(CachingTagValueAPITest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = CachingPermissionAPI(self.user)
        self.tagValues = CachingTagValueAPI(self.user)


class CachingTagValueAPIWithBrokenCacheTest(TagValueAPITestMixin,
                                            FluidinfoTestCase):

    resources = [('cache', BrokenCacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(CachingTagValueAPIWithBrokenCacheTest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = CachingPermissionAPI(self.user)
        self.tagValues = CachingTagValueAPI(self.user)
