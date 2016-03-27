from inspect import isgenerator

from fluiddb.cache.factory import CachingAPIFactory
from fluiddb.cache.recentactivity import (
    RecentObjectActivityCache, RecentUserActivityCache)
from fluiddb.model.value import TagValueAPI


class CachingTagValueAPI(object):
    """The public API to cached L{TagValue}-related logic in the model.

    @param user: The L{User} to perform operations on behalf of.
    """

    def __init__(self, user):
        self._api = TagValueAPI(user, factory=CachingAPIFactory())
        self._user = user

    def get(self, objectIDs, paths=None):
        """See L{TagValueAPI.get}."""
        return self._api.get(objectIDs, paths)

    def set(self, values):
        """See L{TagValueAPI.set}."""
        result = self._api.set(values)
        RecentObjectActivityCache().clear(values.keys())
        RecentUserActivityCache().clear([self._user.username])
        return result

    def delete(self, values):
        """See L{TagValueAPI.delete}."""
        if isgenerator(values):
            values = list(values)
        result = self._api.delete(values)
        objectIDs = [objectID for objectID, path in values]
        RecentObjectActivityCache().clear(objectIDs)
        RecentUserActivityCache().clear([self._user.username])
        return result
