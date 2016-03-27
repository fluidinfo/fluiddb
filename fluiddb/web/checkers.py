import logging

from twisted.cred import checkers, credentials, error
from twisted.internet import defer
from twisted.python import log
from zope.interface import implements, Interface, Attribute

from fluiddb.application import getConfig
from fluiddb.common.types_thrift.ttypes import TPasswordIncorrect, TNoSuchUser
from fluiddb.util.oauth_credentials import IOAuthCredentials
from fluiddb.util.oauth2_credentials import IOAuth2Credentials


class IFacadeChecker(Interface):

    facadeClient = Attribute("Facade client")


class AnonymousChecker(object):
    """
    A checker that always returns the anonymous user, so that
    unauthenticated access to FluidDB may occur.
    """

    implements(checkers.ICredentialsChecker, IFacadeChecker)
    credentialInterfaces = (credentials.IAnonymous,)

    def requestAvatarId(self, credentials):
        allowAnonymousAccess = getConfig().getboolean('service',
                                                      'allow-anonymous-access')
        if not allowAnonymousAccess:
            return error.UnauthorizedLogin('Invalid credentials')
        return self.facadeClient.createAnonymousSession()


class FacadeChecker(object):

    implements(checkers.ICredentialsChecker, IFacadeChecker)
    credentialInterfaces = (credentials.IUsernamePassword,)

    @defer.inlineCallbacks
    def requestAvatarId(self, credentials):
        """
        Return the avatar id of the avatar which can be accessed using the
        given credentials.

        credentials will be an object with username and password tags.  We
        need to raise an error to indicate failure or return a username to
        indicate success.  requestAvatar will then be called with the
        avatar id we returned.
        """
        try:
            session = yield self.facadeClient.authenticateUserWithPassword(
                credentials.username, credentials.password)
        except (TPasswordIncorrect, TNoSuchUser):
            unauthorizedLogin = error.UnauthorizedLogin('Invalid credentials')
            log.msg('Bad credentials: %r:%r' %
                    (credentials.username, '<sanitized>'))
            raise unauthorizedLogin
        except Exception, e:
            log.msg('requestAvatarId exception authenticating %r/%r.' %
                    (credentials.username, '<sanitized>'))
            log.err(e)
            raise
        else:
            defer.returnValue(session)


class FacadeOAuthChecker(object):

    implements(checkers.ICredentialsChecker, IFacadeChecker)
    credentialInterfaces = (IOAuthCredentials,)

    @defer.inlineCallbacks
    def requestAvatarId(self, credentials):
        """
        Return the avatar id of the avatar which can be accessed using the
        given OAuth credentials.

        @param credentials: A L{IOAuthCredentials} that contains OAuth
            credentials.
        @raise UnauthorizedLogin: if the OAuth credentials don't match the
            L{User}'s.
        """
        try:
            session = yield self.facadeClient.authenticateUserWithOAuth(
                credentials)
        except TPasswordIncorrect:
            logging.info('Bad OAuth credentials: %r:%r' %
                         (credentials.consumerKey, '<sanitized>'))
            raise error.UnauthorizedLogin('Invalid credentials')
        except Exception:
            logging.info('requestAvatarId exception authenticating %r/%r.' %
                         (credentials.consumerKey, '<sanitized>'))
            raise
        else:
            defer.returnValue(session)


class FacadeOAuth2Checker(object):

    implements(checkers.ICredentialsChecker, IFacadeChecker)
    credentialInterfaces = (IOAuth2Credentials,)

    @defer.inlineCallbacks
    def requestAvatarId(self, credentials):
        """
        Return the avatar ID of the avatar which can be accessed using the
        given OAuth credentials.

        @param credentials: A L{IOAuth2Credentials} that contains OAuth
            credentials.
        @raise UnauthorizedLogin: Raised if the OAuth credentials don't match
            the L{User}'s.
        """
        try:
            session = yield self.facadeClient.authenticateUserWithOAuth2(
                credentials)
        except TPasswordIncorrect:
            logging.info('Bad OAuth credentials: %r:%r' %
                         (credentials.consumerKey, '<sanitized>'))
            raise error.UnauthorizedLogin('Invalid credentials')
        except Exception:
            logging.info('requestAvatarId exception authenticating %r/%r.' %
                         (credentials.consumerKey, '<sanitized>'))
            raise
        else:
            defer.returnValue(session)
