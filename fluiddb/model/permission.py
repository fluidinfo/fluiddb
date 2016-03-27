from collections import defaultdict

from fluiddb.data.exceptions import UnknownUserError
from fluiddb.data.namespace import Namespace, getNamespaces
from fluiddb.data.path import getParentPath, getPathHierarchy
from fluiddb.data.permission import (
    Operation, getNamespacePermissions, getTagPermissions)
from fluiddb.data.tag import Tag, getTags
from fluiddb.data.user import User, Role, getUsers
from fluiddb.exceptions import FeatureError
from fluiddb.model.exceptions import UserNotAllowedInExceptionError
from fluiddb.model.factory import APIFactory
from fluiddb.util.readonly import readonly


class PermissionAPI(object):
    """The public API to permission-related functionality in the model.

    @param user: The L{User} to perform operations on behalf of.
    @param factory: Optionally, the API factory to use when creating internal
        APIs.  Default is L{APIFactory}.
    """

    def __init__(self, user, factory=None):
        self._user = user
        self._factory = factory or APIFactory()

    def set(self, values):
        """Update L{NamespacePermission}s and L{TagPermission}s.

        @param values: A sequence of C{(path, Operation, Policy, exceptions)}
            4-tuples.
        @raise RuntimeError: Raised if an invalid L{Operation} is provided.
        """
        if not values:
            return

        usernames = set()
        for path, operation, policy, exceptions in values:
            usernames.update(exceptions)
        idByUsername, roleByUsername = self._getUserDetails(usernames)
        self._validatePermissions(values, roleByUsername)

        namespacePermissions = defaultdict(list)
        tagPermissions = defaultdict(list)
        for path, operation, policy, exceptions in values:
            if operation in Operation.NAMESPACE_OPERATIONS:
                namespacePermissions[path].append((operation, policy,
                                                   exceptions))
            elif operation in Operation.TAG_OPERATIONS:
                tagPermissions[path].append((operation, policy, exceptions))
            else:
                raise RuntimeError("Can't set operation %s." % operation)
        self._setNamespacePermissions(namespacePermissions, idByUsername)
        self._setTagPermissions(tagPermissions, idByUsername)

    def _getUserDetails(self, usernames):
        """Get information about the specified usernames.

        @param usernames: A C{set} of usernames to get information about.
        @return: An C{(<id-username-mapping>, <role-username-mapping)}
            2-tuple.
        """
        result = getUsers(usernames=usernames)
        users = result.values(User.username, User.id, User.role)
        idByUsername = {}
        roleByUsername = {}
        for username, userID, role in users:
            idByUsername[username] = userID
            roleByUsername[username] = role
        unknownUsernames = usernames - set(idByUsername.iterkeys())
        if unknownUsernames:
            raise UnknownUserError(list(unknownUsernames))
        return idByUsername, roleByUsername

    def _validatePermissions(self, values, roleByUsername):
        """Validate permission data.

        @param values: A sequence of C{(path, Operation, Policy, exceptions)}
            4-tuples.
        @raises FeatureError: Raised if a L{Role.SUPERUSER} user is in an
            exceptions list or if a L{Role.ANONYMOUS} user is in an exceptions
            list for an L{Operation} they are not allowed to perform.
        """
        for path, operation, policy, exceptions in values:
            for username in exceptions:
                role = roleByUsername[username]
                if role == Role.SUPERUSER:
                    raise UserNotAllowedInExceptionError(
                        "Can't put a superuser in an exceptions list.")

                if (role == Role.ANONYMOUS and
                        operation not in
                        Operation.ALLOWED_ANONYMOUS_OPERATIONS):
                    raise UserNotAllowedInExceptionError(
                        "Can't put an anonymous user in an exceptions list "
                        'for operation %s.' % operation)

    def _setNamespacePermissions(self, values, idByUsername):
        """Update L{NamespacePermission}s.

        @param values: A sequence of C{(path, Operation, Policy, exceptions)}
            4-tuples representing L{NamespacePermission}s.
        @param idByUsername: A C{dict} mapping L{User.username}s to
            L{User.id}s with data for all the usernames in the exceptions
            C{list}s.
        """
        result = getNamespacePermissions(values.keys())
        for namespace, permission in result:
            for operation, policy, exceptions in values[namespace.path]:
                exceptions = [idByUsername[username]
                              for username in exceptions]
                permission.set(operation, policy, exceptions)

    def _setTagPermissions(self, values, idByUsername):
        """Update L{TagPermission}s.

        @param values: A sequence of C{(path, Operation, Policy, exceptions)}
            4-tuples representing L{TagPermission}s.
        @param idByUsername: A C{dict} mapping L{User.username}s to
            L{User.id}s with data for all the usernames in the exceptions
            C{list}s.
        """
        result = getTagPermissions(values.keys())
        for tag, permission in result:
            for operation, policy, exceptions in values[tag.path]:
                exceptions = [idByUsername[username]
                              for username in exceptions]
                permission.set(operation, policy, exceptions)

    def get(self, values):
        """Get permissions matching pairs of paths and L{Operation}s.

        @param values: A sequence of C{(path, Operation)} tuples.
        @raise FeatureError: Raised if the given list of values is empty.
        @return: A C{dict} that maps C{(path, Operation)} tuples to C{(Policy,
            exceptions)} tuples.  Example::

              {(<path>, <operation>): (<policy>, ['user1', 'user2', ...]), ...}
        """
        if not values:
            raise FeatureError("Can't get an empty list of permissions.")

        # Get the requested permission data.
        permissions = {}
        namespaceValues = []
        tagValues = []
        for path, operation in values:
            if operation in Operation.NAMESPACE_OPERATIONS:
                namespaceValues.append((path, operation))
            else:
                tagValues.append((path, operation))
        if namespaceValues:
            permissions.update(self._getNamespacePermissions(namespaceValues))
        if tagValues:
            permissions.update(self._getTagPermissions(tagValues))

        # Translate User.id's in the exception lists to User.username's.
        userIDs = set()
        for key, (policy, exceptions) in permissions.iteritems():
            userIDs.update(exceptions)
        usernames = dict(getUsers(ids=userIDs).values(User.id, User.username))
        for key, (policy, exceptions) in permissions.items():
            permissions[key] = (
                policy, [usernames[userID] for userID in exceptions])

        return permissions

    def _getNamespacePermissions(self, values):
        """Get L{NamespacePermission}s for the specified values.

        @param values: A sequence of C{(Namespace.path, Operation)} 2-tuples.
        @return: A C{dict} that maps C{(Namespace.path, Operation)} tuples to
            C{(Policy, exceptions)} 2-tuples, matching the following format::

              {(<path>, <operation>): (<policy>, [<user-id>, ...]), ...}
        """
        permissionIndex = {}
        paths = set(path for path, operation in values)
        for namespace, permission in readonly(getNamespacePermissions(paths)):
            permissionIndex[namespace.path] = permission

        permissions = {}
        for path, operation in values:
            permission = permissionIndex[path]
            policy, exceptions = permission.get(operation)
            permissions[(path, operation)] = (policy, exceptions)
        return permissions

    def _getTagPermissions(self, values):
        """Get L{TagPermission}s for the specified values.

        @param values: A sequence of C{(Tag.path, Operation)} 2-tuples.
        @return: A C{dict} that maps C{(Tag.path, Operation)} 2-tuples to
            C{(Policy, exceptions)} 2-tuples, matching the following format::

              {(<path>, <operation>): (<policy>, [<user-id>, ...]), ...}
        """
        permissionIndex = {}
        paths = set(path for path, operation in values)
        for tag, permission in readonly(getTagPermissions(paths)):
            permissionIndex[tag.path] = permission

        permissions = {}
        for path, operation in values:
            permission = permissionIndex[path]
            policy, exceptions = permission.get(operation)
            permissions[(path, operation)] = (policy, exceptions)
        return permissions


class PermissionCheckerAPI(object):
    """The public API to permission checking-related logic in the model."""

    def getNamespacePermissions(self, paths):
        """Get L{Permission}s for L{Namespace.path}s.

        @param paths: A sequence of L{Namespace.path}s to retrieve
            L{Permission}s for.
        @return: A C{dict} mapping L{Namespace.path}s to L{Permission}
            instances.
        """
        return dict((namespace.path, permission)
                    for namespace, permission
                    in readonly(getNamespacePermissions(paths)))

    def getTagPermissions(self, paths):
        """Get L{Permission}s for L{Tag.path}s.

        @param paths: A sequence of L{Tag.path}s to retrieve L{Permission}s
            for.
        @return: A C{dict} mapping L{Tag.path}s to L{Permission} instances.
        """
        return dict((tag.path, permission)
                    for tag, permission
                    in readonly(getTagPermissions(paths)))

    def getUnknownPaths(self, values):
        """Check if the paths in a sequence of path-operation exist.

        @param values: A sequence of C{(path, Operation)} 2-tuples.
        @raise FeatureError: Raised if an invalid path or L{Operation} is
            given.
        @return: A C{set} with the unknown paths.
        """
        tagPaths = set()
        namespacePaths = set()
        for path, operation in values:
            if path is None:
                raise FeatureError('A path must be provided.')
            elif operation in Operation.TAG_OPERATIONS:
                tagPaths.add(path)
            elif operation in Operation.NAMESPACE_OPERATIONS:
                namespacePaths.add(path)
            else:
                raise FeatureError('Invalid operation %s for the path %r'
                                   % (operation, path))

        if tagPaths:
            existingTags = set(getTags(paths=tagPaths).values(Tag.path))
            unknownTags = tagPaths - existingTags
            unknownTags.discard(u'fluiddb/id')
        else:
            unknownTags = set()

        if namespacePaths:
            result = getNamespaces(paths=namespacePaths).values(Namespace.path)
            existingNamespaces = set(result)
            unknownNamespaces = namespacePaths - existingNamespaces
        else:
            unknownNamespaces = set()

        return unknownTags.union(unknownNamespaces)

    def getUnknownParentPaths(self, unknownPaths):
        """Get a C{dict} mapping unknown paths to their closest L{Namespace}.

        This function finds the closest L{Namespace} parent for the specified
        unknown paths.  It walks back down each path until it finds a parent or
        determines that one doesn't exist.

        @param unknownPaths: A C{set} of unknown L{Tag.path}s and
            L{Namespace.path}s.
        @return: A C{dict} that maps unknown paths to their closest
            L{Namepace.path} parent.
        """
        if not unknownPaths:
            return {}

        hierarchy = getPathHierarchy(unknownPaths)
        existingPaths = getNamespaces(paths=hierarchy).values(Namespace.path)
        existingPaths = set(existingPaths)
        closestParents = {}
        for path in unknownPaths:
            parentPath = getParentPath(path)
            while parentPath is not None:
                if parentPath in existingPaths:
                    closestParents[path] = parentPath
                    break
                parentPath = getParentPath(parentPath)

        return closestParents
