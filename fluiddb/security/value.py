from inspect import isgenerator

from fluiddb.cache.value import CachingTagValueAPI
from fluiddb.data.permission import Operation
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.security.object import SecureObjectAPI
from fluiddb.security.permission import checkPermissions


class SecureTagValueAPI(object):
    """The public API to secure L{TagValue}-related functionality.

    @param user: The L{User} to perform operations on behalf of.
    """

    def __init__(self, user):
        self._user = user
        self._api = CachingTagValueAPI(user)

    def get(self, objectIDs, paths=None):
        """See L{TagValueAPI.get}.

        @raise PermissionDeniedError: Raised if the user is not authorized to
            read L{TagValue}s.
        """
        if paths is not None:
            pathsAndOperations = set((path, Operation.READ_TAG_VALUE)
                                     for path in paths)
            deniedOperations = checkPermissions(self._user, pathsAndOperations)
            if deniedOperations:
                raise PermissionDeniedError(self._user.username,
                                            deniedOperations)
        else:
            paths = SecureObjectAPI(self._user).getTagsForObjects(objectIDs)
        return self._api.get(objectIDs, paths)

    def set(self, values):
        """See L{TagValueAPI.set}.

        @raise PermissionDeniedError: Raised if the user is not authorized to
            create or update L{TagValue}s.
        """
        pathsAndOperations = set()
        for tagValues in values.itervalues():
            pathsAndOperations.update((path, Operation.WRITE_TAG_VALUE)
                                      for path in tagValues.iterkeys())
        deniedOperations = checkPermissions(self._user, pathsAndOperations)
        if deniedOperations:
            raise PermissionDeniedError(self._user.username, deniedOperations)

        return self._api.set(values)

    def delete(self, values):
        """See L{TagValueAPI.delete}.

        @raise PermissionDeniedError: Raised if the user is not authorized to
            delete L{TagValue}s.
        """
        if isgenerator(values):
            values = list(values)
        pathsAndOperations = set((path, Operation.DELETE_TAG_VALUE)
                                 for _, path, in values)
        deniedOperations = checkPermissions(self._user, pathsAndOperations)
        if deniedOperations:
            raise PermissionDeniedError(self._user.username, deniedOperations)
        return self._api.delete(values)
