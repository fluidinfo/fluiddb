from datetime import datetime, timedelta

from fluiddb.application import getConfig
from fluiddb.data.exceptions import UnknownUserError
from fluiddb.data.oauth import createOAuthConsumer, getOAuthConsumers
from fluiddb.model.exceptions import (
    ExpiredOAuthTokenError, UnknownConsumerError)
from fluiddb.model.user import getUser
from fluiddb.security.authentication import AuthenticationError
from fluiddb.util.minitoken import dataToToken, tokenToData


class OAuthTokenBase(object):
    """Base class for OAuth tokens.

    @param consumer: The L{User} instance representing the L{OAuthConsumer}
        this token gives control to.
    @param user: The L{User} instance representing the user this token gives
        control on behalf of.
    @param now: A C{datetime.utcnow}-like function, used for testing purposes.
    """

    def __init__(self, consumer, user, now=None):
        self.consumer = consumer
        self.user = user
        self.creationTime = now() if now else datetime.utcnow()

    @classmethod
    def decrypt(cls, consumerUser, encryptedToken):
        """Decrypt a token and convert it into a stateful object.

        @param cls: The class representing the token.
        @param consumerUser: The L{User} instance of the consumer that holds
            the token.
        @param: The encrypted token as a C{str}.
        @raise UnknownConsumerError: Raised if C{consumerUser} doesn't have a
            matching L{OAuthConsumer} in the system.
        @raise UnknownUserError: Raised if the L{User} the token provides
            access on behalf of doesn't exist.
        @return: An instance of C{cls}.
        """
        result = getOAuthConsumers(userIDs=[consumerUser.id]).one()
        if result is None:
            raise UnknownConsumerError("'%s' is not a consumer."
                                       % consumerUser.username)
        _, consumer = result
        salt = getConfig().get('oauth', cls.configName)
        secret = salt + consumer.secret
        data = tokenToData(secret, encryptedToken)
        username = data['username'].lower()
        user = getUser(username)
        if user is None:
            raise UnknownUserError([username])
        token = cls(consumerUser, user)
        try:
            token.creationTime = datetime.strptime(data['creationTime'],
                                                   '%Y%m%d-%H%M%S')
        except KeyError:
            token.creationTime = None
        return token

    def encrypt(self):
        """Convert this token into an encrypted blob.

        @return: A encrypted token as a C{str}.
        """
        result = getOAuthConsumers(userIDs=[self.consumer.id]).one()
        if result is None:
            raise UnknownConsumerError("'%s' is not a consumer."
                                       % self.consumer.username)
        _, consumer = result
        salt = getConfig().get('oauth', self.configName)
        secret = salt + consumer.secret
        creationTime = self.creationTime.strftime('%Y%m%d-%H%M%S')
        return dataToToken(secret, {'username': self.user.username,
                                    'creationTime': creationTime})


class OAuthAccessToken(OAuthTokenBase):
    """
    An OAuth access token grants permissions to an L{OAuthConsumer} to act on
    behalf of a L{User}.
    """

    configName = 'access-secret'


class OAuthRenewalToken(OAuthTokenBase):
    """
    An OAuth renewal token may be used by an L{OAuthConsumer} to generate a
    new L{OAuthAccessToken}, to continue to act on behalf of a L{User}.
    """

    configName = 'renewal-secret'


class OAuthConsumerAPI(object):
    """The public API for L{OAuthConsumer}s in the model layer."""

    def register(self, user, secret=None):
        """Register a L{User} (probably an application) as an L{OAuthConsumer}.

        @param user: The L{User} to register.
        @param secret: Optionally a C{str} with the OAuth consumer secret.
        @return: The L{OAuthConsumer} for the specified user.
        """
        return createOAuthConsumer(user, secret)

    def get(self, user):
        """Get the L{OAuthConsumer} associated with the specified L{User}.

        @param user: The L{User} (probably an application) that is a consumer.
        @return: The associated L{OAuthConsumer} instance or C{None} if one
            isn't available.
        """
        result = getOAuthConsumers(userIDs=[user.id]).one()
        if result is not None:
            return result[1]
        return result

    def getAccessToken(self, consumer, user, now=None):
        """
        Get an access token for an L{OAuthConsumer} to make API calls on
        behalf of a L{User}.

        @param consumer: The L{User} consumer to generate an access token for.
        @param user: The L{User} to act on behalf of when the access token is
            used.
        @param now: Optionally, a C{datetime.utcnow}-like function, used for
            testing purposes.
        @raise UnknownConsumerError: Raised if C{consumer} doesn't have a
            matching L{OAuthConsumer} in the system.
        @return: An L{OAuthAccessToken} instance.
        """
        result = getOAuthConsumers(userIDs=[consumer.id]).one()
        if result is None:
            raise UnknownConsumerError("'%s' is not a consumer."
                                       % consumer.username)
        return OAuthAccessToken(consumer, user, now=now)

    def getRenewalToken(self, consumer, user, now=None):
        """
        Get a renewal token for an L{OAuthConsumer} to generate a new access
        token for a L{User}.

        @param consumer: The L{User} consumer to generate a renewal token for.
        @param user: The L{User} to act on behalf of when the renewal token is
            used.
        @param now: Optionally, a C{datetime.utcnow}-like function, used for
            testing purposes.
        @raise UnknownConsumerError: Raised if C{consumer} doesn't have a
            matching L{OAuthConsumer} in the system.
        @return: An L{OAuthRenewalToken} instance.
        """
        result = getOAuthConsumers(userIDs=[consumer.id]).one()
        if result is None:
            raise UnknownConsumerError("'%s' is not a consumer."
                                       % consumer.username)
        return OAuthRenewalToken(consumer, user, now=now)

    def renewToken(self, renewalToken):
        """Use an L{OAuthRenewalToken} to generate a new L{OAuthAccessToken}.

        @param renewalToken: The L{OAuthRenewalToken} to use to generate a new
            L{OAuthAccessToken}.
        @raise ExpiredOAuthTokenError: Raised if C{renewalToken} is expired.
        @raise UnknownConsumerError: Raised if C{consumerUser} doesn't have a
            matching L{OAuthConsumer} in the system.
        @return: An C{(OAuthRenewalToken, OAuthAccessToken)} 2-tuple.
        """
        duration = getConfig().getint('oauth', 'renewal-token-duration')
        duration = timedelta(hours=duration)
        if renewalToken.creationTime < datetime.utcnow() - duration:
            raise ExpiredOAuthTokenError('Renewal token is expired.')
        newRenewalToken = self.getRenewalToken(renewalToken.consumer,
                                               renewalToken.user)
        accessToken = self.getAccessToken(renewalToken.consumer,
                                          renewalToken.user)
        return newRenewalToken, accessToken

    def authenticate(self, oauthCredentials):
        """Verify the given OAuth credentials.

        @param oauthCredentials: The L{OAuthCredentials} that contains the
            OAuth authentication fields.
        @raise UnknownUserError: Raised if the user in the consumer key or in
            the token doesn't exist.
        @raise AuthenticationError: Raised if passed an invalid token or if
            the OAuth credentials can't be verified.
        @return: The L{User} for the OAuth credentials.
        """
        consumerUser = getUser(oauthCredentials.consumerKey)
        if not consumerUser:
            raise UnknownUserError([oauthCredentials.consumerKey])
        oauthConsumer = self.get(consumerUser)

        # Make sure the consumer has been registered.  If so, the
        # oauthConsumer will have a 'secret' attribute.
        try:
            secret = oauthConsumer.secret
        except AttributeError:
            # XXX We should probably log this.
            raise AuthenticationError(oauthCredentials.consumerKey)

        try:
            token = OAuthAccessToken.decrypt(consumerUser,
                                             oauthCredentials.token)
        except ValueError:
            raise AuthenticationError(oauthCredentials.consumerKey)
        if oauthCredentials.verifySignature(secret):
            return token.user
        else:
            raise AuthenticationError(token.user.username)
