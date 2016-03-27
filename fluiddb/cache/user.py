from inspect import isgenerator
import json
from uuid import UUID

from fluiddb.cache.cache import BaseCache, CacheResult
from fluiddb.cache.factory import CachingAPIFactory
from fluiddb.data.user import User, Role
from fluiddb.model.user import getUser, UserAPI


def cachingGetUser(username):
    """Get a L{User} for a given username.

    The L{User}s will be fetched from the cache, otherwise it will be fetched
    directly from the database. Cache misses will be added to the cache. See
    L{fluiddb.model.user.getUser}.

    @param username: The username of the user.
    @return: A L{User} instance corresponding to the given username.
    """
    cache = UserCache()
    cachedResult = cache.get(username)
    if cachedResult.results is not None:
        return cachedResult.results
    else:
        user = getUser(username)
        if user is not None:
            cache.save(user)
        return user


class CachingUserAPI(object):
    """The public API to secure L{User}-related functionality.

    @param user: The L{User} to perform operations on behalf of.
    """

    def __init__(self):
        self._api = UserAPI(factory=CachingAPIFactory())

    def create(self, values, createPrivateNamespace=None):
        """See L{UserAPI.create}."""
        return self._api.create(values, createPrivateNamespace)

    def delete(self, usernames):
        """See L{UserAPI.delete}."""
        if isgenerator(usernames):
            usernames = list(usernames)
        cache = UserCache()
        for username in usernames:
            cache.clear(username)
        return self._api.delete(usernames)

    def get(self, usernames):
        """See L{UserAPI.get}."""
        return self._api.get(usernames)

    def set(self, values):
        """See L{UserAPI.set}."""
        cache = UserCache()
        for username, password, fullname, email, role in values:
            cache.clear(username)
        return self._api.set(values)


class UserCache(BaseCache):
    """Provides caching functions for the L{getUser} function."""

    keyPrefix = u'user:'

    def get(self, username):
        """Get a L{User} object from the cache.

        @param username: The username of the L{User} as C{unicode}.
        @return: A L{CacheResult} object with the L{User} in the L{results}
            field if it's found or the username in the C{uncachedValues}
            field if it's not found.
        """
        result = self.getValues([username])
        if result is None or result == [None]:
            return CacheResult(None, username)

        userdict = json.loads(result[0])

        user = User(username=userdict['username'],
                    passwordHash=str(userdict['passwordHash']),
                    fullname=userdict['fullname'],
                    email=userdict['email'],
                    role=Role.fromID(userdict['role']))
        user.id = userdict['id']
        user.objectID = UUID(userdict['objectID'])

        return CacheResult(user, None)

    def save(self, user):
        """Store a L{User} in the cache.

        @param user: A L{User} object to save in the cache.
        """
        userdict = {'id': user.id,
                    'objectID': str(user.objectID),
                    'username': user.username,
                    'passwordHash': user.passwordHash,
                    'fullname': user.fullname,
                    'email': user.email,
                    'role': user.role.id}

        self.setValues({user.username: json.dumps(userdict)})

    def clear(self, username):
        """Delete a L{User} from the cache.

        @param username: The username of the L{User} as C{unicode}.
        """
        self.deleteValues([username])
