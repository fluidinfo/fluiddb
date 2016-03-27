from inspect import isgenerator

from fluiddb.data.exceptions import DuplicateUserError, UnknownUserError
from fluiddb.data.namespace import getNamespaces
from fluiddb.data.permission import Operation, Policy
from fluiddb.data.user import (
    User, createUser, createTwitterUser, getUsers, getTwitterUsers,
    hashPassword)
from fluiddb.exceptions import FeatureError
from fluiddb.model.factory import APIFactory


class UserAPI(object):
    """The public API for L{User}s in the model layer.

    @param factory: Optionally, the API factory to use when creating internal
        APIs.  Default is L{APIFactory}.
    """

    def __init__(self, factory=None):
        self._factory = factory or APIFactory()

    def create(self, values, createPrivateNamespace=None):
        """Create new L{User}s.

        @param values: A sequence of C{(username, password, fullname, email)}
            4-tuples.
        @param createPrivateNamespace: Optionally, a flag to specify whether
            or not the C{<username>/private} L{Namespace} should be created.
            Default is C{True}.
        @raise DuplicateUserError: Raised if the username for a new L{User}
            collides with an existing one.
        @raise FeatureError: Raised if C{values} is empty.
        @return: A C{list} of C{(objectID, username)} 2-tuples for the new
            L{User}s.
        """
        if not values:
            raise FeatureError('Information about at least one user must be '
                               'provided.')

        # Make sure usernames don't exist before trying to create
        # new users.
        usernames = [username for username, _, _, _ in values]
        result = getUsers(usernames=usernames)
        existingUsernames = set(result.values(User.username))
        if existingUsernames:
            raise DuplicateUserError(existingUsernames)

        # Create the users.
        systemValues = {}
        result = []
        privateUpdateResults = []
        admin = getUser(u'fluiddb')
        objects = self._factory.objects(admin)
        for username, password, fullname, email in values:
            user = createUser(username, password, fullname, email)
            about = u'@%s' % username
            user.objectID = objects.create(about)
            namespaces = self._factory.namespaces(user)

            # Create the user's root namespace.
            namespaces.create([(username,
                                u'Namespace for user %s' % username)])
            namespace = getNamespaces(paths=[username]).one()
            user.namespaceID = namespace.id

            # Create the user's private namespace.
            if createPrivateNamespace is None or createPrivateNamespace:
                privateNamespaceName = '%s/private' % username
                privateUpdateResults.append(
                    namespaces.create(
                        [(privateNamespaceName,
                          u'Private namespace for user %s' % username)]))
                namespace = getNamespaces(paths=[privateNamespaceName]).one()
                permission = namespace.permission
                permission.set(Operation.LIST_NAMESPACE, Policy.CLOSED,
                               [user.id])

            # Create system tags
            systemValues[user.objectID] = {
                u'fluiddb/users/username': username,
                u'fluiddb/users/name': fullname,
                u'fluiddb/users/email': email,
                u'fluiddb/users/role': unicode(user.role)}
            result.append((user.objectID, user.username))
        self._factory.tagValues(admin).set(systemValues)
        return result

    def delete(self, usernames):
        """Delete L{User}s matching C{username}s.

        @param usernames: A sequence of L{User.username}s.
        @raise FeatureError: Raised if no L{User.username}s are provided.
        @raise UnknownUserError: Raised if one or more usernames don't match
            existing L{User}s.
        @return: A  C{list} of C{(objectID, User.username)} 2-tuples
            representing the L{User}s that that were removed.
        """
        if isgenerator(usernames):
            usernames = list(usernames)
        if not usernames:
            raise FeatureError('At least one username must be provided.')

        usernames = set(usernames)
        result = getUsers(usernames=usernames)
        existingUsernames = set(result.values(User.username))
        unknownUsernames = usernames - existingUsernames
        if unknownUsernames:
            raise UnknownUserError(list(unknownUsernames))

        admin = getUser(u'fluiddb')
        deletedUsers = list(result.values(User.objectID, User.username))
        # FIXME: Deleting a user will leave the permission exception lists
        # containing the user in a corrupt state.
        result.remove()
        self._factory.tagValues(admin).delete(
            [(objectID, systemTag) for objectID, _ in deletedUsers
             for systemTag in [u'fluiddb/users/username',
                               u'fluiddb/users/name',
                               u'fluiddb/users/email',
                               u'fluiddb/users/role']])
        return deletedUsers

    def get(self, usernames):
        """Get information about L{User}s matching C{usernames}.

        @param usernames: A sequence of L{User.username}s.
        @raise FeatureError: Raised if no L{User.username}s are provided.
        @return: A C{dict} that maps L{User.username}s to C{dict}s with
            information about matching L{User}s, matching the following
            format::

              {<username>: {'id': <object-id>,
                            'name': <full-name>,
                            'role': <role>}}
        """
        if not usernames:
            raise FeatureError('At least one username must be provided.')

        result = getUsers(usernames=usernames)
        result = result.values(User.objectID, User.username, User.fullname,
                               User.role)
        users = {}
        for objectID, username, name, role in result:
            users[username] = {'id': objectID, 'name': name, 'role': role}
        return users

    def set(self, values):
        """Update information about L{User}s.

        If an incoming field is C{None} the appropriate instance field will not
        be modified.

        @param values: A sequence of C{(username, password, fullname, email,
            role)} 5-tuples.
        @raise FeatureError: Raised if C{values} is empty.
        @raise UnknownUserError: Raised if a specified L{User} does not exist.
        @return: A 2-tuples representing the L{User}s that were updated.
        """
        if not values:
            raise FeatureError('Information about at least one user must be '
                               'provided.')

        usernames = set(username for username, _, _, _, _ in values)
        users = dict((user.username, user)
                     for user in getUsers(usernames=usernames))
        existingUsernames = set(users.iterkeys())
        unknownUsernames = usernames - existingUsernames
        if unknownUsernames:
            raise UnknownUserError(list(unknownUsernames))

        result = []
        systemValues = {}
        for username, password, fullname, email, role in values:
            user = users[username]
            valuesToUpdate = {}
            if password is not None:
                user.passwordHash = hashPassword(password)
            if fullname is not None:
                user.fullname = fullname
                valuesToUpdate[u'fluiddb/users/name'] = user.fullname
            if email is not None:
                user.email = email
                valuesToUpdate[u'fluiddb/users/email'] = user.email
            if role is not None:
                user.role = role
                valuesToUpdate[u'fluiddb/users/role'] = unicode(user.role)
            if valuesToUpdate:
                systemValues[user.objectID] = valuesToUpdate
            result.append((user.objectID, user.username))
        if systemValues:
            admin = getUser(u'fluiddb')
            self._factory.tagValues(admin).set(systemValues)
        return result


class TwitterUserAPI(object):
    """The public API for L{TwitterUser}s in the model layer."""

    def create(self, username, uid):
        """Create a L{TwitterUser} mapping a UID to the specified username.

        @param username: The L{User.username} the UID is for.
        @param uid: The Twitter UID for the specified Fluidinfo user.
        @raise UnknownUserError: Raised if the specified L{User} doesn't exist.
        """
        user = getUser(username)
        if user is None:
            raise UnknownUserError([username])
        createTwitterUser(user, uid)

    def get(self, uid):
        """Get the L{User} matching a Twitter UID.

        @param uid: The Twitter UID to fetch a L{User} for.
        @return: The matching L{User} or C{None} if one isn't available.
        """
        result = getTwitterUsers(uids=[uid]).one()
        if result is not None:
            return result[0]
        else:
            return None


def checkPassword(password, passwordHash):
    """Check that a given plaintext password matches a password hash.

    @param password: A C{unicode} password in plain text.
    @param passwordHash: A hashed C{str}.
    @return: C{True} if the password matches the password hash, otherwise
        C{False}.
    """
    return hashPassword(password, passwordHash) == passwordHash


def getUser(username):
    """Get a L{User} object for a given username.

    @param username: The username of the user to get.
    @return: A L{User} object or C{None} if the username doesn't exist.
    """
    return getUsers(usernames=[username]).one()
