import logging

from redis import Redis, RedisError

from fluiddb.application import getConfig, getCacheConnectionPool


class CacheResult(object):
    """Encapsulates the information returned by cache look up.

    @ivar results: Those results found in the cache.
    @ivar uncachedValues: Those values not found in the cache.
    """

    def __init__(self, results, uncachedValues):
        self.results = results
        self.uncachedValues = uncachedValues


def getCacheClient():
    """
    Returns a L{Redis} client instance. It uses a global ConnectionPool for the
    whole process.
    """
    connectionPool = getCacheConnectionPool()
    if connectionPool is None:
        raise RuntimeError('ConnectionPool is not configured')
    return Redis(connection_pool=connectionPool)


class BaseCache(object):
    """Base class for all objects that fetch values from the cache.

    @cvar keyPrefix: The prefix for the keys stored in the cache.
    """
    keyPrefix = ''

    def __init__(self):
        self._client = getCacheClient()
        config = getConfig()
        self.expireTimeout = config.getint('cache', 'expire-timeout')

    def _getKey(self, identifier):
        """Generate a key for the key-value store with the appropriate prefix.

        @param identifier: The identifier to combine with the key prefix.
        @return: A C{unicode} string to be used as key in the cache.
        """
        return self.keyPrefix + identifier

    def getValues(self, identifiers):
        """Get a value from the cache for the given identifiers.

        @param identifiers: A C{list} of identifier to make the keys.
        @return A C{list} with all the values for the given identifiers.
        """
        if not identifiers:
            return []
        try:
            keys = [self._getKey(identifier) for identifier in identifiers]
            return self._client.mget(keys)
        except RedisError as error:
            logging.error('Redis error: %s', error)

    def setValues(self, values):
        """Set values in the cache for the given identifiers.

        @param values: A C{dict} mapping identifiers to values.
        """
        pipe = self._client.pipeline()
        for identifier, value in values.iteritems():
            pipe.setex(self._getKey(identifier), value, self.expireTimeout)
        try:
            results = pipe.execute()
            for item in results:
                if isinstance(item, RedisError):
                    raise item
        except RedisError as error:
            logging.error('Redis error: %s', error)

    def deleteValues(self, identifiers):
        """Delete values from the cache for the given identifiers.

        @param identifiers: A C{list} of identifier to make the keys.
        """
        if not identifiers:
            return
        try:
            keys = [self._getKey(identifier) for identifier in identifiers]
            self._client.delete(*keys)
        except RedisError as error:
            logging.error('Redis error: %s', error)
