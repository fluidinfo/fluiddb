from inspect import isgenerator

from fluiddb.cache.namespace import CachingNamespaceAPI
from fluiddb.data.path import getParentPath
from fluiddb.data.permission import Operation
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.security.permission import checkPermissions


# FIXME We should probably have an INamespaceAPI interface and assert that
# SecureNamespaceAPI and NamespaceAPI both implement it.  And also move the
# docstrings there.
class SecureNamespaceAPI(object):
    """The public API to secure L{Namespace}-related functionality.

    @param user: The L{User} to perform operations on behalf of.
    """

    def __init__(self, user):
        self._api = CachingNamespaceAPI(user)
        self._user = user

    def create(self, values):
        """See L{NamespaceAPI.create}.

        @raise PermissionDeniedError: Raised if the user is not authorized to
            create L{Namespace}s.
        """
        paths = []
        pathsAndOperations = []
        for path, description in values:
            parentPath = getParentPath(path)
            pathsAndOperations.append((parentPath, Operation.CREATE_NAMESPACE))
            paths.append(path)

        deniedOperations = checkPermissions(self._user, pathsAndOperations)
        if deniedOperations:
            raise PermissionDeniedError(self._user.username, deniedOperations)

        return self._api.create(values)

    def delete(self, paths):
        """See L{NamespaceAPI.delete}.

        @raise PermissionDeniedError: Raised if the user is not authorized to
            delete a given L{Namespace}.
        """
        if isgenerator(paths):
            paths = list(paths)
        pathsAndOperations = [(path, Operation.DELETE_NAMESPACE)
                              for path in paths]
        deniedOperations = checkPermissions(self._user, pathsAndOperations)
        if deniedOperations:
            raise PermissionDeniedError(self._user.username, deniedOperations)

        return self._api.delete(paths)

    def get(self, paths, withDescriptions=None, withNamespaces=None,
            withTags=None):
        """See L{NamespaceAPI.get}.

        @raise PermissionDeniedError: Raised if the user is not authorized to
            list a given L{Namespace}.
        """
        if withNamespaces or withTags:
            pathsAndOperations = [(path, Operation.LIST_NAMESPACE)
                                  for path in paths]
            deniedOperations = checkPermissions(self._user, pathsAndOperations)
            if deniedOperations:
                raise PermissionDeniedError(self._user.username,
                                            deniedOperations)

        return self._api.get(paths, withDescriptions=withDescriptions,
                             withNamespaces=withNamespaces, withTags=withTags)

    def set(self, values):
        """See L{NamespaceAPI.set}.

        @raise PermissionDeniedError: Raised if the user is not authorized to
            update a given L{Namespace}.
        """
        pathsAndOperations = [(path, Operation.UPDATE_NAMESPACE)
                              for path in values.iterkeys()]
        deniedOperations = checkPermissions(self._user, pathsAndOperations)
        if deniedOperations:
            raise PermissionDeniedError(self._user.username, deniedOperations)

        return self._api.set(values)
