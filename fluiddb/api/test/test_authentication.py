from uuid import UUID

from oauth2 import Request, SignatureMethod_HMAC_SHA1
from twisted.internet.defer import inlineCallbacks

from fluiddb.api.facade import Facade
from fluiddb.application import FluidinfoSessionFactory
from fluiddb.common.types_thrift.ttypes import (
    TNoSuchUser, TPasswordIncorrect, TPathPermissionDenied,
    TUserAlreadyExists, TInvalidUsername, TUsernameTooLong)
from fluiddb.data.oauth import createOAuthConsumer
from fluiddb.data.system import createSystemData
from fluiddb.data.user import createUser, Role
from fluiddb.model.oauth import OAuthConsumerAPI
from fluiddb.model.user import UserAPI, getUser
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    CacheResource, ConfigResource, DatabaseResource, LoggingResource,
    ThreadPoolResource)
from fluiddb.testing.session import login
from fluiddb.util.minitoken import dataToToken
from fluiddb.util.oauth_credentials import OAuthCredentials
from fluiddb.util.oauth2_credentials import OAuth2Credentials
from fluiddb.util.session import Session
from fluiddb.util.transact import Transact


class FacadeTest(FluidinfoTestCase):
    """
    Simple tests of L{Facade} functionality that are not to do with user
    creation or authentication.
    """

    resources = [('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(FacadeTest, self).setUp()
        factory = FluidinfoSessionFactory('API-9000')
        self.transact = Transact(self.threadPool)
        self.facade = Facade(self.transact, factory)
        self.system = createSystemData()

    @inlineCallbacks
    def testCreateAnonymousSession(self):
        """
        L{FacadeAuthMixin.createAnonymousSession} creates a
        L{FluidinfoSession} for the anonymous user C{anon} so that anonymous
        requests coming from the C{WSFE} can be correctly verified by the
        L{Facade}.
        """
        anon = self.system.users[u'anon']
        self.store.commit()

        session = yield self.facade.createAnonymousSession()
        self.assertEqual('anon', session.auth.username)
        self.assertEqual(anon.objectID, session.auth.objectID)


class FacadeUserCreationTest(FluidinfoTestCase):
    """Test L{Facade} user creation."""

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(FacadeUserCreationTest, self).setUp()
        factory = FluidinfoSessionFactory('API-9000')
        self.transact = Transact(self.threadPool)
        self.facade = Facade(self.transact, factory)
        self.system = createSystemData()

    @inlineCallbacks
    def testCreateUserWithPassword(self):
        """
        L{FacadeAuthMixin.createUserWithPassword} will create a new user in
        the database and return its object ID when invoked by the superuser.
        """
        superuser = self.system.users[u'fluiddb']
        self.store.commit()

        with login(u'fluiddb', superuser.objectID, self.transact) as session:
            objectID = yield self.facade.createUserWithPassword(
                session, 'user', 'secret', 'User', 'user@example.com')
        self.store.rollback()

        self.assertEqual({u'user': {'id': UUID(objectID), 'name': u'User',
                                    'role': Role.USER}},
                         UserAPI().get([u'user']))

    @inlineCallbacks
    def testCreateUserWithPasswordIgnoresCase(self):
        """
        L{FacadeAuthMixin.createUserWithPassword} ignores the case of the
        username.
        """
        superuser = self.system.users[u'fluiddb']
        self.store.commit()

        with login(u'fluiddb', superuser.objectID, self.transact) as session:
            objectID = yield self.facade.createUserWithPassword(
                session, 'UsEr', 'secret', 'User', 'user@example.com')
        self.store.rollback()

        self.assertEqual({u'user': {'id': UUID(objectID), 'name': u'User',
                                    'role': Role.USER}},
                         UserAPI().get([u'user']))

    @inlineCallbacks
    def testCreateUserUnicode(self):
        """
        L{FacadeAuthMixin.createUserWithPassword} will accept UTF-8 encoded
        C{str}s for the username, the password, the full name and the email
        address and convert them to C{unicode} appropriately.
        """
        superuser = self.system.users[u'fluiddb']
        username = u'\N{HIRAGANA LETTER A}'
        password = u'\N{HIRAGANA LETTER E}'
        name = u'\N{HIRAGANA LETTER I}'
        email = u'hiragana@example.com'
        self.store.commit()

        with login(u'fluiddb', superuser.objectID, self.transact) as session:
            objectID = yield self.facade.createUserWithPassword(
                session, username.encode('utf-8'), password.encode('utf-8'),
                name.encode('utf-8'), email.encode('utf-8'))
        self.store.rollback()
        user = getUser(username)

        self.assertEqual(str(user.objectID), objectID)
        self.assertEqual(user.fullname, name)
        self.assertEqual(user.email, email)

    @inlineCallbacks
    def testCreateUserDuplicate(self):
        """
        L{FacadeAuthMixin.createUserWithPassword} will raise a
        L{TUserAlreadyExists} if the username given already exists in the
        database.
        """
        createUser(u'fred', u'password', u'Fred', u'fred@example.com')
        superuser = self.system.users[u'fluiddb']
        self.store.commit()

        with login(u'fluiddb', superuser.objectID, self.transact) as session:
            deferred = self.facade.createUserWithPassword(
                session, 'fred', 'password', 'Fred', 'fred@example.com')
            yield self.assertFailure(deferred, TUserAlreadyExists)

    @inlineCallbacks
    def testCreateUserWithInvalidUsername(self):
        """
        L{FacadeAuthMixin.createUserWithPassword} will raise a
        L{TInvalidUsername} exception if the username given is invalid.
        """
        superuser = self.system.users[u'fluiddb']
        self.store.commit()

        with login(u'fluiddb', superuser.objectID, self.transact) as session:
            deferred = self.facade.createUserWithPassword(
                session, '!invalid & ', 'secret', 'None', 'none@example.com')
            yield self.assertFailure(deferred, TInvalidUsername)

    @inlineCallbacks
    def testCreateUserWithLongUsername(self):
        """
        L{FacadeAuthMixin.createUserWithPassword} will raise a
        L{TUsernameTooLong} exception if the username given is longer than 128
        characters.
        """
        superuser = self.system.users[u'fluiddb']
        self.store.commit()

        with login(u'fluiddb', superuser.objectID, self.transact) as session:
            session.auth.login(u'fluiddb', superuser.objectID)
            deferred = self.facade.createUserWithPassword(
                session, 'x' * 129, 'secret', 'None', 'none@example.com')
            yield self.assertFailure(deferred, TUsernameTooLong)

    @inlineCallbacks
    def testCreateUserNormalUserRole(self):
        """
        L{FacadeAuthMixin.createUserWithPassword} will raise a
        L{TPathPermissionDenied} if invoked by a normal user.
        """
        user = createUser(u'user', u'pass', u'User', u'user@example.com')
        self.store.commit()

        with login(u'user', user.objectID, self.transact) as session:
            deferred = self.facade.createUserWithPassword(
                session, 'fred', 'password', 'Fred', 'fred@example.com')
            yield self.assertFailure(deferred, TPathPermissionDenied)

    @inlineCallbacks
    def testCreateUserByAnonymousRole(self):
        """
        L{FacadeAuthMixin.createUserWithPassword} will raise a
        L{TPathPermissionDenied} if invoked by the anonymous user.
        """
        anonymous = self.system.users[u'anon']
        self.store.commit()

        with login(u'anon', anonymous.objectID, self.transact) as session:
            deferred = self.facade.createUserWithPassword(
                session, 'fred', 'password', 'Fred', 'fred@example.com')
            yield self.assertFailure(deferred, TPathPermissionDenied)


class FacadeAuthenticateUserWithPasswordTest(FluidinfoTestCase):
    """Test L{Facade} user+password authentication."""

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(FacadeAuthenticateUserWithPasswordTest, self).setUp()
        factory = FluidinfoSessionFactory('API-9000')
        self.transact = Transact(self.threadPool)
        self.facade = Facade(self.transact, factory)
        self.system = createSystemData()

    @inlineCallbacks
    def testAuthenticateUserWithPassword(self):
        """
        L{FacadeAuthMixin.authenticateUserWithPassword} creates a
        L{FluidinfoSession} for the authenticated user only if credentials are
        correct.
        """
        user = createUser(u'user', u'pass', u'User', u'user@example.com')
        self.store.commit()

        session = yield self.facade.authenticateUserWithPassword('user',
                                                                 'pass')

        self.assertEqual('user', session.auth.username)
        self.assertEqual(user.objectID, session.auth.objectID)

    @inlineCallbacks
    def testAuthenticateUserWithPasswordIgnoresCase(self):
        """
        L{FacadeAuthMixin.authenticateUserWithPassword} ignores case for the
        the username.
        """
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        self.store.commit()

        session = yield self.facade.authenticateUserWithPassword('UsEr',
                                                                 'secret')

        self.assertEqual('user', session.auth.username)

    @inlineCallbacks
    def testAuthenticateUserWithPasswordUnicodeUsername(self):
        """
        L{FacadeAuthMixin.authenticateUserWithPassword} will accept UTF-8
        encoded C{str}s for the username and the password, and convert them to
        C{unicode} appropiately.
        """
        username = u'\N{HIRAGANA LETTER A}'
        password = u'\N{HIRAGANA LETTER E}'
        fullname = u'\N{HIRAGANA LETTER I}'
        email = u'hiragana@example.com'
        user = createUser(username, password, fullname, email)
        self.store.commit()

        session = yield self.facade.authenticateUserWithPassword(
            username.encode('utf-8'), password.encode('utf-8'))
        self.assertEqual(username, session.auth.username)
        self.assertEqual(user.objectID, session.auth.objectID)

    def testAuthenticateUserWithPasswordIncorrectPassword(self):
        """
        L{FacadeAuthMixin.authenticateUserWithPassword} raises a
        L{TPasswordIncorrect} exception if the provided password doesn't match
        the L{User}'s.
        """
        createUser(u'username', u'password', u'User', u'user@example.com')
        self.store.commit()

        deferred = self.facade.authenticateUserWithPassword('username',
                                                            'bad-password')
        return self.assertFailure(deferred, TPasswordIncorrect)

    def testAuthenticateUserWithPasswordUnknownUser(self):
        """
        L{FacadeAuthMixin.authenticateUserWithPassword} raises a
        L{TNoSuchUser} exception if the provided username doesn't exist in the
        database.
        """
        self.store.commit()
        deferred = self.facade.authenticateUserWithPassword('unknown', 'pwd')
        return self.assertFailure(deferred, TNoSuchUser)

    @inlineCallbacks
    def testAuthenticateUserWithPasswordStopsSessionOnError(self):
        """
        L{FacadeAuthMixin.authenticateUserWithPassword} stops the session if an
        authentication error occurs, preventing memory leaks.
        """
        self.store.commit()

        # We monkeypatch the Session.close method to know if it was called.
        oldStop = Session.stop

        def stopWrapper(*args, **kwargs):
            self.sessionStopped = True
            return oldStop(*args, **kwargs)
        Session.stop = stopWrapper

        self.sessionStopped = False
        deferred = self.facade.authenticateUserWithPassword('unknown', 'pwd')
        yield self.assertFailure(deferred, TNoSuchUser)
        self.assertTrue(self.sessionStopped)

        self.sessionStopped = False
        deferred = self.facade.authenticateUserWithPassword('username', 'bad')
        yield self.assertFailure(deferred, TNoSuchUser)
        self.assertTrue(self.sessionStopped)

        Session.stop = oldStop


class FacadeAuthenticateUserWithOAuthTest(FluidinfoTestCase):
    """Test L{Facade} OAuth authentication."""

    resources = [('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(FacadeAuthenticateUserWithOAuthTest, self).setUp()
        factory = FluidinfoSessionFactory('API-9000')
        self.transact = Transact(self.threadPool)
        self.facade = Facade(self.transact, factory)
        self.system = createSystemData()

    @inlineCallbacks
    def testAuthenticateUserWithOAuth(self):
        """
        L{FacadeAuthMixin.authenticateUserWithOAuth} creates a
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
        request = Request.from_request('GET', u'https://fluidinfo.com/foo',
                                       headers, {'argument1': 'bar'})
        signature = SignatureMethod_HMAC_SHA1().sign(request,
                                                     consumer, None)
        nonce = 'nonce'
        credentials = OAuthCredentials(
            'fluidinfo.com', consumerUser.username, token.encrypt(),
            'HMAC-SHA1', signature, timestamp, nonce, 'GET',
            u'https://fluidinfo.com/foo', headers, arguments)
        session = yield self.facade.authenticateUserWithOAuth(credentials)
        self.assertEqual(user.username, session.auth.username)
        self.assertEqual(user.objectID, session.auth.objectID)

    @inlineCallbacks
    def testAuthenticateUserWithOAuthIgnoresCase(self):
        """
        L{FacadeAuthMixin.authenticateUserWithOAuth} ignores the case in the
        consumer key.
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
        request = Request.from_request('GET', u'https://fluidinfo.com/foo',
                                       headers, {'argument1': 'bar'})
        signature = SignatureMethod_HMAC_SHA1().sign(request,
                                                     consumer, None)
        nonce = 'nonce'
        credentials = OAuthCredentials(
            'fluidinfo.com', u'ConsumeR', token.encrypt(),
            'HMAC-SHA1', signature, timestamp, nonce, 'GET',
            u'https://fluidinfo.com/foo', headers, arguments)
        session = yield self.facade.authenticateUserWithOAuth(credentials)
        self.assertEqual(user.username, session.auth.username)
        self.assertEqual(user.objectID, session.auth.objectID)

    @inlineCallbacks
    def testAuthenticateUserWithOAuthWithMixedCaseInToken(self):
        """
        L{FacadeAuthMixin.authenticateUserWithOAuth} ignores the case in the
        username in the token.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumerUser = getUser(u'consumer')
        user = getUser(u'user')
        api = OAuthConsumerAPI()
        consumer = api.register(consumerUser)
        token = dataToToken(consumer.secret,
                            {'username': u'UseR',
                             'creationTime': '20121228-161823'})

        self.store.commit()
        timestamp = 1314976811
        headers = {'header1': 'foo'}
        arguments = 'argument1=bar'
        request = Request.from_request('GET', u'https://fluidinfo.com/foo',
                                       headers, {'argument1': 'bar'})
        signature = SignatureMethod_HMAC_SHA1().sign(request,
                                                     consumer, None)
        nonce = 'nonce'
        credentials = OAuthCredentials(
            'fluidinfo.com', consumerUser.username, token,
            'HMAC-SHA1', signature, timestamp, nonce, 'GET',
            u'https://fluidinfo.com/foo', headers, arguments)
        session = yield self.facade.authenticateUserWithOAuth(credentials)
        self.assertEqual(user.username, session.auth.username)
        self.assertEqual(user.objectID, session.auth.objectID)

    def testAuthenticateUserWithOAuthIncorrectSignature(self):
        """
        L{FacadeAuthMixin.authenticateUserWithOAuth} raises a
        L{TPasswordIncorrect} exception if the signature in the OAuth
        credentials is incorrect.
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
        timestamp = 1314976811
        headers = {'header1': 'foo'}
        arguments = 'argument1=bar'
        signature = 'wrong'
        nonce = 'nonce'
        credentials = OAuthCredentials(
            'fluidinfo.com', user.username, token.encrypt(), u'HMAC-SHA1',
            signature, timestamp, nonce, 'GET', 'https://fluidinfo.com/foo',
            headers, arguments)
        deferred = self.facade.authenticateUserWithOAuth(credentials)
        return self.assertFailure(deferred, TPasswordIncorrect)

    def testAuthenticateUserWithOAuthUnknownConsumer(self):
        """
        L{FacadeAuthMixin.authenticateUserWithOAuth} raises
        L{TNoSuchUser} if the consumer does not exist.
        """
        user2 = createUser(u'user2', u'pass2', u'User2', u'user2@example.com')
        self.store.commit()

        timestamp = 1314976811
        headers = {'header1': 'foo'}
        arguments = 'argument1=bar'
        token = dataToToken('a' * 16, {'username': user2.username})
        signature = '3MNZYSgsGftopjuwv3g2u5Q+MZM='
        nonce = 'nonce'

        credentials = OAuthCredentials(
            'fluidinfo.com', u'user1', token, 'HMAC-SHA1', signature,
            timestamp, nonce, 'GET', u'https://fluidinfo.com/foo', headers,
            arguments)
        deferred = self.facade.authenticateUserWithOAuth(credentials)

        return self.assertFailure(deferred, TNoSuchUser)

    def testAuthenticateUserWithOAuthUnregisteredConsumer(self):
        """
        L{FacadeAuthMixin.authenticateUserWithOAuth} raises
        L{TPasswordIncorrect} if the consumer exists as a Fluidinfo user
        but is not registered as an OAuth consumer.
        """
        user1 = createUser(u'user1', u'pass1', u'User1', u'user1@example.com')
        user2 = createUser(u'user2', u'pass2', u'User2', u'user2@example.com')
        self.store.commit()

        timestamp = 1314976811
        headers = {'header1': 'foo'}
        arguments = 'argument1=bar'
        token = dataToToken('a' * 16, {'username': user2.username})
        signature = '3MNZYSgsGftopjuwv3g2u5Q+MZM='
        nonce = 'nonce'

        credentials = OAuthCredentials(
            'fluidinfo.com', user1.username, token, 'HMAC-SHA1', signature,
            timestamp, nonce, 'GET', u'https://fluidinfo.com/foo', headers,
            arguments)
        deferred = self.facade.authenticateUserWithOAuth(credentials)

        return self.assertFailure(deferred, TPasswordIncorrect)

    def testAuthenticateUserWithOAuthUnknownUsernameInToken(self):
        """
        L{FacadeAuthMixin.authenticateUserWithOAuth} raises a
        L{TNoSuchUser} exception if the username in the token does
        not match an existing L{User}.
        """
        user1 = createUser(u'user1', u'pass1', u'User1', u'user1@example.com')
        oauthConsumer1 = createOAuthConsumer(user1, secret='secret16charlng1')
        self.store.commit()

        timestamp = 1314976811
        headers = {'header1': 'foo'}
        arguments = 'argument1=bar'
        token = dataToToken(oauthConsumer1.secret,
                            {'username': u'unknownUser'})
        signature = '3MNZYSgsGftopjuwv3g2u5Q+MZM='
        nonce = 'nonce'

        credentials = OAuthCredentials(
            'fluidinfo.com', user1.username, token, u'HMAC-SHA1', signature,
            timestamp, nonce, 'GET', 'https://fluidinfo.com/foo', headers,
            arguments)
        deferred = self.facade.authenticateUserWithOAuth(credentials)

        return self.assertFailure(deferred, TNoSuchUser)


class FacadeAuthenticateUserWithOAuth2Test(FluidinfoTestCase):
    """Test L{Facade} OAuth2 authentication."""

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(FacadeAuthenticateUserWithOAuth2Test, self).setUp()
        factory = FluidinfoSessionFactory('API-9000')
        self.transact = Transact(self.threadPool)
        self.facade = Facade(self.transact, factory)
        self.system = createSystemData()

    @inlineCallbacks
    def testAuthenticateUserWithOAuth2(self):
        """
        L{FacadeAuthMixin.authenticateUserWithOAuth2} creates a
        L{FluidinfoSession} for the authenticated user only if credentials are
        correct.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumer = getUser(u'consumer')
        user = getUser(u'user')
        api = OAuthConsumerAPI()
        api.register(consumer)
        token = api.getAccessToken(consumer, user)
        self.store.commit()

        credentials = OAuth2Credentials(u'consumer', u'secret',
                                        token.encrypt())
        session = yield self.facade.authenticateUserWithOAuth2(credentials)
        self.assertEqual(user.username, session.auth.username)
        self.assertEqual(user.objectID, session.auth.objectID)

    @inlineCallbacks
    def testAuthenticateUserWithOAuth2IgnoresCase(self):
        """
        L{FacadeAuthMixin.authenticateUserWithOAuth2} creates a
        L{FluidinfoSession} for the authenticated user only if credentials are
        correct.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumer = getUser(u'consumer')
        user = getUser(u'user')
        api = OAuthConsumerAPI()
        api.register(consumer)
        token = api.getAccessToken(consumer, user)
        self.store.commit()

        credentials = OAuth2Credentials(u'ConsumeR', u'secret',
                                        token.encrypt())
        session = yield self.facade.authenticateUserWithOAuth2(credentials)
        self.assertEqual(user.username, session.auth.username)
        self.assertEqual(user.objectID, session.auth.objectID)

    @inlineCallbacks
    def testAuthenticateUserWithOAuthWithMixedCaseToken(self):
        """
        L{FacadeAuthMixin.authenticateUserWithOAuth2} ignores case in the
        username in the token.
        """
        UserAPI().create([
            (u'consumer', u'secret', u'Consumer', u'consumer@example.com'),
            (u'user', u'secret', u'User', u'user@example.com')])
        consumer = getUser(u'consumer')
        user = getUser(u'user')
        api = OAuthConsumerAPI()
        oauthConsumer = api.register(consumer)
        token = dataToToken(oauthConsumer.secret,
                            {'username': u'UseR',
                             'creationTime': '20121228-161823'})
        self.store.commit()

        credentials = OAuth2Credentials(consumer.username, u'secret', token)
        session = yield self.facade.authenticateUserWithOAuth2(credentials)
        self.assertEqual(user.username, session.auth.username)
        self.assertEqual(user.objectID, session.auth.objectID)

    @inlineCallbacks
    def testAuthenticateAnonymousUserWithOAuth2(self):
        """
        L{FacadeAuthMixin.authenticateUserWithOAuth2} should create a
        L{FluidinfoSession} for the anonymous user.
        """
        anonymous = self.system.users[u'anon']
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        user = getUser(u'user')
        api = OAuthConsumerAPI()
        api.register(anonymous)
        token = api.getAccessToken(anonymous, user)
        self.store.commit()

        credentials = OAuth2Credentials(u'anon', None, token.encrypt())
        session = yield self.facade.authenticateUserWithOAuth2(credentials)
        self.assertEqual(user.username, session.auth.username)
        self.assertEqual(user.objectID, session.auth.objectID)

    def testAuthenticateUserWithOAuth2ConsumerPasswordIncorrect(self):
        """
        L{FacadeAuthMixin.authenticateUserWithOAuth2} raises
        L{TPasswordIncorrect} if the consumer's password is not correct.
        """
        user1 = createUser(u'user1', u'pass1', u'User1', u'user1@example.com')
        oauthConsumer1 = createOAuthConsumer(user1, secret='secret16charlng1')
        user2 = createUser(u'user2', u'pass2', u'User2', u'user2@example.com')
        self.store.commit()

        token = dataToToken(oauthConsumer1.secret,
                            {'username': user2.username})

        credentials = OAuth2Credentials(u'user1', u'invalid', token)
        deferred = self.facade.authenticateUserWithOAuth2(credentials)

        return self.assertFailure(deferred, TPasswordIncorrect)

    def testAuthenticateUserWithOAuth2UnknownConsumer(self):
        """
        L{FacadeAuthMixin.authenticateUserWithOAuth2} raises
        L{TNoSuchUser} if the consumer does not exist.
        """
        user = createUser(u'user', u'pass', u'User', u'user1@example.com')
        oauthConsumer = createOAuthConsumer(user, secret='secret16charlng1')
        self.store.commit()

        token = dataToToken(oauthConsumer.secret, {'username': u'unknownUser'})
        credentials = OAuth2Credentials(u'invalid', u'pass', token)
        deferred = self.facade.authenticateUserWithOAuth2(credentials)

        return self.assertFailure(deferred, TNoSuchUser)

    def testAuthenticateUserWithOAuth2UnregisteredConsumer(self):
        """
        L{FacadeAuthMixin.authenticateUserWithOAuth2} raises
        L{TPasswordIncorrect} if the consumer exists as a Fluidinfo user
        but is not registered as an OAuth consumer.
        """
        createUser(u'user1', u'pass1', u'User1', u'user1@example.com')
        createUser(u'user2', u'pass2', u'User2', u'user2@example.com')
        self.store.commit()

        token = dataToToken('a' * 16, {'username': u'user2'})
        credentials = OAuth2Credentials(u'user1', u'pass1', token)
        deferred = self.facade.authenticateUserWithOAuth2(credentials)

        return self.assertFailure(deferred, TPasswordIncorrect)

    def testAuthenticateUserWithOAuth2UnknownUsernameInToken(self):
        """
        L{FacadeAuthMixin.authenticateUserWithOAuth2} ignores the case in the
        consumer key.
        """
        user = createUser(u'user', u'pass', u'User', u'user1@example.com')
        oauthConsumer = createOAuthConsumer(user, secret='secret16charlng1')
        self.store.commit()

        token = dataToToken(oauthConsumer.secret, {'username': u'unknownUser'})
        credentials = OAuth2Credentials(u'user', u'pass', token)
        deferred = self.facade.authenticateUserWithOAuth2(credentials)

        return self.assertFailure(deferred, TNoSuchUser)
