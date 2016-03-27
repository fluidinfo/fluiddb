from datetime import datetime, timedelta
from random import sample

from fluiddb.application import getConfig
from fluiddb.data.exceptions import UnknownUserError
from fluiddb.data.oauth import OAuthConsumer
from fluiddb.data.system import createSystemData
from fluiddb.data.user import getUsers, ALPHABET
from fluiddb.model.exceptions import ExpiredOAuthTokenError
from fluiddb.model.oauth import (
    OAuthAccessToken, OAuthRenewalToken, OAuthConsumerAPI,
    UnknownConsumerError)
from fluiddb.model.user import UserAPI, getUser
from fluiddb.security.authentication import AuthenticationError
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import ConfigResource, DatabaseResource
from fluiddb.util.minitoken import dataToToken
from fluiddb.util.oauth_credentials import OAuthCredentials
from fluiddb.util.oauth2_credentials import OAuth2Credentials


class OAuthAccessTokenBaseTestMixin(object):

    def testInstantiate(self):
        """An OAuth token contains a consumer, user and creation time."""
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumer = getUser(u'consumer')
        user = getUser(u'user')
        now = datetime.utcnow()

        token = self.cls(consumer, user, lambda: now)
        self.assertEqual(consumer, token.consumer)
        self.assertEqual(user, token.user)
        self.assertEqual(now, token.creationTime)

    def testEncryptAndDecrypt(self):
        """
        An OAuth token can be encrypted into a C{str} blob and then decrypted
        back into a stateful object.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumer = getUser(u'consumer')
        user = getUser(u'user')
        # Microseconds aren't encoded in the token so we remove them from the
        # cooked time we provide in the first place to ease assertion logic.
        now = datetime.utcnow().replace(microsecond=0)
        OAuthConsumerAPI().register(consumer)

        token1 = self.cls(consumer, user, lambda: now)
        token2 = self.cls.decrypt(consumer, token1.encrypt())
        self.assertEqual(token2.consumer, token1.consumer)
        self.assertEqual(token2.user, token1.user)
        self.assertEqual(token2.creationTime, token1.creationTime)

    def testEncryptTokenWithUnknownConsumer(self):
        """
        L{OAuthTokenBase.encrypt} raises an L{UnknownConsumerError} if the
        consumer specified in the token doesn't have a matching
        L{OAuthConsumer} object.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumer = getUser(u'consumer')
        user = getUser(u'user')

        token = self.cls(consumer, user)
        self.assertRaises(UnknownConsumerError, token.encrypt)

    def testDecryptTokenWithUnknownConsumer(self):
        """
        L{OAuthTokenBase.decrypt} raises an L{UnknownConsumerError} if the
        consumer specified in the token doesn't have a matching
        L{OAuthConsumer} object.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumer = getUser(u'consumer')
        user = getUser(u'user')
        OAuthConsumerAPI().register(consumer)

        encryptedToken = self.cls(consumer, user).encrypt()
        # Deleting the consumer will cause an UnknownConsumerError when we try
        # to decrypt the token.
        self.store.find(OAuthConsumer).remove()
        self.assertRaises(UnknownConsumerError, self.cls.decrypt, consumer,
                          encryptedToken)

    def testDecryptTokenWithUnknownUser(self):
        """
        L{OAuthTokenBase.decrypt} raises an L{UnknownUserError} if the L{User}
        specified in the token doesn't exist.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumer = getUser(u'consumer')
        user = getUser(u'user')
        OAuthConsumerAPI().register(consumer)

        encryptedToken = self.cls(consumer, user).encrypt()
        # Deleting the user will cause an UnknownUserError when we try to
        # decrypt the token.
        getUsers(usernames=[u'user']).remove()
        self.assertRaises(UnknownUserError, self.cls.decrypt, consumer,
                          encryptedToken)

    def testDecryptTokenWithoutCreationTime(self):
        """
        L{OAuthTokenBase.decrypt} correctly decrypts tokens without a
        C{creationTime} field, since old OAuth tokens didn't have these.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumerUser = getUser(u'consumer')
        consumer = OAuthConsumerAPI().register(consumerUser)

        salt = getConfig().get('oauth', self.cls.configName)
        secret = salt + consumer.secret
        encryptedToken = dataToToken(secret, {'username': u'user'})
        token = self.cls.decrypt(consumerUser, encryptedToken)
        self.assertIdentical(None, token.creationTime)


class OAuthAccessTokenTest(OAuthAccessTokenBaseTestMixin, FluidinfoTestCase):

    cls = OAuthAccessToken
    resources = [('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(OAuthAccessTokenTest, self).setUp()
        createSystemData()
        secret = ''.join(sample(ALPHABET, 16))
        self.config.set('oauth', 'access-secret', secret)


class OAuthRenewalTokenTest(OAuthAccessTokenBaseTestMixin, FluidinfoTestCase):

    cls = OAuthRenewalToken
    resources = [('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(OAuthRenewalTokenTest, self).setUp()
        createSystemData()
        secret = ''.join(sample(ALPHABET, 16))
        self.config.set('oauth', 'renewal-secret', secret)


class OAuthConsumerAPITest(FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(OAuthConsumerAPITest, self).setUp()
        createSystemData()
        secret = ''.join(sample(ALPHABET, 16))
        self.config.set('oauth', 'access-secret', secret)

    def testRegister(self):
        """
        L{OAuthConsumerAPI.register} creates a new L{OAuthConsumer} so that a
        L{User} (most likely an application) can make OAuth calls to
        Fluidinfo.
        """
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        user = getUser(u'user')
        consumer = OAuthConsumerAPI().register(user)
        self.assertTrue(isinstance(consumer, OAuthConsumer))
        self.assertIdentical(user, consumer.user)

    def testGetWithoutMatch(self):
        """
        L{OAuthConsumerAPI.get} returns C{None} if the specified L{User} isn't
        an OAuth consumer.
        """
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        user = getUser(u'user')
        self.assertIdentical(None, OAuthConsumerAPI().get(user))

    def testGet(self):
        """
        L{OAuthConsumerAPI.get} returns the L{OAuthConsumer} associated with
        the specified L{User}.
        """
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        user = getUser(u'user')
        consumer = OAuthConsumerAPI().register(user)
        self.assertIdentical(consumer, OAuthConsumerAPI().get(user))

    def testGetAccessToken(self):
        """
        L{OAuthConsumerAPI.getAccessToken} returns an L{OAuthAccessToken} for
        a consumer to act on behalf of a L{User}.  It includes the consumer,
        the user to act on behalf of, and the creation time, after which the
        token will not be accepted.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumerUser = getUser(u'consumer')
        user = getUser(u'user')

        now = datetime.utcnow()
        api = OAuthConsumerAPI()
        api.register(consumerUser)
        token = api.getAccessToken(consumerUser, user, now=lambda: now)
        self.assertTrue(isinstance(token, OAuthAccessToken))
        self.assertIdentical(consumerUser, token.consumer)
        self.assertIdentical(user, token.user)
        self.assertEqual(now, token.creationTime)

    def testGetAccessTokenWithoutConsumer(self):
        """
        L{OAuthConsumerAPI.getAccessToken} raised an L{UnknownConsumerError}
        if an L{OAuthConsumer} is not available for the specified L{User}
        consumer.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumerUser = getUser(u'consumer')
        user = getUser(u'user')

        now = datetime.utcnow()
        api = OAuthConsumerAPI()
        self.assertRaises(UnknownConsumerError, api.getAccessToken,
                          consumerUser, user, now=lambda: now)

    def testGetRenewalToken(self):
        """
        L{OAuthConsumerAPI.getRenewalToken} returns an L{OAuthRenewalToken} for
        a consumer to act on behalf of a L{User}.  It includes the consumer,
        the user to act on behalf of, and the creation time, after which the
        token will not be accepted.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumerUser = getUser(u'consumer')
        user = getUser(u'user')

        now = datetime.utcnow()
        api = OAuthConsumerAPI()
        api.register(consumerUser)
        token = api.getRenewalToken(consumerUser, user, now=lambda: now)
        self.assertTrue(isinstance(token, OAuthRenewalToken))
        self.assertIdentical(consumerUser, token.consumer)
        self.assertIdentical(user, token.user)
        self.assertEqual(now, token.creationTime)

    def testGetRenewalTokenWithoutConsumer(self):
        """
        L{OAuthConsumerAPI.getRenewalToken} raised an L{UnknownConsumerError}
        if an L{OAuthConsumer} is not available for the specified L{User}
        consumer.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumerUser = getUser(u'consumer')
        user = getUser(u'user')

        now = datetime.utcnow()
        api = OAuthConsumerAPI()
        self.assertRaises(UnknownConsumerError, api.getRenewalToken,
                          consumerUser, user, now=lambda: now)

    def testAuthenticateOAuth(self):
        """
        L{OAuthConsumerAPI.authenticate} returns the L{User} when passed valid
        L{OAuthCredentials}.  In the case of OAuth Echo, and in the case of
        this test, a consumer makes a request using a token that grants it
        access to act on behalf of a particular user.
        """
        UserAPI().create([(u'consumer', u'password', u'Consumer',
                           u'consumer@example.com')])
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        consumer = getUser(u'consumer')
        user = getUser(u'user')

        api = OAuthConsumerAPI()
        api.register(consumer, secret='abyOTsAfo9MVN0qz')
        token = api.getAccessToken(consumer, user)
        timestamp = 1314976811
        headers = {'header1': 'foo'}
        arguments = 'argument1=bar'
        signature = 'Sno1ocDhYv9vwJnEJATE3cmUvSo='
        nonce = 'nonce'
        credentials = OAuthCredentials(
            'fluidinfo.com', consumer.username, token.encrypt(), 'HMAC-SHA1',
            signature, timestamp, nonce, 'GET', u'https://fluidinfo.com/foo',
            headers, arguments)
        self.assertIdentical(user, api.authenticate(credentials))

    def testAuthenticateOAuth2(self):
        """
        L{OAuthConsumerAPI.authenticate} returns the L{User} when passed valid
        L{OAuth2Credentials}.  In the case of OAuth Echo, and in the case of
        this test, a consumer makes a request using a token that grants it
        access to act on behalf of a particular user.
        """
        UserAPI().create([(u'consumer', u'password', u'Consumer',
                           u'consumer@example.com')])
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        consumer = getUser(u'consumer')
        user = getUser(u'user')

        api = OAuthConsumerAPI()
        api.register(consumer, secret='abyOTsAfo9MVN0qz')
        token = api.getAccessToken(consumer, user)
        credentials = OAuth2Credentials(u'consumer', u'secret1',
                                        token.encrypt())
        self.assertIdentical(user, api.authenticate(credentials))

    def testAuthenticateOAuthWithUnknownUser(self):
        """
        L{OAuthConsumerAPI.authenticate} raises a L{UnknownUserError} exception
        if the user in the L{OAuthCredentials} token doesn't exist.
        """
        UserAPI().create([(u'user1', u'secret1', u'User1',
                           u'user1@example.com')])
        user1 = getUser(u'user1')

        oauthConsumerAPI = OAuthConsumerAPI()
        consumer = oauthConsumerAPI.register(user1, secret='abyOTsAfo9MVN0qz')

        timestamp = 1314976811
        headers = {'header1': 'foo'}
        arguments = 'argument1=bar'
        oauthEchoSecret = getConfig().get('oauth', 'access-secret')
        token = dataToToken(oauthEchoSecret + consumer.secret,
                            {'username': 'unknown'})
        signature = 'Sno1ocDhYv9vwJnEJATE3cmUvSo='
        nonce = 'nonce'
        credentials = OAuthCredentials(
            'fluidinfo.com', user1.username, token, 'HMAC-SHA1', signature,
            timestamp, nonce, 'GET', u'https://fluidinfo.com/foo', headers,
            arguments)
        self.assertRaises(UnknownUserError, oauthConsumerAPI.authenticate,
                          credentials)

    def testAuthenticateOAuth2WithUnknownUser(self):
        """
        L{OAuthConsumerAPI.authenticate} raises a L{UnknownUserError} exception
        if the user in the L{OAuth2Credentials} token doesn't exist.
        """
        UserAPI().create([(u'user1', u'secret1', u'User1',
                           u'user1@example.com')])
        user1 = getUser(u'user1')

        oauthConsumerAPI = OAuthConsumerAPI()
        consumer = oauthConsumerAPI.register(user1, secret='abyOTsAfo9MVN0qz')
        oauthEchoSecret = getConfig().get('oauth', 'access-secret')
        token = dataToToken(oauthEchoSecret + consumer.secret,
                            {'username': 'unknown'})

        credentials = OAuth2Credentials(u'user1', u'secret1', token)
        self.assertRaises(UnknownUserError, oauthConsumerAPI.authenticate,
                          credentials)

    def testAuthenticateOAuthWithInvalidToken(self):
        """
        L{OAuthConsumerAPI.authenticate} raises an L{AuthenticationError}
        exception if the token in the L{OAuthCredentials} is invalid.
        """
        UserAPI().create([(u'user1', u'secret1', u'User1',
                           u'user1@example.com')])
        user1 = getUser(u'user1')

        # NOTE This second user is not used, but it's created anyway to make
        # sure that the environment is the same as the other tests, but this
        # time the test will only fail because of an invalid token.
        # This is here to avoid regressions.
        UserAPI().create([(u'user2', u'secret2', u'User2',
                           u'user2@example.com')])

        oauthConsumerAPI = OAuthConsumerAPI()
        oauthConsumerAPI.register(user1, secret='abyOTsAfo9MVN0qz')
        timestamp = 1314976811
        headers = {'header1': 'foo'}
        arguments = 'argument1=bar'
        token = 'invalid'
        signature = 'wrong'
        nonce = 'nonce'
        credentials = OAuthCredentials(
            'fluidinfo.com', user1.username, token, 'HMAC-SHA1', signature,
            timestamp, nonce, 'GET', u'https://fluidinfo.com/foo', headers,
            arguments)
        self.assertRaises(AuthenticationError, oauthConsumerAPI.authenticate,
                          credentials)

    def testAuthenticateOAuth2WithInvalidToken(self):
        """
        L{OAuthConsumerAPI.authenticate} raises an L{AuthenticationError}
        exception if the token in the L{OAuthCredentials} is invalid.
        """
        UserAPI().create([(u'user1', u'secret1', u'User1',
                           u'user1@example.com')])
        user1 = getUser(u'user1')

        # NOTE This second user is not used, but it's created anyway to make
        # sure that the environment is the same as the other tests, but this
        # time the test will only fail because of an invalid token.
        # This is here to avoid regressions.
        UserAPI().create([(u'user2', u'secret2', u'User2',
                           u'user2@example.com')])

        oauthConsumerAPI = OAuthConsumerAPI()
        oauthConsumerAPI.register(user1, secret='abyOTsAfo9MVN0qz')

        token = 'invalid'
        credentials = OAuth2Credentials(u'user1', u'secret1', token)

        self.assertRaises(AuthenticationError, oauthConsumerAPI.authenticate,
                          credentials)

    def testAuthenticateOAuth2WithTokenMadeFromBadOAuthEchoSecret(self):
        """
        L{OAuthConsumerAPI.authenticate} raises an L{AuthenticationError}
        exception if the token in the L{OAuthCredentials} is invalid
        because it is not made with our oauthEchoSecret in the key.
        """
        UserAPI().create([(u'user1', u'secret1', u'User1',
                           u'user1@example.com')])
        user1 = getUser(u'user1')

        UserAPI().create([(u'user2', u'secret2', u'User2',
                           u'user2@example.com')])

        oauthConsumerAPI = OAuthConsumerAPI()
        consumer = oauthConsumerAPI.register(user1, secret='abyOTsAfo9MVN0qz')

        oauthEchoSecret = 'x' * 16
        token = dataToToken(oauthEchoSecret + consumer.secret,
                            {'username': 'user2'})
        credentials = OAuth2Credentials(u'user1', u'secret1', token)

        self.assertRaises(AuthenticationError, oauthConsumerAPI.authenticate,
                          credentials)

    def testAuthenticateOAuthWithUnknownConsumer(self):
        """
        L{OAuthConsumerAPI.authenticate} raises an L{AuthenticationError}
        exception if the consumer is not registered.
        """
        UserAPI().create([(u'user1', u'secret1', u'User1',
                           u'user1@example.com')])
        user1 = getUser(u'user1')

        secret = 'a' * 16
        timestamp = 1314976811
        headers = {'header1': 'foo'}
        arguments = 'argument1=bar'

        oauthEchoSecret = getConfig().get('oauth', 'access-secret')
        token = dataToToken(oauthEchoSecret + secret, {'user1': 'secret1'})
        signature = 'Sno1ocDhYv9vwJnEJATE3cmUvSo='
        nonce = 'nonce'

        oauthConsumerAPI = OAuthConsumerAPI()
        credentials = OAuthCredentials(
            'fluidinfo.com', user1.username, token, 'HMAC-SHA1', signature,
            timestamp, nonce, 'GET', u'https://fluidinfo.com/foo', headers,
            arguments)

        self.assertRaises(AuthenticationError, oauthConsumerAPI.authenticate,
                          credentials)

    def testAuthenticateOAuth2WithUnknownConsumer(self):
        """
        L{OAuthConsumerAPI.authenticate} raises an L{AuthenticationError}
        exception if the consumer is not registered.
        """
        UserAPI().create([(u'user1', u'secret1', u'User1',
                           u'user1@example.com')])

        secret = 'a' * 16
        oauthEchoSecret = getConfig().get('oauth', 'access-secret')
        token = dataToToken(oauthEchoSecret + secret, {'user1': 'secret1'})

        oauthConsumerAPI = OAuthConsumerAPI()
        credentials = OAuth2Credentials(u'user1', u'secret1', token)

        self.assertRaises(AuthenticationError, oauthConsumerAPI.authenticate,
                          credentials)

    def testAuthenticateOAuthWithIncorrectSignature(self):
        """
        L{OAuthConsumerAPI.authenticate} raises an L{AuthenticationError}
        exception if the signature in the L{OAuthCredentials} is incorrect.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumerUser = getUser(u'consumer')
        user = getUser(u'user')

        api = OAuthConsumerAPI()
        consumer = api.register(consumerUser, secret='abyOTsAfo9MVN0qz')
        timestamp = 1314976811
        headers = {'header1': 'foo'}
        arguments = 'argument1=bar'
        oauthEchoSecret = getConfig().get('oauth', 'access-secret')
        token = dataToToken(oauthEchoSecret + consumer.secret,
                            {'username': user.username,
                             'creationTime': '2012-12-28 16:18:23'})
        signature = 'wrong'
        nonce = 'nonce'
        credentials = OAuthCredentials(
            'fluidinfo.com', consumerUser.username, token, 'HMAC-SHA1',
            signature, timestamp, nonce, 'GET', u'https://fluidinfo.com/foo',
            headers, arguments)
        self.assertRaises(AuthenticationError, api.authenticate, credentials)

    def testRenewToken(self):
        """
        L{OAuthConsumerAPI.renewToken} generates a new L{OAuthRenewalToken}
        and L{OAuthAccessToken}, given a valid L{OAuthRenewalToken}.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumerUser = getUser(u'consumer')
        user = getUser(u'user')

        api = OAuthConsumerAPI()
        api.register(consumerUser)
        renewalToken = api.getRenewalToken(consumerUser, user)
        newRenewalToken, accessToken = api.renewToken(renewalToken)
        self.assertNotEqual(renewalToken, newRenewalToken)
        self.assertTrue(isinstance(renewalToken, OAuthRenewalToken))
        self.assertIdentical(consumerUser, renewalToken.consumer)
        self.assertIdentical(user, renewalToken.user)
        self.assertTrue(isinstance(accessToken, OAuthAccessToken))
        self.assertIdentical(consumerUser, accessToken.consumer)
        self.assertIdentical(user, accessToken.user)

    def testRenewExpiredToken(self):
        """
        L{OAuthConsumerAPI.renewToken} raises an L{ExpiredOAuthTokenError} if
        an expired L{OAuthRenewalToken} is used when trying to generate a new
        L{OAuthAccessToken}.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumerUser = getUser(u'consumer')
        user = getUser(u'user')

        creationTime = datetime.utcnow() - timedelta(hours=200)
        api = OAuthConsumerAPI()
        api.register(consumerUser)
        renewalToken = api.getRenewalToken(consumerUser, user,
                                           now=lambda: creationTime)
        self.assertRaises(ExpiredOAuthTokenError, api.renewToken, renewalToken)

    def testRenewTokenWithUnknownConsumer(self):
        """
        L{OAuthConsumerAPI.renewToken} raises an L{UnknownConsumerError} if an
        L{OAuthRenewalToken} for an unknown consumer is used to generate a new
        L{OAuthAccessToken}.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumerUser = getUser(u'consumer')
        user = getUser(u'user')

        api = OAuthConsumerAPI()
        api.register(consumerUser)
        renewalToken = api.getRenewalToken(consumerUser, user)
        getUsers(usernames=[u'consumer']).remove()
        self.assertRaises(UnknownConsumerError, api.renewToken, renewalToken)
