from datetime import datetime
from json import dumps, loads
from uuid import uuid4

from fluiddb.cache.object import CachingObjectAPI
from fluiddb.cache.recentactivity import (
    CachingRecentActivityAPI, RecentObjectActivityCache,
    RecentUserActivityCache)
from fluiddb.cache.value import CachingTagValueAPI
from fluiddb.data.system import createSystemData
from fluiddb.data.value import getTagValues
from fluiddb.model.test.test_recentactivity import RecentActivityAPITestMixin
from fluiddb.model.user import getUser, UserAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    BrokenCacheResource, CacheResource, ConfigResource, DatabaseResource,
    LoggingResource)
from fluiddb.model.tag import TagAPI


class CachingRecentActivityAPITestMixin(object):

    def getObjectAPI(self, user):
        """Get an L{CachingObjectAPI} instance for the specified user.

        @param user: The L{User} to configure the L{CachingObjectAPI}
            instance.
        @return: An L{CachingObjectAPI} instance.
        """
        return CachingObjectAPI(user)

    def getTagValueAPI(self, user):
        """Get a L{TagValueAPI} instance for the specified user.

        @param user: The L{User} to configure the L{TagValueAPI} instance.
        @return: A L{TagValueAPI} instance.
        """
        return CachingTagValueAPI(user)

    def testGetForObjectsUsesTheCache(self):
        """
        L{CachingRecentActivityAPI.getForObjects} attempts to fetch objects
        from the cache.
        """
        now = datetime.utcnow()
        objectID = uuid4()
        TagAPI(self.user).create([(u'user/tag', u'description')])
        activity = [(u'user/tag', str(objectID), u'about-value',
                     u'tag-value', u'user', now.isoformat())]
        self.cache.set(u'recentactivity:object:' + str(objectID),
                       dumps(activity))
        result = self.recentActivity.getForObjects([objectID])
        self.assertEqual([(u'user/tag', objectID, u'about-value',
                           u'tag-value', u'user', now)], result)

    def testGetForObjectsUpdatesTheCache(self):
        """
        L{CachingRecentActivityAPI.getForObjects} adds cache misses pulled
        from the database to the cache.
        """
        tagValues = self.getTagValueAPI(self.user)
        objectID = self.getObjectAPI(self.user).create(u'object')
        tagValues.set({objectID: {u'user/tag': u'A'}})

        databaseResult = self.recentActivity.getForObjects([objectID])

        # Remove all the tag values to ensure that the values for the next
        # request are taken from the cache.
        getTagValues().remove()
        cachedResult = self.recentActivity.getForObjects([objectID])
        self.assertEqual(databaseResult, cachedResult)

    def testGetForUsersUsesTheCache(self):
        """
        L{CachingRecentActivityAPI.getForUsers} attempts to fetch objects
        from the cache.
        """
        now = datetime.utcnow()
        objectID = uuid4()
        TagAPI(self.user).create([(u'user/tag', u'description')])
        activity = [(u'user/tag', str(objectID), u'about-value',
                     u'tag-value', u'user', now.isoformat())]
        self.cache.set(u'recentactivity:user:user', dumps(activity))

        result = self.recentActivity.getForUsers([u'user'])
        self.assertEqual([(u'user/tag', objectID, u'about-value',
                           u'tag-value', u'user', now)], result)

    def testGetForUsersUpdatesTheCache(self):
        """
        L{CachingRecentActivityAPI.getForUsers} adds cache misses pulled
        from the database to the cache.
        """
        tagValues = self.getTagValueAPI(self.user)
        objectID = self.getObjectAPI(self.user).create(u'object')
        tagValues.set({objectID: {u'user/tag': u'A'}})

        databaseResult = self.recentActivity.getForUsers([u'user'])

        # Remove all the tag values to ensure that the values for the next
        # request are taken from the cache.
        getTagValues().remove()
        cachedResult = self.recentActivity.getForUsers([u'user'])
        self.assertEqual(databaseResult, cachedResult)


class CachingRecentActivityAPITest(RecentActivityAPITestMixin,
                                   CachingRecentActivityAPITestMixin,
                                   FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(CachingRecentActivityAPITest, self).setUp()
        createSystemData()
        self.recentActivity = CachingRecentActivityAPI()
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        self.user = getUser(u'user')


class CachingRecentActivityAPIWithBrokenCacheTest(RecentActivityAPITestMixin,
                                                  FluidinfoTestCase):

    resources = [('cache', BrokenCacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(CachingRecentActivityAPIWithBrokenCacheTest, self).setUp()
        createSystemData()
        self.recentActivity = CachingRecentActivityAPI()
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        self.user = getUser(u'user')

    def getObjectAPI(self, user):
        """Get an L{CachingObjectAPI} instance for the specified user.

        @param user: The L{User} to configure the L{CachingObjectAPI}
            instance.
        @return: An L{CachingObjectAPI} instance.
        """
        return CachingObjectAPI(user)

    def getTagValueAPI(self, user):
        """Get a L{TagValueAPI} instance for the specified user.

        @param user: The L{User} to configure the L{TagValueAPI} instance.
        @return: A L{TagValueAPI} instance.
        """
        return CachingTagValueAPI(user)


class RecentObjectActivityCacheTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource(format='%(message)s'))]

    def testGetReturnsRecentActivityFromCache(self):
        """
        L{RecentObjectActivityCache.get} returns the recent activity saved in
        the cache.
        """
        now = datetime.utcnow()
        objectID = uuid4()
        activity = [(u'user/tag', str(objectID), u'about-value',
                     u'tag-value', u'user', now.isoformat())]
        self.cache.set(u'recentactivity:object:' + str(objectID),
                       dumps(activity))

        result = RecentObjectActivityCache().get(objectID)
        self.assertEqual({objectID: [(u'user/tag', objectID, u'about-value',
                                      u'tag-value', u'user', now)]},
                         result.results)
        self.assertEqual([], result.uncachedValues)

    def testGetReturnsUncachedValues(self):
        """
        L{RecentObjectActivityCache.get} returns values not found in the cache
        in the C{uncachedValues} field of the L{CacheResult} object.
        """
        objectID = uuid4()
        result = RecentObjectActivityCache().get(objectID)
        self.assertEqual([objectID], result.uncachedValues)
        self.assertEqual({}, result.results)

    def testSaveStoresRecentActivityInTheCache(self):
        """
        L{RecentObjectActivityCache.save} stores recent activity in the cache.
        """
        now = datetime.utcnow()
        objectID = uuid4()
        RecentObjectActivityCache().save(
            objectID, [(u'user/tag', objectID, u'about-value',
                        u'tag-value', u'user', now)])
        self.assertEqual(
            [[u'user/tag', str(objectID), u'about-value',
              u'tag-value', u'user', now.isoformat()]],
            loads(self.cache.get('recentactivity:object:' + str(objectID))))

    def testSaveSetsExpirationTimeout(self):
        """
        L{RecentObjectActivityCache.save} stores a result in the cache with
        the configured expiration timeout.
        """
        objectID = uuid4()
        RecentObjectActivityCache().save(
            objectID, [(u'user/tag', objectID, u'about-value',
                        u'tag-value', u'user', datetime.utcnow())])
        expectedTimeout = self.config.getint('cache', 'expire-timeout')
        ttl = self.cache.ttl('recentactivity:object:' + str(objectID))
        self.assertNotIdentical(None, ttl)
        self.assertAlmostEqual(expectedTimeout, ttl)

    def testClearUnknownObjectID(self):
        """
        L{RecentObjectActivityCache.clear} is a no-op if no data exists for
        the specified object ID.
        """
        objectID = uuid4()
        cache = RecentObjectActivityCache()
        cache.clear([objectID])
        result = cache.get(objectID)
        self.assertEqual({}, result.results)
        self.assertEqual([objectID], result.uncachedValues)

    def testClear(self):
        """
        L{RecentObjectActivityCache.clear} removes the cached recent activity
        for the specified object ID.
        """
        objectID = uuid4()
        cache = RecentObjectActivityCache()
        cache.save(objectID, [(u'user/tag', objectID, u'about-value',
                               u'tag-value', u'user', datetime.utcnow())])
        cache.clear([objectID])
        result = cache.get(objectID)
        self.assertEqual({}, result.results)
        self.assertEqual([objectID], result.uncachedValues)


class RecentUserActivityCacheTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource(format='%(message)s'))]

    def testGetReturnsRecentActivityFromCache(self):
        """
        L{RecentUserActivityCache.get} returns the recent activity saved in
        the cache.
        """
        now = datetime.utcnow()
        objectID = uuid4()
        activity = [(u'user/tag', str(objectID), u'about-value',
                     u'tag-value', u'user', now.isoformat())]
        self.cache.set(u'recentactivity:user:user', dumps(activity))

        result = RecentUserActivityCache().get(u'user')
        self.assertEqual({u'user': [(u'user/tag', objectID, u'about-value',
                                     u'tag-value', u'user', now)]},
                         result.results)
        self.assertEqual([], result.uncachedValues)

    def testGetReturnsUncachedValues(self):
        """
        L{RecentUserActivityCache.get} returns values not found in the cache
        in the C{uncachedValues} field of the L{CacheResult} object.
        """
        result = RecentUserActivityCache().get(u'user')
        self.assertEqual([u'user'], result.uncachedValues)
        self.assertEqual({}, result.results)

    def testSaveStoresRecentActivityInTheCache(self):
        """
        L{RecentUserActivityCache.save} stores recent activity in the cache.
        """
        now = datetime.utcnow()
        objectID = uuid4()
        RecentUserActivityCache().save(
            u'user', [(u'user/tag', objectID, u'about-value',
                       u'tag-value', u'user', now)])
        self.assertEqual(
            [[u'user/tag', str(objectID), u'about-value',
              u'tag-value', u'user', now.isoformat()]],
            loads(self.cache.get('recentactivity:user:user')))

    def testClearUnknownUser(self):
        """
        L{RecentUserActivityCache.clear} is a no-op if no data exists for the
        specified L{User}.
        """
        cache = RecentObjectActivityCache()
        cache.clear([u'username'])
        result = cache.get(u'username')
        self.assertEqual({}, result.results)
        self.assertEqual([u'username'], result.uncachedValues)

    def testClear(self):
        """
        L{RecentUserActivityCache.clear} removes the cached recent activity
        for the specified L{User}.
        """
        cache = RecentObjectActivityCache()
        cache.save(u'user', [(u'user/tag', u'user', u'about-value',
                              u'tag-value', u'user', datetime.utcnow())])
        cache.clear([u'user'])
        result = cache.get(u'user')
        self.assertEqual({}, result.results)
        self.assertEqual([u'user'], result.uncachedValues)
