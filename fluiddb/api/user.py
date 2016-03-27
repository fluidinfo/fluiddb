from twisted.internet.defer import fail

from fluiddb.api.util import getCategoryAndAction
from fluiddb.common.types_thrift.ttypes import (
    TUser, TBadRequest, TNoSuchUser, TPathPermissionDenied)
from fluiddb.data.exceptions import UnknownUserError
from fluiddb.data.user import Role
from fluiddb.model.exceptions import NotEmptyError
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.security.user import SecureUserAPI


class FacadeUserMixin(object):

    def getUser(self, session, username):
        """Get information about a L{User}.

        @param session: The L{AuthenticatedSession} for the request.
        @param username: The L{User.username} to get information about.
        @raise TNoSuchUser: Raised if the specified L{User} doesn't exist.
        @return: A C{Deferred} that will fire with a L{TUser} object
            representing the L{User}.
        """
        username = username.decode('utf-8').lower()

        def run():
            users = SecureUserAPI(session.auth.user)
            result = users.get([username])
            if not result:
                raise TNoSuchUser(username.encode('utf-8'))
            else:
                return TUser(username=username,
                             name=result[username]['name'],
                             role=str(result[username]['role']),
                             objectId=str(result[username]['id']))

        return session.transact.run(run)

    def updateUser(self, session, info):
        """Update information about a L{User}.

        @param session: The L{AuthenticatedSession} for the request.
        @param info: A L{TUserUpdate} with information about a L{User}.
        @raise TNoSuchUser: Raised if the specified L{User} doesn't exist.
        @raise TPathPermissionDenied: Raised if the L{User} requesting the
            update is not a superuser.
        @return: A C{Deferred} that will fire after the update has been
            performed.
        """
        info.username = info.username.decode('utf-8').lower()
        if info.password is not None:
            info.password = info.password.decode('utf-8')
        if info.name is not None:
            info.name = info.name.decode('utf-8')
        if info.email is not None:
            info.email = info.email.decode('utf-8')
        if info.role is not None:
            try:
                info.role = Role.fromName(info.role)
            except LookupError:
                return fail(TBadRequest('Invalid role given.'))

        def run():
            try:
                [(objectID, _)] = SecureUserAPI(session.auth.user).set(
                    [(info.username, info.password, info.name, info.email,
                      info.role)])
            except UnknownUserError as error:
                session.log.exception(error)
                raise TNoSuchUser(info.username.encode('utf-8'))
            except PermissionDeniedError as error:
                session.log.exception(error)
                deniedPath, operation = error.pathsAndOperations[0]
                deniedPath = deniedPath.encode('utf-8')
                category, action = getCategoryAndAction(operation)
                raise TPathPermissionDenied(category, action, deniedPath)

            return str(objectID)

        return session.transact.run(run)

    def deleteUser(self, session, username):
        """Get information about a L{Tag}.

        @param session: The L{AuthenticatedSession} for the request.
        @param username: The L{User.username} to delete.
        @raise TNoSuchUser: Raised if the specified L{User} doesn't exist.
        @raise TPathPermissionDenied: Raised if the L{User} requesting the
            update is not a superuser.
        @return: A C{Deferred} that will fire after the delete has been
            performed.
        """
        username = username.decode('utf-8').lower()

        def run():
            try:
                SecureUserAPI(session.auth.user).delete([username])
            except UnknownUserError as error:
                session.log.exception(error)
                raise TNoSuchUser(username)
            except PermissionDeniedError as error:
                session.log.exception(error)
                deniedPath, operation = error.pathsAndOperations[0]
                deniedPath = deniedPath.encode('utf-8')
                category, action = getCategoryAndAction(operation)
                raise TPathPermissionDenied(category, action, deniedPath)
            except NotEmptyError as error:
                session.log.exception(error)
                raise TBadRequest("Can't delete user %r because they have "
                                  'data.' % username)

        return session.transact.run(run)
