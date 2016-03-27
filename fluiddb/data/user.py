import crypt
import random
import re
from string import ascii_letters, digits
from uuid import uuid4

from storm.locals import (
    Storm, DateTime, Int, Unicode, UUID, Reference, AutoReload, RawStr)

from fluiddb.data.exceptions import DuplicateUserError, MalformedUsernameError
from fluiddb.data.store import getMainStore
from fluiddb.util.constant import Constant, ConstantEnum, EnumBase


class Role(EnumBase):
    """User roles.

    @cvar ANONYMOUS: A user with the anonymous role only has read-only access
        to data in Fluidinfo, unless a permission specifically grants write
        access to a particular entity.
    @cvar SUPERUSER: A user with the superuser role has read-write access to
        all data in Fluidinfo and is not subject to permission checks.
    @cvar USER: A user with the user role has read-write access to some data
        in Fluidinfo, based on the rules defined by the permission system.
    @cvar USER_MANAGER: A user with the user manager role is the same as a
        C{USER}, except they can create, update and delete L{User}s.
    """

    ANONYMOUS = Constant(1, 'ANONYMOUS')
    SUPERUSER = Constant(2, 'SUPERUSER')
    USER = Constant(3, 'USER')
    USER_MANAGER = Constant(4, 'USER_MANAGER')


DOT_ATOM = r"(^[-!#$%&'*+/=?^_`{}|~0-9A-Z]+(\.[-!#$%&'*+/=?^_`{}|~0-9A-Z]+)*"
QUOTED_STRING = (r"|^\"([\001-\010\013\014\016-\037!#-\[\]-\177]|\\[\001-\011"
                 r"\013\014\016-\177])*\"")
DOMAIN_STRING = r")@(?:[A-Z0-9-]+\.)+[A-Z]{2,6}$"
EMAIL_REGEXP = re.compile(DOT_ATOM + QUOTED_STRING + DOMAIN_STRING,
                          re.IGNORECASE)


def validateEmail(obj, attribute, value):
    """Validate a L{User.email} value before storing it in the database.

    @param obj: The L{User} instance being updated.
    @param attribute: The name of the attribute being set.
    @param value: The email address being stored.
    @raise ValueError: Raised if the value isn't a valid email address.
    @return: The value to store.
    """
    if value is not None and not EMAIL_REGEXP.match(value):
        raise ValueError('%r is not a valid email address.' % value)
    return value


class User(Storm):
    """A user of Fluidinfo.

    @param username: The username of the user.
    @param passwordHash: The hashed password of the user.
    @param fullname: The name of the user.
    @param email: The email address for the user.
    @param role: The L{Role} for the user.
    """

    __storm_table__ = 'users'

    id = Int('id', primary=True, allow_none=False, default=AutoReload)
    objectID = UUID('object_id', allow_none=False)
    role = ConstantEnum('role', enum_class=Role, allow_none=False)
    username = Unicode('username', allow_none=False)
    passwordHash = RawStr('password_hash', allow_none=False)
    fullname = Unicode('fullname', allow_none=False)
    email = Unicode('email', validator=validateEmail)
    namespaceID = Int('namespace_id')
    creationTime = DateTime('creation_time', default=AutoReload)

    namespace = Reference(namespaceID, 'Namespace.id')

    def __init__(self, username, passwordHash, fullname, email, role):
        self.objectID = uuid4()
        self.username = username
        self.passwordHash = passwordHash
        self.fullname = fullname
        self.email = email
        self.role = role

    def isAnonymous(self):
        """Returns C{True} if this user has the anonymous role."""
        return self.role == Role.ANONYMOUS

    def isSuperuser(self):
        """Returns C{True} if this user has the super user role."""
        return self.role == Role.SUPERUSER

    def isUser(self):
        """Returns C{True} if this user has the regular user role."""
        return self.role == Role.USER


def createUser(username, password, fullname, email=None, role=None):
    """Create a L{User} called C{name} with C{role}.

    @param username: A C{unicode} username for the user.
    @param password: A C{unicode} password in plain text for the user.  The
        password will be hashed before being stored.  The password will be
        disabled if C{None} is provided.
    @param email: Optionally, an email address for the user.
    @param role: Optionally, a role for the user, defaults to L{Role.USER}.
    @raise MalformedUsernameError: Raised if C{username} is not valid.
    @raise DuplicateUserError: Raised if a user with the given C{username}
        already exists.
    @return: A new L{User} instance persisted in the main store.
    """
    if not isValidUsername(username):
        raise MalformedUsernameError(username)
    store = getMainStore()
    if store.find(User.id, User.username == username).any():
        raise DuplicateUserError([username])

    passwordHash = '!' if password is None else hashPassword(password)
    role = role if role is not None else Role.USER
    return store.add(User(username, passwordHash, fullname, email, role))


def getUsers(usernames=None, ids=None, objectIDs=None):
    """Get L{User}s.

    @param usernames: Optionally, a sequence of L{User.username}s to filter
        the results with.
    @param ids: Optionally, a sequence of L{User.id}s to filter the results
        with.
    @param objectIDs: Optionally, a sequence of L{User.objectID}s to filter the
        result with.
    @return: A C{ResultSet} with matching L{User}s.
    """
    store = getMainStore()
    where = []
    if ids:
        where.append(User.id.is_in(ids))
    if usernames:
        where.append(User.username.is_in(usernames))
    if objectIDs:
        where.append(User.objectID.is_in(objectIDs))
    return store.find(User, *where)


# Password hashing code used by the low-level functions for creating users
ALPHABET = ascii_letters + digits
SALT_LENGTH = 8


def hashPassword(password, salt=None):
    """Convert a password string into a secure hash.

    This function generates an MD5-hashed password, which consists of three
    fields separated by a C{$} symbol:

     1. The status of the password.  If this field is empty, the user is
        enabled, otherwise it's disabled.  The C{!} character should be used
        when specifying that a user is disabled.
     2. The mechanism (1 for MD5, 2a for Blowfish, 5 for SHA-256 and 6 for
        SHA-512).
     3. The salt.
     4. The hashed password.

    @param password: The C{unicode} password to be hashed.
    @param salt: Optionally, a key to be passed to the L{crypt.crypt} function
        to secure against brute-force attacks. Defaults to a random string
        and the MD5 hashing algorithm.
    @return: A C{str} hash of C{password} generated with C{crypt} algorithm.
    """
    # crypt.crypt needs the password to be encoded in ASCII
    password = password.encode('utf-8')
    if salt is None:
        salt = '$1$' + ''.join(random.choice(ALPHABET)
                               for _ in xrange(SALT_LENGTH))
    return crypt.crypt(password, salt)


USERNAME_REGEXP = re.compile(r'^[\:\.\-\w]{1,128}$', re.UNICODE)


def isValidUsername(username):
    """Determine if C{username} is valid.

    A username may only contain letters, numbers, and colon, dash, dot and
    underscore characters. It can't contain more than 128 characters.

    @param path: A C{unicode} username to validate.
    @return: C{True} if C{username} is valid, otherwise C{False}.
    """
    return (USERNAME_REGEXP.match(username) is not None)


class TwitterUser(Storm):
    """The Twitter UID for a Fluidinfo user.

    @param userID: The L{User.id} to link to Twitter.
    @param uid: The Twitter UID to link to the L{Fluidinfo} user.
    """

    __storm_table__ = 'twitter_users'

    userID = Int('user_id', primary=True, allow_none=False)
    uid = Int('uid', allow_none=False)
    creationTime = DateTime('creation_time', default=AutoReload)

    user = Reference(userID, User.id)

    def __init__(self, userID, uid):
        self.userID = userID
        self.uid = uid


def createTwitterUser(user, uid):
    """Create a L{TwitterUser}.

    @param user: The L{User} to link to a Twitter account.
    @param uid: The Twitter UID for the user.
    @return: A new L{TwitterUser} instance persisted in the main store.
    """
    store = getMainStore()
    return store.add(TwitterUser(user.id, uid))


def getTwitterUsers(uids=None):
    """Get C{(User, TwitterUser)} 2-tuples matching specified Twitter UIDs.

    @param uids: Optionally, a sequence of L{TwitterUser.uid}s to filter the
        results with.
    @return: A C{ResultSet} with matching C{(User, TwitterUser)} 2-tuples.
    """
    store = getMainStore()
    where = []
    if uids:
        where.append(TwitterUser.uid.is_in(uids))
    return store.find((User, TwitterUser),
                      User.id == TwitterUser.userID,
                      *where)
