from redis import Redis, ConnectionPool

from fluiddb.application import getCacheConnectionPool
from fluiddb.cache.cache import getCacheClient, BaseCache
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import CacheResource, ConfigResource,\
    LoggingResource


class GetCacheClientTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource())]

    def testGetCacheClient(self):
        """
        L{getCacheClient} returns a configured L{Redis} client that is ready to
        use.
        """
        client = getCacheClient()
        self.assertIsInstance(client, Redis)

    def testGetCacheClientUsesGlobalConnectionPool(self):
        """
        L{getCacheClient} returns a L{Redis} client that uses the global
        connection pool.
        """
        client = getCacheClient()
        connectionPool = getCacheConnectionPool()
        self.assertIdentical(client.connection_pool, connectionPool)

    def testGetCacheClientsUseTheSameConnectionPool(self):
        """
        L{getCacheClient} returns a L{Redis} client that uses the global
        connection pool.
        """
        client1 = getCacheClient()
        client2 = getCacheClient()
        self.assertIdentical(client1.connection_pool, client2.connection_pool)


class BaseCacheTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource(format='%(message)s'))]

    def testGetValues(self):
        """L{BaseCache.getValues} returns values stored in the cache."""
        self.cache.set('identifier1', 'test1')
        self.cache.set('identifier2', 'test2')
        result = BaseCache().getValues([u'identifier1', u'identifier2'])
        self.assertEqual([u'test1', u'test2'], result)

    def testGetValuesWithPrefix(self):
        """L{BaseCache.getValues} uses the given prefix as key."""
        self.cache.set('prefix:identifier1', 'test1')
        self.cache.set('prefix:identifier2', 'test2')
        cache = BaseCache()
        cache.keyPrefix = 'prefix:'
        result = cache.getValues([u'identifier1', u'identifier2'])
        self.assertEqual([u'test1', u'test2'], result)

    def testGetValuesWithUnknownValue(self):
        """L{BaseCache.getValues} returns L{None} for values not found."""
        self.cache.set('identifier1', 'test1')
        result = BaseCache().getValues([u'identifier1', u'identifier2'])
        self.assertEqual([u'test1', None], result)

    def testGetValuesWithEmptyIdentifiers(self):
        """
        L{BaseCache.getValues} returns an empty list if the list of identifiers
        is empty as well.
        """
        self.assertEqual([], BaseCache().getValues([]))

    def testGetValuesWithError(self):
        """
        Redis errors are ignored by L{BaseCache.getValues} and a line is
        written in the logs.
        """
        cache = BaseCache()
        cache._client.connection_pool = ConnectionPool(port=0)
        result = cache.getValues([u'identifier1'])
        self.assertIdentical(None, result)
        self.assertEqual('Redis error: Error 111 connecting localhost:0. '
                         'Connection refused.\n', self.log.getvalue())

    def testSetValues(self):
        """L{BaseCache.setValues} sets values in the cache."""
        BaseCache().setValues({'identifier1': 'test1', 'identifier2': 'test2'})
        self.assertEqual('test1', self.cache.get('identifier1'))
        self.assertEqual('test2', self.cache.get('identifier2'))

    def testSetValuesWithTimeout(self):
        """L{BaseCache.setValues} set the expire timout of the values."""
        BaseCache().setValues({'identifier1': 'test1', 'identifier2': 'test2'})
        expectedTimeout = self.config.getint('cache', 'expire-timeout')
        self.assertAlmostEqual(expectedTimeout, self.cache.ttl('identifier1'))
        self.assertAlmostEqual(expectedTimeout, self.cache.ttl('identifier2'))

    def testSetValuesWithPrefix(self):
        """L{BaseCache.setValues} uses the given prefix as key."""
        cache = BaseCache()
        cache.keyPrefix = 'prefix:'
        cache.setValues({'identifier1': 'test1', 'identifier2': 'test2'})
        self.assertEqual('test1', self.cache.get('prefix:identifier1'))
        self.assertEqual('test2', self.cache.get('prefix:identifier2'))

    def testSetValuesWithError(self):
        """
        Redis errors are ignored by L{BaseCache.setValues} and a line is
        written in the logs.
        """
        cache = BaseCache()
        cache._client.connection_pool = ConnectionPool(port=0)
        cache.setValues({'identifier': 'test'})
        self.assertEqual('Redis error: Error 111 connecting localhost:0. '
                         'Connection refused.\n', self.log.getvalue())

    def testDeleteValues(self):
        """L{BaseCache.deleteValues} deletes values from the cache."""
        self.cache.set('identifier1', 'test1')
        self.cache.set('identifier2', 'test2')
        BaseCache().deleteValues([u'identifier1', u'identifier2'])
        self.assertEqual([None, None],
                         self.cache.mget([u'identifier1', u'identifier2']))

    def testDeleteValuesWithPrefix(self):
        """L{BaseCache.deleteValues} uses the given prefix as key."""
        self.cache.set('prefix:identifier1', 'test1')
        self.cache.set('prefix:identifier2', 'test2')
        cache = BaseCache()
        cache.keyPrefix = 'prefix:'
        cache.deleteValues([u'identifier1', u'identifier2'])
        self.assertEqual([None, None],
                         self.cache.mget([u'prefix:identifier1',
                                          u'prefix:identifier2']))

    def testDeleteValuesWithEmpyIdentifiers(self):
        """
        L{BaseCache.deleteValues} doesn't show errors if an empty list of
        identifiers is given.
        """
        BaseCache().deleteValues([])
        self.assertEqual('', self.log.getvalue())

    def testDeleteValuesWithError(self):
        """
        Redis errors are ignored by L{BaseCache.deleteValues} and a line is
        written in the logs.
        """
        cache = BaseCache()
        cache._client.connection_pool = ConnectionPool(port=0)
        cache.deleteValues(['identifier'])
        self.assertEqual('Redis error: Error 111 connecting localhost:0. '
                         'Connection refused.\n', self.log.getvalue())
