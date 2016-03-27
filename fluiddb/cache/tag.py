from inspect import isgenerator

from fluiddb.cache.factory import CachingAPIFactory
from fluiddb.cache.permission import PermissionCache
from fluiddb.cache.recentactivity import (
    RecentObjectActivityCache, RecentUserActivityCache)
from fluiddb.data.value import getObjectIDs
from fluiddb.model.tag import TagAPI


class CachingTagAPI(object):
    """The public API to cached tag-related logic in the model.

    @param user: The L{User} to perform operations on behalf of.
    """

    def __init__(self, user):
        self._api = TagAPI(user, factory=CachingAPIFactory())

    def create(self, values):
        """See L{TagAPI.create}."""
        return self._api.create(values)

    def delete(self, paths):
        """See L{TagAPI.delete}.

        Permissions for deleted L{Tag}s are removed from the cache.
        """
        if isgenerator(paths):
            paths = list(paths)
        # FIXME getObjectIDs is called twice--once here and once in
        # TagAPI.delete.  It would be better if we only did this once, not to
        # mention that this breaks encapsulation by bypassing the model layer
        # and accessing the data layer directly. -jkakar
        objectIDs = set(getObjectIDs(paths))
        RecentObjectActivityCache().clear(objectIDs)
        usernames = set([path.split('/')[0] for path in paths])
        RecentUserActivityCache().clear(usernames)
        PermissionCache().clearTagPermissions(paths)
        return self._api.delete(paths)

    def get(self, paths, withDescriptions=None):
        """See L{TagAPI.get}."""
        return self._api.get(paths, withDescriptions=withDescriptions)

    def set(self, values):
        """Set L{TagAPI.set}."""
        return self._api.set(values)
