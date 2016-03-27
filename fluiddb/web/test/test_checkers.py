from random import sample

from oauth2 import Request, SignatureMethod_HMAC_SHA1
from twisted.cred.credentials import UsernamePassword
from twisted.cred.error import UnauthorizedLogin
from twisted.internet.defer import inlineCallbacks

from fluiddb.api.facade import Facade
from fluiddb.application import FluidinfoSessionFactory, getConfig
from fluiddb.data.oauth import createOAuthConsumer
from fluiddb.data.system import createSystemData
from fluiddb.data.user import createUser, ALPHABET
from fluiddb.model.oauth import OAuthConsumerAPI
from fluiddb.model.user import UserAPI, getUser
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    ConfigResource, DatabaseResource, LoggingResource, ThreadPoolResource,
    CacheResource)
from fluiddb.util.minitoken import dataToToken
from fluiddb.util.oauth_credentials import OAuthCredentials
from fluiddb.util.oauth2_credentials import OAuth2Credentials
from fluiddb.util.transact import Transact
from fluiddb.web.checkers import (
    AnonymousChecker, FacadeChecker, FacadeOAuthChecker, FacadeOAuth2Checker)


class FacadeAnonymousCheckerTest(FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(FacadeAnonymousCheckerTest, self).setUp()
        factory = FluidinfoSessionFactory('API-9000')
        transact = Transact(self.threadPool)
        createSystemData()
        self.checker = AnonymousChecker()
        self.checker.facadeClient = Facade(transact, factory)

    @inlineCallbacks
    def testRequestAvatarIdWithAnonymousAccessDenied(self):
        """
        L{FacadeAnonymousCheckerTest.requestAvatarId} returns
        C{UnauthorizedLogin} for the C{anon} user if the
        C{allow-anonymous-access} configuration option is C{False}.
        """
        getConfig().set('service', 'allow-anonymous-access', 'False')
        self.store.commit()
        session = yield self.checker.requestAvatarId(credentials=None)
        self.assertTrue(isinstance(session, UnauthorizedLogin))

    @inlineCallbacks
    def testRequestAvatarId(self):
        """
        L{FacadeAnonymousCheckerTest.requestAvatarId} creates a
        L{FluidinfoSession} for the anonymous 'anon' user if the
        C{allow-anonymous-access} configuration option is C{True}.
        """
        getConfig().set('service', 'allow-anonymous-access', 'True')
        self.store.commit()
        session = yield self.checker.requestAvatarId(credentials=None)
        self.assertEqual('anon', session.auth.username)


class FacadeCheckerTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(FacadeCheckerTest, self).setUp()
        factory = FluidinfoSessionFactory('API-9000')
        transact = Transact(self.threadPool)
        createSystemData()
        self.checker = FacadeChecker()
        self.checker.facadeClient = Facade(transact, factory)

    def testRequestAvatarIdWithIncorrectPassword(self):
        """
        L{FacadeChecker.requestAvatarId} when passed credentials with an
        incorrect password must raise C{UnauthorizedLogin}.
        """
        createUser(u'user', u'pass', u'User', u'user@example.com')
        self.store.commit()
        credentials = UsernamePassword('user', 'bad password')
        deferred = self.checker.requestAvatarId(credentials)
        return self.assertFailure(deferred, UnauthorizedLogin)

    def testRequestAvatarIdWithNonExistentUser(self):
        """
        L{FacadeChecker.requestAvatarId} when passed credentials with a
        non-existent user must raise C{UnauthorizedLogin}.
        """
        credentials = UsernamePassword('user', 'pass')
        deferred = self.checker.requestAvatarId(credentials)
        return self.assertFailure(deferred, UnauthorizedLogin)

    @inlineCallbacks
    def testRequestAvatarId(self):
        """
        L{FacadeChecker.requestAvatarId} when passed credentials creates a
        L{FluidinfoSession} for the authenticated user only if credentials
        are correct.
        """
        user = createUser(u'user', u'pass', u'User', u'user@example.com')
        self.store.commit()
        credentials = UsernamePassword('user', 'pass')
        session = yield self.checker.requestAvatarId(credentials)
        self.assertEqual(user.username, session.auth.username)
        self.assertEqual(user.objectID, session.auth.objectID)


class FacadeOAuthCheckerTest(FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(FacadeOAuthCheckerTest, self).setUp()
        factory = FluidinfoSessionFactory('API-9000')
        transact = Transact(self.threadPool)
        createSystemData()
        self.checker = FacadeOAuthChecker()
        self.checker.facadeClient = Facade(transact, factory)

    @inlineCallbacks
    def testRequestAvatarId(self):
        """
        L{FacadeOAuthChecker.requestAvatarId} creates a
        L{FluidinfoSession} for the authenticated user only if credentials are
        correct.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumerUser = getUser(u'consumer')
        user = getUser(u'user')
        api = OAuthConsumerAPI()
        consumer = api.register(consumerUser)
        token = api.getAccessToken(consumerUser, user)
        self.store.commit()

        timestamp = 1314976811
        headers = {'header1': 'foo'}
        arguments = 'argument1=bar'
        # FIXME This isn't ideal.  It'd be better to use a hard-coded
        # signature, because then we'd know when something changed.  It's hard
        # to do that, though, because the encrypted token generated by
        # fluiddb.util.minitoken is always different. -jkakar
        request = Request.from_request('GET', u'https://fluidinfo.com/foo',
                                       headers, {'argument1': 'bar'})
        signature = SignatureMethod_HMAC_SHA1().sign(request, consumer, None)
        nonce = 'nonce'
        credentials = OAuthCredentials(
            'fluidinfo.com', consumerUser.username, token.encrypt(),
            'HMAC-SHA1', signature, timestamp, nonce, 'GET',
            u'https://fluidinfo.com/foo', headers, arguments)
        session = yield self.checker.requestAvatarId(credentials)
        self.assertEqual(user.username, session.auth.username)
        self.assertEqual(user.objectID, session.auth.objectID)

    def testRequestAvatarIdWithTokenMadeFromWrongSecret(self):
        """
        L{FacadeOAuthChecker.requestAvatarId} creates a L{FluidinfoSession}
        for the authenticated user only if the access token was created
        using the consumer's secret.
        """
        secret = ''.join(sample(ALPHABET, 16))
        user = createUser(u'username', u'password',
                          u'User', u'user@example.com')
        createOAuthConsumer(user, secret=secret)
        self.store.commit()

        timestamp = 1314976811
        headers = {'header1': 'foo'}
        arguments = 'argument1=bar'
        token = dataToToken('a' * 16, {'username': user.username})
        signature = 'wrong'
        nonce = 'nonce'

        credentials = OAuthCredentials(
            'fluidinfo.com', user.username, token, 'HMAC-SHA1', signature,
            timestamp, nonce, 'GET', u'https://fluidinfo.com/foo', headers,
            arguments)

        deferred = self.checker.requestAvatarId(credentials)
        return self.assertFailure(deferred, UnauthorizedLogin)

    def testRequestAvatarIdInvalidToken(self):
        """
        L{FacadeOAuthChecker.requestAvatarId} creates a
        L{FluidinfoSession} for the authenticated user only if
        the access token was properly formed (by calling dataToToken).
        """
        secret = ''.join(sample(ALPHABET, 16))
        user = createUser(u'username', u'password',
                          u'User', u'user@example.com')
        createOAuthConsumer(user, secret=secret)
        self.store.commit()

        timestamp = 1314976811
        headers = {'header1': 'foo'}
        arguments = 'argument1=bar'
        token = 'token'
        signature = 'wrong'
        nonce = 'nonce'

        credentials = OAuthCredentials(
            'fluidinfo.com', user.username, token, 'HMAC-SHA1', signature,
            timestamp, nonce, 'GET', u'https://fluidinfo.com/foo', headers,
            arguments)

        deferred = self.checker.requestAvatarId(credentials)
        return self.assertFailure(deferred, UnauthorizedLogin)


class FacadeOAuth2CheckerTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(FacadeOAuth2CheckerTest, self).setUp()
        factory = FluidinfoSessionFactory('API-9000')
        transact = Transact(self.threadPool)
        createSystemData()
        self.checker = FacadeOAuth2Checker()
        self.checker.facadeClient = Facade(transact, factory)

    @inlineCallbacks
    def testRequestAvatarId(self):
        """
        L{FacadeOAuth2Checker.requestAvatarId} creates a
        L{FluidinfoSession} for the authenticated user only if credentials are
        correct.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumerUser = getUser(u'consumer')
        user = getUser(u'user')
        api = OAuthConsumerAPI()
        api.register(consumerUser)
        token = api.getAccessToken(consumerUser, user)
        self.store.commit()

        credentials = OAuth2Credentials(u'consumer', 'secret', token.encrypt())
        session = yield self.checker.requestAvatarId(credentials)
        self.assertEqual(user.username, session.auth.username)
        self.assertEqual(user.objectID, session.auth.objectID)

    def testRequestAvatarIdWithTokenMadeFromWrongSecret(self):
        """
        L{FacadeOAuth2Checker.requestAvatarId} creates a
        L{FluidinfoSession} for the authenticated user only if the access
        token was created using the consumer's secret.
        """
        user1 = createUser(u'user1', u'pass1', u'User1', u'user1@example.com')
        createOAuthConsumer(user1, secret='secret16charlng1')
        user2 = createUser(u'user2', u'pass2', u'User2', u'user2@example.com')
        self.store.commit()
        token = dataToToken('a' * 16, {'username': user2.username})
        credentials = OAuth2Credentials(u'user1', u'pass1', token)
        deferred = self.checker.requestAvatarId(credentials)
        return self.assertFailure(deferred, UnauthorizedLogin)

    def testRequestAvatarIdWithInvalidToken(self):
        """
        L{FacadeOAuth2Checker.requestAvatarId} creates a
        L{FluidinfoSession} for the authenticated user only if the access
        token was properly formed (by calling dataToToken).
        """
        user = createUser(u'user', u'pass', u'User', u'user@example.com')
        createOAuthConsumer(user, secret='secret16charlng1')
        self.store.commit()
        credentials = OAuth2Credentials(u'user', u'pass', token='xxx')
        deferred = self.checker.requestAvatarId(credentials)
        return self.assertFailure(deferred, UnauthorizedLogin)
