from datetime import datetime
from json import dumps, loads
from uuid import UUID

from fluiddb.cache.cache import BaseCache, CacheResult
from fluiddb.model.recentactivity import RecentActivityAPI


class CachingRecentActivityAPI(object):
    """The public API to cached recent activity-related functionality."""

    def __init__(self):
        self._api = RecentActivityAPI()

    def getForObjects(self, objectIDs):
        """Get information about recent tag values on the given objects.

        The cache is only used if a single object ID is provided.  Requests
        for many object IDs will hit the database.

        @param objectIDs: A sequence of object IDs to get recent tags from.
        @return: A C{list} of C{(Tag.path, TagValue.objectID,
            AboutTagValue.value, TagValue.value, User.username,
            value.creationTime)} 6-tuples with the information about the
            recent tag values.
        """
        if not objectIDs:
            return []
        elif len(objectIDs) > 1:
            return self._api.getForObjects(objectIDs)
        else:
            [objectID] = objectIDs
            cache = RecentObjectActivityCache()
            cached = cache.get(objectID)
            if cached.uncachedValues:
                result = self._api.getForObjects([objectID])
                if result:
                    cache.save(objectID, result)
                    cached.results[objectID] = result
            return cached.results.get(objectID, [])

    def getForUsers(self, usernames):
        """Get information about recent tag values on the given users.

        @param usernames: A sequence of usernames to get recent tags from.
        @raise: L{UnknownUserError} if one of the given usernames doesn't
            exist.
        @return: A C{list} of C{(Tag.path, TagValue.objectID,
            AboutTagValue.value, TagValue.value, User.username,
            value.creationTime)} 6-tuples with the information about the
            recent tag values.
        """
        if not usernames:
            return []
        elif len(usernames) > 1:
            return self._api.getForUsers(usernames)
        else:
            [username] = usernames
            cache = RecentUserActivityCache()
            cached = cache.get(username)
            if cached.uncachedValues:
                result = self._api.getForUsers([username])
                if result:
                    cache.save(username, result)
                    cached.results[username] = result
            return cached.results.get(username, [])


class RecentActivityCacheBase(BaseCache):
    """Base class for recent activity caching logic."""

    def get(self, identifier):
        """Get recent object activity from the cache.

        @param identifier: The identifier to fetch cached data for.
        @return: A L{CacheResult} instance with a C{dict} mapping the object
            ID to recent activity 6-tuples in the C{results} field.  If no
            cached data is available the object ID will be available in the
            C{uncachedValues} field.
        """
        result = self.getValues([identifier])
        if result is None or result == [None]:
            return CacheResult({}, [identifier])

        result = loads(result[0])
        recentActivity = []
        for value in result:
            value[1] = UUID(value[1])
            value[5] = datetime.strptime(value[5], '%Y-%m-%dT%H:%M:%S.%f')
            recentActivity.append(tuple(value))
        return CacheResult({identifier: recentActivity}, [])

    def save(self, identifier, recentActivity):
        """Save recent object activity in the cache.

        @param identifier: The identifier the recent activity is associated
            with.
        @param recentActivity: A list of recent activity 6-tuples.
        """
        serializableValues = []
        for value in recentActivity:
            value = list(value)
            value[1] = str(value[1])
            value[5] = value[5].isoformat()
            serializableValues.append(tuple(value))
        self.setValues({identifier: dumps(serializableValues)})

    def clear(self, identifiers):
        """Invalidate recent object activity in the cache.

        @param identifiers: A sequence of recent activity identifiers to
            invalidate.
        """
        self.deleteValues(identifiers)


class RecentUserActivityCache(RecentActivityCacheBase):
    """Cache recent L{User} activity for L{CachingRecentActivityAPI}."""

    keyPrefix = u'recentactivity:user:'


class RecentObjectActivityCache(RecentActivityCacheBase):
    """Cache recent object activity for L{CachingRecentActivityAPI}."""

    keyPrefix = u'recentactivity:object:'

    def _getKey(self, identifier):
        return super(RecentObjectActivityCache, self)._getKey(str(identifier))
