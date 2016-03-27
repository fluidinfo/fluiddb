from inspect import isgenerator

from fluiddb.cache.tag import CachingTagAPI
from fluiddb.data.path import getParentPath
from fluiddb.data.permission import Operation
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.security.permission import checkPermissions


# FIXME We should probably have an ITagAPI interface and assert that
# SecureTagAPI and TagAPI both implement it.  And also move the docstrings
# there.
class SecureTagAPI(object):
    """The public API to secure L{Tag}-related functionality.

    @param user: The L{User} to perform operations on behalf of.
    """

    def __init__(self, user):
        self._api = CachingTagAPI(user)
        self._user = user

    def create(self, values):
        """See L{TagAPI.create}.

        @raises PermissionDeniedError: Raised if the user is not authorized to
            create L{Tag}s.
        """
        pathsAndOperations = [(getParentPath(path), Operation.CREATE_NAMESPACE)
                              for path, description in values]
        deniedOperations = checkPermissions(self._user, pathsAndOperations)
        if deniedOperations:
            raise PermissionDeniedError(self._user.username, deniedOperations)
        return self._api.create(values)

    def delete(self, paths):
        """See L{TagAPI.delete}.

        @raises PermissionDeniedError: Raised if the user is not authorized to
            delete L{Tag}s.
        """
        if isgenerator(paths):
            paths = list(paths)
        pathsAndOperations = [(path, Operation.DELETE_TAG) for path in paths]
        deniedOperations = checkPermissions(self._user, pathsAndOperations)
        if deniedOperations:
            raise PermissionDeniedError(self._user.username, deniedOperations)
        return self._api.delete(paths)

    def get(self, paths, withDescriptions=None):
        """See L{TagAPI.get}."""
        return self._api.get(paths, withDescriptions=withDescriptions)

    def set(self, values):
        """See L{TagAPI.set}.

        @raises PermissionDeniedError: Raised if the user is not authorized to
            update L{Tag}s.
        """
        pathsAndOperations = [(path, Operation.UPDATE_TAG)
                              for path in values.iterkeys()]
        deniedOperations = checkPermissions(self._user, pathsAndOperations)
        if deniedOperations:
            raise PermissionDeniedError(self._user.username, deniedOperations)
        return self._api.set(values)
