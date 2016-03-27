from random import sample

from fluiddb.data.exceptions import UnknownUserError
from fluiddb.data.system import createSystemData
from fluiddb.data.user import getUsers, ALPHABET
from fluiddb.model.oauth import (
    OAuthAccessToken, OAuthRenewalToken, OAuthConsumerAPI,
    UnknownConsumerError)
from fluiddb.model.user import UserAPI, getUser
from fluiddb.security.exceptions import InvalidOAuthTokenError
from fluiddb.security.oauth import SecureOAuthConsumerAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    ConfigResource, DatabaseResource, CacheResource)


class SecureOAuthConsumerAPITest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureOAuthConsumerAPITest, self).setUp()
        createSystemData()
        secret = ''.join(sample(ALPHABET, 16))
        self.config.set('oauth', 'access-secret', secret)

    def testRenewToken(self):
        """
        L{SecureOAuthConsumerAPI.renewToken} generates a new
        L{OAuthRenewalToken} and L{OAuthAccessToken}, given a valid
        L{OAuthRenewalToken}.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumer = getUser(u'consumer')
        user = getUser(u'user')

        api = OAuthConsumerAPI()
        api.register(consumer)
        token = api.getRenewalToken(consumer, user).encrypt()
        encryptedRenewalToken, encryptedAccessToken = (
            SecureOAuthConsumerAPI().renewToken(u'consumer', token))
        renewalToken = OAuthRenewalToken.decrypt(consumer,
                                                 encryptedRenewalToken)
        accessToken = OAuthAccessToken.decrypt(consumer, encryptedAccessToken)
        self.assertTrue(isinstance(renewalToken, OAuthRenewalToken))
        self.assertIdentical(consumer, renewalToken.consumer)
        self.assertIdentical(user, renewalToken.user)
        self.assertTrue(isinstance(accessToken, OAuthAccessToken))
        self.assertIdentical(consumer, accessToken.consumer)
        self.assertIdentical(user, accessToken.user)

    def testRenewTokenWithUnknownConsumer(self):
        """
        L{SecureOAuthConsumerAPI.renewToken} raises an L{UnknownConsumerError}
        if an L{OAuthRenewalToken} for an unknown consumer is used to generate
        a new L{OAuthAccessToken}.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumer = getUser(u'consumer')
        user = getUser(u'user')

        api = OAuthConsumerAPI()
        api.register(consumer)
        token = api.getRenewalToken(consumer, user).encrypt()
        getUsers(usernames=[u'consumer']).remove()
        self.assertRaises(UnknownConsumerError,
                          SecureOAuthConsumerAPI().renewToken, u'consumer',
                          token)

    def testRenewTokenWithUnknownUser(self):
        """
        L{SecureOAuthConsumerAPI.renewToken} raises an L{UnknownUserError} if
        an L{OAuthRenewalToken} for an unknown L{User} is used to generate a
        new L{OAuthAccessToken}.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumer = getUser(u'consumer')
        user = getUser(u'user')

        api = OAuthConsumerAPI()
        api.register(consumer)
        token = api.getRenewalToken(consumer, user).encrypt()
        getUsers(usernames=[u'user']).remove()
        self.assertRaises(UnknownUserError,
                          SecureOAuthConsumerAPI().renewToken, u'consumer',
                          token)

    def testRenewTokenWithInvalidRenewalToken(self):
        """
        L{SecureOAuthConsumerAPI.renewToken} raises an
        L{InvalidOAuthTokenError} if the specified encrypted
        L{OAuthRenewalToken} can't be decrypted.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumer = getUser(u'consumer')
        OAuthConsumerAPI().register(consumer)
        self.assertRaises(InvalidOAuthTokenError,
                          SecureOAuthConsumerAPI().renewToken, u'consumer',
                          'invalid')
