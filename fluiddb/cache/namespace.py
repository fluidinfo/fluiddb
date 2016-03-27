from inspect import isgenerator

from fluiddb.cache.factory import CachingAPIFactory
from fluiddb.cache.permission import PermissionCache
from fluiddb.model.namespace import NamespaceAPI


class CachingNamespaceAPI(object):
    """The public API to cached namespace-related logic in the model.

    @param user: The L{User} to perform operations on behalf of.
    """

    def __init__(self, user):
        self._api = NamespaceAPI(user, factory=CachingAPIFactory())

    def create(self, values):
        """See L{NamespaceAPI.create}."""
        return self._api.create(values)

    def delete(self, paths):
        """See L{NamespaceAPI.delete}.

        Permissions for deleted L{Namespace}s are removed from the cache.
        """
        if isgenerator(paths):
            paths = list(paths)
        cache = PermissionCache()
        cache.clearNamespacePermissions(paths)
        return self._api.delete(paths)

    def get(self, paths, withDescriptions=None, withNamespaces=None,
            withTags=None):
        """See L{NamespaceAPI.get}."""
        return self._api.get(paths, withDescriptions=withDescriptions,
                             withNamespaces=withNamespaces, withTags=withTags)

    def set(self, values):
        """Set or update L{Namespace}s.

        @param values: A C{dict} mapping L{Namespace.path}s to descriptions.
        @return: A C{list} of C{(objectID, Namespace.path)} 2-tuples
            representing the L{Namespace}s that were updated.
        """
        return self._api.set(values)
