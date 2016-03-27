from itertools import izip
from uuid import UUID

from fluiddb.cache.cache import BaseCache, CacheResult
from fluiddb.cache.factory import CachingAPIFactory
from fluiddb.model.object import ObjectAPI


class CachingObjectAPI(object):
    """The public API to cached object-related functionality.

    @param user: The L{User} to perform operations on behalf of.
    """

    def __init__(self, user):
        self._api = ObjectAPI(user, factory=CachingAPIFactory())
        self._cache = ObjectCache()
        self._user = user

    def create(self, value=None):
        """See L{ObjectAPI.create}."""
        return self._api.create(value)

    def get(self, values):
        """Get object IDs matching C{fluiddb/about} tag values.

        Values will be fetched from the cache if they are available, otherwise
        they will be fetched directly from the data base.

        See L{ObjectAPI.get} for more details.
        """
        cached = self._cache.get(values)
        if cached.uncachedValues:
            result = self._api.get(cached.uncachedValues)
            if result:
                self._cache.save(result)
                cached.results.update(result)
        return cached.results

    def getTagsByObjects(self, objectIDs):
        """See L{ObjectAPI.getTagsByObjects}."""
        return self._api.getTagsByObjects(objectIDs)

    def getTagsForObjects(self, objectIDs):
        """See L{ObjectAPI.getTagsForObjects}."""
        return self._api.getTagsForObjects(objectIDs)

    def search(self, queries, implicitCreate=True):
        """See L{ObjectAPI.search}."""
        return self._api.search(queries, implicitCreate)


class ObjectCache(BaseCache):
    """Provides caching functions for the L{CachingObjectAPI} class."""

    keyPrefix = u'about:'

    def get(self, values):
        """
        Get object IDs stored in the cache for the given C{fluiddb/about}
        values.  See L{CachingObjectAPI.get}.

        @param values: A C{list} of C{fluiddb/about} tag values.
        @return: A L{CacheResult} instance with a C{dict} mapping
            C{fluiddb/about} tag values to object IDs in the C{results} field
            and uncached about values in the C{uncachedValues} field.
        """
        result = self.getValues(values)

        if result is None:
            return CacheResult({}, values)

        foundValues = {}
        uncachedValues = []
        for aboutValue, objectID in izip(values, result):
            if objectID is None:
                uncachedValues.append(aboutValue)
            else:
                foundValues[aboutValue] = UUID(objectID)
        return CacheResult(foundValues, uncachedValues)

    def save(self, result):
        """
        Save a L{CachingObjectAPI.get} result in the cache for faster future
        requests.

        @param result: A C{dict} mapping C{fluiddb/about} tag values to object
            IDs. usually returned by a L{CachingObjectAPI.get} call.
        """
        self.setValues(result)
