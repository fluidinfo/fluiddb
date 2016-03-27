from fluiddb.data.exceptions import UnknownUserError
from fluiddb.model.user import checkPassword
from fluiddb.cache.user import cachingGetUser


class AuthenticationError(Exception):
    """
    Raised when an attempt to C{authenticate} an existing L{User} with
    invalid credentials is made.

    @param username: The username of the L{User}.
    """

    def __init__(self, username):
        self.username = username

    def __str__(self):
        return 'Invalid credentials for user %r.' % self.username


def authenticate(username, password):
    """Authenticate a L{User}.

    @param username: The username of the requested L{User}.
    @param password: The password in plaintext for authenticating the L{User}.
    @raise UnknownUserError: If there's no L{User} with the given C{username}.
    @raise AuthenticationError: If the given C{password} doesn't match the
        L{User}'s.
    @return: A L{User} representing the user.
    """
    user = cachingGetUser(username)
    if user is None:
        raise UnknownUserError([username])
    elif not checkPassword(password, user.passwordHash):
        raise AuthenticationError(username)
    return user
