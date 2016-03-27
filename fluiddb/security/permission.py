from fluiddb.cache.permission import (
    CachingPermissionAPI, CachingPermissionCheckerAPI)
from fluiddb.data.path import getParentPath
from fluiddb.data.permission import Operation
from fluiddb.data.user import Role
from fluiddb.model.exceptions import UnknownPathError
from fluiddb.security.exceptions import PermissionDeniedError


class SecurePermissionAPI(object):
    """The public API to secure permission-related functionality.

    @param user: The L{User} to perform operations on behalf of.
    """

    def __init__(self, user):
        self._user = user
        self._permissions = CachingPermissionAPI(user)

    def get(self, values):
        """See L{PermissionAPI.get}.

        @raise PermissionDeniedError: Raised if the user is not authorized to
            see the specified permissions.
        """
        self._checkPermissions(values)
        return self._permissions.get(values)

    def set(self, values):
        """See L{PermissionAPI.set}.

        @raise PermissionDeniedError: Raised if the user is not authorized to
            change the specified permissions.
        """
        self._checkPermissions([(path, operation)
                                for path, operation, _, _ in values])
        return self._permissions.set(values)

    def _checkPermissions(self, values):
        """Check C{CONTROL} permissions for a set of path-operation pairs.

        @param values: A sequence of C{(path, Operation)} 2-tuples with the
            that should be checked.
        @raise PermissionDeniedError: Raised if the user doesn't have
            C{CONTROL} permissions for a given path-L{Operation} pair.
        @raise RuntimeError: Raised if an invalid L{Operation} is provided.
        """
        pathsAndOperations = set()
        for path, operation in values:
            if operation in [Operation.WRITE_TAG_VALUE,
                             Operation.READ_TAG_VALUE,
                             Operation.DELETE_TAG_VALUE,
                             Operation.CONTROL_TAG_VALUE]:
                pathsAndOperations.add((path, Operation.CONTROL_TAG_VALUE))
            elif operation in [Operation.UPDATE_TAG, Operation.DELETE_TAG,
                               Operation.CONTROL_TAG]:
                pathsAndOperations.add((path, Operation.CONTROL_TAG))
            elif operation in Operation.NAMESPACE_OPERATIONS:
                pathsAndOperations.add((path, Operation.CONTROL_NAMESPACE))
            else:
                raise RuntimeError('Invalid operation %r.' % operation)

        deniedOperations = checkPermissions(self._user, pathsAndOperations)
        if deniedOperations:
            raise PermissionDeniedError(self._user.username, deniedOperations)


def checkPermissions(user, values):
    """Check permissions for a list of path-operation pairs.

    Note that the special C{fluiddb/id} virtual tag is handled as a
    special case.  Specifically, the path presence checking logic doesn't
    raise an L{UnknownPathError} and all tag related permission are always
    granted (because permissions for C{fluiddb/id} are never checked).
    This isn't ideal, but for now it's the behaviour in place.

    @param user: The user to check the permissions for.
    @param values: A sequence of C{(path, Operation)} 2-tuples
        representing the actions to check.
    @raise FeatureError: Raised if the given C{list} of values is empty or
        if one of the given actions is invalid.
    @raise UnknownUserError: Raised if a user don't exist for user
        operations.
    @raise UnknownPathError: Raised if any of the given paths doesn't
        exist.
    @return: A C{list} of C{(path, Operation)} 2-tuples that represent
        denied actions.
    """
    if not values:
        return []

    api = CachingPermissionCheckerAPI()
    if user.isSuperuser():
        checker = SuperuserPermissionChecker(api)
    elif user.isAnonymous():
        checker = AnonymousPermissionChecker(api, user)
    else:
        checker = UserPermissionChecker(api, user)
    return checker.check(values)


class PermissionCheckerBase(object):
    """Base class for permission checkers."""

    PASSTHROUGH_OPERATIONS = [Operation.WRITE_TAG_VALUE,
                              Operation.CREATE_NAMESPACE]

    def _getDeniedOperations(self, values):
        """Get information about denied permissions.

        All operations are assumed to be denied to begin with.  Each requested
        L{Operation} is checked against a permission to determine if access
        should be granted.  Operations that are not explicitly granted access
        by a permission are denied.

        The following rules are used to determine whether access should be
        granted or denied:

         - Access is always granted for L{Operation}s on the special
           C{fluiddb/id} virtual tag.

         - C{Operation.CREATE_NAMESPACE} and C{Operation.WRITE_TAG_VALUE}
           operations on unknown L{Tag.path}s and L{Namespace.path}s are
           allowed if the L{User} has the related permission on the nearest
           parent L{Namespace}.  The model layer automatically creates missing
           L{Namespace}s and L{Tag}s, so we need to make sure that the parents
           of implicit paths provide access for the user to create children.

         - Finally, access is only given if a L{NamespacePermission} or
           L{TagPermission} explicitly grant the L{User} access to perform the
           L{Operation} on the L{Tag} or L{Namespace}.

        @param values: A sequence of C{(path, Operation)} 2-tuples
            representing actions that should be checked.
        @raise UnknownPathError: Raised if any of the given paths doesn't
            exist (and the L{User} doesn't have permission to create them).
        @return: A C{list} of C{(path, Operation)} 2-tuples that represent
            denied actions.
        """
        deniedTagOperations = set()
        deniedNamespaceOperations = set()
        unknownPaths = self._api.getUnknownPaths(values)
        parentPaths = self._api.getUnknownParentPaths(unknownPaths)
        remainingUnknownPaths = set(unknownPaths)
        for path, operation in values:
            if path == u'fluiddb/id':
                continue
            if (operation in self.PASSTHROUGH_OPERATIONS
                    and path in unknownPaths):
                parentPath = parentPaths.get(path)
                if parentPath:
                    remainingUnknownPaths.remove(path)
                    deniedNamespaceOperations.add(
                        (parentPath, Operation.CREATE_NAMESPACE))
            elif operation in Operation.NAMESPACE_OPERATIONS:
                deniedNamespaceOperations.add((path, operation))
            elif path not in unknownPaths:
                deniedTagOperations.add((path, operation))
        if remainingUnknownPaths:
            raise UnknownPathError(remainingUnknownPaths)

        deniedTagOperations = self._getDeniedTagOperations(deniedTagOperations)
        deniedTagOperations.update(
            self._getDeniedNamespaceOperations(deniedNamespaceOperations))
        return list(deniedTagOperations)

    def _getDeniedNamespaceOperations(self, values):
        """Determine whether L{Namespace} L{Operation}s are allowed.

        @param values: A C{set} of C{(Namespace.path, Operation)} 2-tuples
            representing actions that should be checked.
        @return: A C{set} of C{(Namespace.path, Operation)} 2-tuples that
            represent denied actions.
        """
        if not values:
            return set()

        paths = set(path for path, operation in values)
        permissions = self._api.getNamespacePermissions(paths)
        return values - self._getGrantedOperations(permissions, values)

    def _getDeniedTagOperations(self, values):
        """Determine whether L{Tag} L{Operation}s are allowed.

        @param values: A C{set} of C{(Tag.path, Operation)} 2-tuples
            representing actions that should be checked.
        @return: A C{set} of C{(Tag.path, Operation)} 2-tuples that represent
            denied actions.
        """
        if not values:
            return set()

        paths = set(path for path, operation in values)
        permissions = self._api.getTagPermissions(paths)
        return values - self._getGrantedOperations(permissions, values)

    def _getGrantedOperations(self, permissions, values):
        """Determine which operations are granted given a set of permissions.

        @param permissions: A C{dict} mapping paths to L{PermissionBase}
            instances.
        @param values: A C{set} of C{(path, Operation)} 2-tuples representing
            actions that should be checked.
        @return: A C{set} of C{(path, Operation)} 2-tuples that represent
            granted actions.
        """
        allowedOperations = set()
        for path, operation in values:
            permission = permissions.get(path)
            if permission and permission.allow(operation, self._user.id):
                allowedOperations.add((path, operation))
        return allowedOperations


class SuperuserPermissionChecker(PermissionCheckerBase):
    """Permission checker for L{User}s with the L{Role.SUPERUSER} role.

    Permission for all actions is always granted to L{User}s with the
    L{Role.SUPERUSER}.

    @param api: The L{PermissionCheckerAPI} instance to use when performing
       permission checks.
    """

    def __init__(self, api):
        self._api = api

    def check(self, values):
        """Check permissions for a L{User} with the L{Role.SUPERUSER} role.

        @param values: A sequence of C{(path, Operation)} 2-tuples
            representing actions that should be checked.
        @raise UnknownUserError: Raised if a user don't exist for user
            operations.
        @return: A C{list} of C{(path, Operation)} 2-tuples representing
            actions that are denied.
        """
        # Check paths for tag or namespace related operations.
        pathsAndOperations = [(path, operation) for path, operation in values
                              if operation in Operation.PATH_OPERATIONS]
        unknownPaths = self._api.getUnknownPaths(pathsAndOperations)
        if unknownPaths:
            raise UnknownPathError(unknownPaths)
        return []


class AnonymousPermissionChecker(PermissionCheckerBase):
    """Permission checker for L{User}s with the L{Role.ANONYMOUS} role.

    Anonymous users have read-only access to (some) data in Fluidinfo and may
    never perform operations that create new objects.  In particular,
    anonymous users may only perform actions that match an operation in the
    L{Operation.ALLOWED_ANONYMOUS_OPERATIONS} list.

    @param api: The L{PermissionCheckerAPI} instance to use when performing
       permission checks.
    @param user: The anonymous L{User} to perform checks on behalf of.
    """

    def __init__(self, api, user):
        self._api = api
        self._user = user

    def check(self, values):
        """Check permissions for a L{User} with the L{Role.ANONYMOUS} role.

        @param values: A sequence of C{(path, Operation)} 2-tuples
            representing actions that should be checked.
        @return: A C{list} of C{(path, Operation)} 2-tuples representing
            actions that are denied.
        """
        deniedOperations = []
        storedOperations = set()
        for path, operation in values:
            if operation not in Operation.ALLOWED_ANONYMOUS_OPERATIONS:
                deniedOperations.append((path, operation))
                continue
            else:
                storedOperations.add((path, operation))

        if not storedOperations:
            return deniedOperations

        return deniedOperations + self._getDeniedOperations(storedOperations)


class UserPermissionChecker(PermissionCheckerBase):
    """Permission checker for L{User}s with the L{Role.USER} role.

    Normal users have read/write access to data in Fluidinfo as granted by
    L{NamespacePermission}s and L{TagPermission}s.  L{Operation}s in the
    L{Operation.USER_OPERATIONS} list are always denied, as is the ability to
    create or delete root L{Namespace}s.

    @param api: The L{PermissionCheckerAPI} instance to use when performing
       permission checks.
    @param user: The L{User} to perform checks on behalf of.
    """

    def __init__(self, api, user):
        self._api = api
        self._user = user

    def check(self, values):
        """Check permissions for a L{User} with the L{Role.USER} role.

        @param values: A sequence of C{(path, Operation)} 2-tuples
            representing actions that should be checked.
        @raise UnknownUserError: Raised if a user don't exist for user
            operations.
        @return: A C{list} of C{(path, Operation)} 2-tuples representing
            actions that are denied.
        """
        deniedOperations = []
        storedOperations = set()
        for path, operation in values:
            # Create object is always allowed for normal users.
            if operation == Operation.CREATE_OBJECT:
                continue
            # Create root namespaces is always denied for normal users.
            elif path is None and operation == Operation.CREATE_NAMESPACE:
                deniedOperations.append((path, operation))
                continue
            # Delete root namespaces is always denied for normal users.
            elif (path is not None and getParentPath(path) is None
                  and operation == Operation.DELETE_NAMESPACE):
                deniedOperations.append((path, operation))
                continue
            # User managers are always allowed to perform user operations.
            elif (self._user.role == Role.USER_MANAGER
                  and operation in Operation.USER_OPERATIONS):
                continue
            # Updating user data is only allowed for the own user.
            elif (operation == Operation.UPDATE_USER
                  and self._user.username == path):
                continue
            # All other user operations are always denied for normal users.
            elif operation in Operation.USER_OPERATIONS:
                deniedOperations.append((path, operation))
                continue
            else:
                # Operations that have to be checked in the database.
                storedOperations.add((path, operation))

        if not storedOperations:
            return deniedOperations

        return deniedOperations + self._getDeniedOperations(storedOperations)
