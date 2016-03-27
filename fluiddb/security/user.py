from inspect import isgenerator

from fluiddb.cache.user import CachingUserAPI
from fluiddb.data.permission import Operation
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.security.permission import checkPermissions


class SecureUserAPI(object):
    """The public API to secure L{User}-related functionality.

    @param user: The L{User} to perform operations on behalf of.
    """

    def __init__(self, user):
        self._user = user
        self._api = CachingUserAPI()

    def create(self, values, createPrivateNamespace=None):
        """See L{UserAPI.create}.

        @raises PermissionDeniedError: Raised if the user is not a
            superuser and tries to create a new L{User}.
        """
        actions = [(username, Operation.CREATE_USER)
                   for username, password, fullname, email in values]
        deniedActions = checkPermissions(self._user, actions)
        if deniedActions:
            raise PermissionDeniedError(self._user.username, deniedActions)
        return self._api.create(values,
                                createPrivateNamespace=createPrivateNamespace)

    def delete(self, usernames):
        """See L{UserAPI.delete}.

        @raises PermissionDeniedError: Raised if the user is not a superuser
            and tries to delete a L{User}.
        """
        if isgenerator(usernames):
            usernames = list(usernames)
        actions = [(username, Operation.DELETE_USER) for username in usernames]
        deniedActions = checkPermissions(self._user, actions)
        if deniedActions:
            raise PermissionDeniedError(self._user.username, deniedActions)
        return self._api.delete(usernames)

    def get(self, usernames):
        """See L{UserAPI.get}."""
        return self._api.get(usernames)

    def set(self, values):
        """See L{UserAPI.set}.

        @raises PermissionDeniedError: Raised if the user is not a superuser
            and tries to set values for a L{User}.
        """
        actions = [(username, Operation.UPDATE_USER)
                   for username, password, fullname, email, role in values]
        deniedActions = checkPermissions(self._user, actions)
        if deniedActions:
            raise PermissionDeniedError(self._user.username, deniedActions)
        return self._api.set(values)
