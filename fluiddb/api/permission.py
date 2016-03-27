from twisted.internet import defer

from fluiddb.api.util import getCategoryAndAction, getOperation
from fluiddb.common.types_thrift.ttypes import (
    TNonexistentTag, TBadRequest, TNonexistentNamespace, TPathPermissionDenied,
    TPolicyAndExceptions, TInvalidPolicy, TNoSuchUser, TInvalidUsername)
from fluiddb.data.exceptions import UnknownUserError
from fluiddb.data.permission import Operation, Policy
from fluiddb.model.exceptions import (
    UnknownPathError, UserNotAllowedInExceptionError)
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.security.permission import SecurePermissionAPI


class FacadePermissionMixin(object):

    def getPermission(self, session, category, action, path):
        """Get permissions for a given path.

        @param session: The L{AuthenticatedSession} for the request.
        @param category: A C{unicode} indicating the category of the
            permission.
        @param action: A C{unicode} indicating the action of the permission.
        @param path: The L{Namespace.path} or L{Tag.path} to get permissions
            from.
        @raise TBadRequest: Raised if the given C{action} or C{category} are
            invalid.
        @raise TNonexistentNamespace: Raised if the given L{Namespace} path
            does not exist.
        @raise TNonexistentTag: Raised if the given L{Tag} path does not exist.
        @raise TPathPermissionDenied: Raised if the user does not have
            C{CONTROL} permissions on the given L{Namespace} or L{Tag}.
        @return: A C{Deferred} that will fire with a L{TPolicyAndExceptions}
            object containing the policy and exceptions list for the requested
            permission.
        """
        path = path.decode('utf-8')

        try:
            operation = getOperation(category, action)
        except KeyError as error:
            session.log.exception(error)
            error = TBadRequest(
                'Action %r not possible on category %r.' % (action, category))
            return defer.fail(error)

        def run():
            permissions = SecurePermissionAPI(session.auth.user)
            try:
                result = permissions.get([(path, operation)])
            except UnknownPathError as error:
                session.log.exception(error)
                unknownPath = error.paths[0]
                if operation in Operation.TAG_OPERATIONS:
                    raise TNonexistentTag(unknownPath.encode('utf-8'))
                if operation in Operation.NAMESPACE_OPERATIONS:
                    raise TNonexistentNamespace(unknownPath.encode('utf-8'))
                raise
            except PermissionDeniedError as error:
                session.log.exception(error)
                deniedPath, deniedOperation = error.pathsAndOperations[0]
                deniedCategory, deniedAction = getCategoryAndAction(
                    deniedOperation)
                raise TPathPermissionDenied(deniedPath, deniedCategory,
                                            deniedAction)

            policy, exceptions = result[(path, operation)]
            policy = str(policy).lower()
            return TPolicyAndExceptions(policy=policy, exceptions=exceptions)

        return session.transact.run(run)

    def updatePermission(self, session, category, action, path,
                         policyAndExceptions):
        """Update permissions for a given path.

        @param session: The L{AuthenticatedSession} for the request.
        @param category: A C{unicode} indicating the category of the
            permission.
        @param action: A C{unicode} indicating the action of the permission.
        @param path: The L{Namespace.path} or L{Tag.path} to get permissions
            from.
        @param policyAndExceptions: A L{TPolicyAndExceptions} object containing
            the policy and exceptions list for the permission.
        @raise TBadRequest: Raised if the given C{action} or C{category} are
            invalid.
        @raise TInvalidPolicy: Raised if the policy given in
            C{policyAndExceptions} is invalid.
        @raise TNonexistentNamespace: Raised if the given L{Namespace} path
            does not exist.
        @raise TNonexistentTag: Raised if the given L{Tag} path does not exist.
        @raise TPathPermissionDenied: Raised if the user does not have
            C{CONTROL} permissions on the given L{Namespace} or L{Tag}.
        @return: A C{Deferred} that will fire with a C{None} if the operation
            was successful.
        """
        path = path.decode('utf-8')

        try:
            operation = getOperation(category, action)
        except KeyError as error:
            session.log.exception(error)
            error = TBadRequest(
                'Action %r not possible on category %r.' % (action, category))
            return defer.fail(error)

        policy = policyAndExceptions.policy
        if policy not in ('open', 'closed'):
            return defer.fail(TInvalidPolicy())
        policy = Policy.OPEN if policy == 'open' else Policy.CLOSED
        exceptions = policyAndExceptions.exceptions

        def run():
            permissions = SecurePermissionAPI(session.auth.user)
            try:
                permissions.set([(path, operation, policy, exceptions)])
            except UnknownPathError as error:
                session.log.exception(error)
                unknownPath = error.paths[0]
                if operation in Operation.TAG_OPERATIONS:
                    raise TNonexistentTag(unknownPath.encode('utf-8'))
                if operation in Operation.NAMESPACE_OPERATIONS:
                    raise TNonexistentNamespace(unknownPath.encode('utf-8'))
                raise
            except UnknownUserError as error:
                # FIXME There could be more than one unknown username, but
                # TNoSuchUser can only be passed a single username, so we'll
                # only pass the first one.  Ideally, we'd be able to pass all
                # of them.
                raise TNoSuchUser(error.usernames[0].encode('utf-8'))
            except UserNotAllowedInExceptionError as error:
                raise TInvalidUsername(str(error))
            except PermissionDeniedError as error:
                session.log.exception(error)
                deniedPath, deniedOperation = error.pathsAndOperations[0]
                deniedCategory, deniedAction = getCategoryAndAction(
                    deniedOperation)
                raise TPathPermissionDenied(deniedPath, deniedCategory,
                                            deniedAction)

        return session.transact.run(run)
