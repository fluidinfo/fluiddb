from uuid import uuid4

from twisted.internet.defer import inlineCallbacks

from fluiddb.cache.object import CachingObjectAPI, ObjectCache
from fluiddb.data.system import createSystemData
from fluiddb.data.value import createAboutTagValue, getAboutTagValues
from fluiddb.model.test.test_object import ObjectAPITestMixin
from fluiddb.model.user import UserAPI, getUser
from fluiddb.query.parser import parseQuery
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    BrokenCacheResource, CacheResource, ConfigResource, DatabaseResource,
    IndexResource, LoggingResource)


class CachingObjectAPITestMixin(object):

    def testGetUsesTheCache(self):
        """
        L{ObjectAPI.get} returns a C{dict} that maps L{AboutTagValue.value}s
        to object IDs.
        """
        objectID = uuid4()
        aboutValue = createAboutTagValue(objectID, u'Hello world!')

        # The first time the value is fetched from the DB.
        self.assertEqual({u'Hello world!': objectID},
                         self.objects.get([u'Hello world!']))

        # Change the value without updating the cache.
        aboutValue.value = u'Different'

        # Check the object is not in the Data Base anymore.
        result = getAboutTagValues(values=[u'Hello world!'])
        self.assertIdentical(None, result.one())

        # Check the value is fetched from the cache this time.
        self.assertEqual({u'Hello world!': objectID},
                         self.objects.get([u'Hello world!']))

    @inlineCallbacks
    def testSearchAboutValueUsesTheCache(self):
        """
        L{ObjectAPI.search} uses the cache to get the results of
        C{fluiddb/about = "..."} queries if they're available.
        """
        objectID = self.objects.create(u'about')
        query = parseQuery('fluiddb/about = "about"')
        # Get the value once to store it in the cache.
        self.objects.search([query])

        # Remove the value from the store to check that we're using the cache.
        getAboutTagValues(values=[u'about']).remove()
        result = self.objects.search([query])
        result = yield result.get()
        self.assertEqual({query: set([objectID])}, result)


class CachingObjectAPITest(ObjectAPITestMixin, CachingObjectAPITestMixin,
                           FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('client', IndexResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(CachingObjectAPITest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'user', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'user')
        self.objects = CachingObjectAPI(self.user)


class CachingObjectAPIWithBrokenCacheTest(ObjectAPITestMixin,
                                          FluidinfoTestCase):

    resources = [('cache', BrokenCacheResource()),
                 ('client', IndexResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(CachingObjectAPIWithBrokenCacheTest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'user', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'user')
        self.objects = CachingObjectAPI(self.user)


class ObjectCacheTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource(format='%(message)s'))]

    def setUp(self):
        super(ObjectCacheTest, self).setUp()
        self.objectCache = ObjectCache()

    def testGetReturnsObjectsInCache(self):
        """L{ObjectCache.get} returns the objectIDs saved in the cache."""
        objectID1 = uuid4()
        objectID2 = uuid4()
        self.cache.set(u'about:about1', str(objectID1))
        self.cache.set(u'about:about2', str(objectID2))
        result = self.objectCache.get([u'about1', u'about2'])
        expected = {u'about1': objectID1,
                    u'about2': objectID2}
        self.assertEqual(expected, result.results)
        self.assertEqual([], result.uncachedValues)

    def testGetReturnsUncachedValues(self):
        """
        L{ObjectCache.get} returns values not found in the cache in the
        C{uncachedValues} field of the L{CacheResult} object.
        """
        objectID1 = uuid4()
        self.cache.set(u'about:about1', str(objectID1))
        result = self.objectCache.get([u'about1', u'about2', u'about3'])
        self.assertEqual({u'about1': objectID1}, result.results)
        self.assertEqual([u'about2', u'about3'], result.uncachedValues)

    def testGetWithUnicodeAboutValue(self):
        """
        L{ObjectCache.get} correctly get objectIDs with unicode about values.
        """
        objectID1 = uuid4()
        self.cache.set(u'about:\N{HIRAGANA LETTER A}', str(objectID1))
        result = self.objectCache.get([u'\N{HIRAGANA LETTER A}'])
        self.assertEqual({u'\N{HIRAGANA LETTER A}': objectID1}, result.results)
        self.assertEqual([], result.uncachedValues)

    def testSaveStoresValuesInTheCache(self):
        """L{ObjectCache.save} stores a result in the cache."""
        objectID1 = uuid4()
        objectID2 = uuid4()
        self.objectCache.save({u'about1': objectID1,
                               u'about2': objectID2})
        self.assertEqual(str(objectID1), self.cache.get('about:about1'))
        self.assertEqual(str(objectID2), self.cache.get('about:about2'))
