from fluiddb.data.exceptions import (
    DuplicateUserError, UnknownUserError, MalformedUsernameError)
from fluiddb.model.oauth import OAuthConsumerAPI
from fluiddb.model.user import UserAPI
from fluiddb.common.types_thrift.ttypes import (
    TNoSuchUser, TPasswordIncorrect, TPathPermissionDenied,
    TUserAlreadyExists, TInvalidUsername, TUsernameTooLong)
from fluiddb.security.authentication import AuthenticationError, authenticate
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.security.user import SecureUserAPI


class AuthenticatedSession(object):
    """Represents a Fluidinfo session.

    @param username: The username for the user owning the session.
    @param objectId: The objectID of the user.
    """

    def __init__(self, username=None, objectId=None):
        self.username = username
        self.objectId = objectId


class FacadeAuthMixin(object):

    def createAnonymousSession(self):
        """Create a session for an anonymous user.

        @return: A C{Deferred} that will fire with an L{AuthenticatedSession}.
        """
        session = self._factory.create(self._transact)
        session.start()

        def run():
            result = UserAPI().get([u'anon'])
            session.auth.login(u'anon', result[u'anon']['id'])
            return session

        return session.transact.run(run)

    def createUserWithPassword(self, session, username, password, name, email):
        """Create a new L{User}.

        @param session: The L{AuthenticatedSession} for the request.
        @param username: The C{str} username for the new L{User}.
        @param password: The C{str} password for the new L{User}.
        @param name: The C{str} full name for the new L{User}.
        @param email: The C{str} email address for the new L{User}.
        @raise TPathPermissionDenied: Raised if the requesting user doesn't
            have permission to create users.
        @raise TUserAlreadyExists: Raised if the given username is already
            present in the database.
        @return: A C{Deferred} that will fire with the object ID for the new
            L{User}.
        """
        username = username.decode('utf-8').lower()
        password = password.decode('utf-8')
        name = name.decode('utf-8')
        email = email.decode('utf-8')

        def run():
            secureUserAPI = SecureUserAPI(session.auth.user)
            values = [(username, password, name, email)]
            try:
                [(objectID, _)] = secureUserAPI.create(values)
            except MalformedUsernameError as error:
                session.log.exception(error)
                # This looks weird, but I think it's better to keep only one
                # exception for bad usernames in the model layer.
                if len(username) > 128:
                    raise TUsernameTooLong(username.encode('utf-8'))
                else:
                    raise TInvalidUsername(username.encode('utf-8'))
            except DuplicateUserError as error:
                session.log.exception(error)
                raise TUserAlreadyExists(username.encode('utf-8'))
            except PermissionDeniedError as error:
                session.log.exception(error)
                raise TPathPermissionDenied()
            return str(objectID)

        return session.transact.run(run)

    def authenticateUserWithPassword(self, username, password):
        """Authenticate a user.

        @param username: A UTF-8 C{str} containing the username from the
            credentials.
        @param password: A UTF-8 C{str} containing the password from the
            credentials.
        @raise TNoSuchUser: if the username doesn't exist in the database.
        @raise TPasswordIncorrect: if the given password doesn't match the
            L{User}'s.
        @return: A C{Deferred} that will fire with an L{AuthenticatedSession}.
        """
        session = self._factory.create(self._transact)
        session.start()
        username = username.decode('utf-8').lower()
        password = password.decode('utf-8')

        def run():
            try:
                user = authenticate(username, password)
            except AuthenticationError as error:
                session.log.exception(error)
                session.stop()
                raise TPasswordIncorrect()
            except UnknownUserError as error:
                session.log.exception(error)
                session.stop()
                raise TNoSuchUser(username.encode('utf-8'))
            else:
                session.auth.login(user.username, user.objectID)
                return session

        return session.transact.run(run)

    def authenticateUserWithOAuth(self, credentials):
        """Authenticate a user using OAuth credentials.

        @param credentials: An L{IOAuthCredentials} that can be verified.
        @raise TNoSuchUser: if the given username doesn't exist in the
            database.
        @raise TPasswordIncorrect: if the given credentials don't match
            the L{User}'s.
        @return: A C{Deferred} that will fire with an L{AuthenticatedSession}.
        """
        session = self._factory.create(self._transact)
        session.start()

        credentials.consumerKey = credentials.consumerKey.lower()

        def run():
            try:
                user = OAuthConsumerAPI().authenticate(credentials)
            except AuthenticationError as error:
                session.log.exception(error)
                raise TPasswordIncorrect()
            except UnknownUserError as error:
                raise TNoSuchUser(error.usernames[0].encode('utf-8'))
            else:
                session.auth.login(user.username, user.objectID)
                return session

        return session.transact.run(run)

    def authenticateUserWithOAuth2(self, credentials):
        """Authenticate a user.

        @param credentials: An L{OAuth2Credentials} instance.
        @raise TNoSuchUser: if the given username or the username in the
            token (if any) doesn't exist in the database.
        @raise TPasswordIncorrect: if the given password doesn't match the
            L{User}'s or if the data in the token (if any) was somehow invalid.
        @return: A C{Deferred} that will fire with an L{AuthenticatedSession}.
        """
        session = self._factory.create(self._transact)
        session.start()

        credentials.consumerKey = credentials.consumerKey.lower()

        def run():
            # Check the consumer username and password if this is not an
            # anonymous request.
            if credentials.consumerKey != u'anon':
                try:
                    user = authenticate(credentials.consumerKey,
                                        credentials.consumerPassword)
                except AuthenticationError as error:
                    session.log.exception(error)
                    raise TPasswordIncorrect()
                except UnknownUserError as error:
                    session.log.exception(error)
                    raise TNoSuchUser(credentials.consumerKey.encode('utf-8'))

            # The Consumer has been authenticated (or was anonymous). Use
            # the OAuthConsumerAPI to get the username the request is being
            # made for from the OAuth access token.
            try:
                user = OAuthConsumerAPI().authenticate(credentials)
            except AuthenticationError as error:
                session.log.exception(error)
                raise TPasswordIncorrect()
            except UnknownUserError as error:
                raise TNoSuchUser(error.usernames[0].encode('utf-8'))

            session.auth.login(user.username, user.objectID)
            return session

        return session.transact.run(run)
