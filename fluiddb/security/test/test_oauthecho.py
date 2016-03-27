from json import dumps

from twisted.internet.defer import inlineCallbacks
from twisted.web.client import Agent, Request, ResponseDone
from twisted.web.http import BAD_REQUEST
from twisted.web.http_headers import Headers

from fluiddb.data.exceptions import DuplicateUserError
from fluiddb.data.system import createSystemData
from fluiddb.model.oauth import OAuthConsumerAPI
from fluiddb.model.user import UserAPI, TwitterUserAPI, getUser
from fluiddb.security.oauthecho import (
    Delegator, ServiceProvider, ServiceProviderError)
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.doubles import FakeReactorAndConnectMixin, FakeResponse
from fluiddb.testing.resources import (
    ConfigResource, DatabaseResource, LoggingResource, ThreadPoolResource)
from fluiddb.util.transact import Transact


class ServiceProviderTest(FluidinfoTestCase, FakeReactorAndConnectMixin):

    def setUp(self):
        super(ServiceProviderTest, self).setUp()
        self.agent = Agent(self.FakeReactor())

    def testVerifyCredentialsPassesOAuthEchoHeadersWithRequest(self):
        """
        L{ServiceProvider.verifyCredentials} makes a request to Twitter
        to verify credentials for the consumer, as part of the OAuth Echo
        process.  It includes an C{Authentication} response header with the
        OAuth Echo credentials provided by the consumer.
        """
        self.agent._connect = self._connect
        authentication = 'OAuth oauth_consumer_key="...", ...'
        provider = ServiceProvider(self.agent, 'https://example.com/verify')
        provider.verifyCredentials(authentication)

        [(request, responseDeferred)] = self.protocol.requests
        self.assertIsInstance(request, Request)
        self.assertEqual('GET', request.method)
        self.assertEqual('/verify', request.uri)
        self.assertEqual(Headers({'Authorization': [authentication],
                                  'Host': ['example.com']}),
                         request.headers)

    @inlineCallbacks
    def testVerifyCredentialsUnpacksSuccessfulResponse(self):
        """
        L{ServiceProvider.verifyCredentials} returns a C{Deferred} that
        fires with the user object returned by Twitter, as a C{dict}, when
        credentials are successfully verified.
        """
        self.agent._connect = self._connect
        authentication = 'OAuth oauth_consumer_key="...", ...'
        provider = ServiceProvider(self.agent, 'https://example.com/verify')
        deferred = provider.verifyCredentials(authentication)

        [(request, responseDeferred)] = self.protocol.requests
        response = FakeResponse(ResponseDone(), dumps({'id': 1984245}))
        responseDeferred.callback(response)
        user = yield deferred
        self.assertEqual(1984245, user['id'])

    @inlineCallbacks
    def testVerifyCredentialsWithUnsuccessfulResponseCode(self):
        """
        L{ServiceProvider.verifyCredentials} fires an errback with a
        L{ServiceProviderError} exception if the service provider returns a
        code other than C{200 OK}.  The exception contains the HTTP status
        code and the payload, if any, that was sent by the service provider.
        """
        self.agent._connect = self._connect
        authentication = 'OAuth oauth_consumer_key="...", ...'
        provider = ServiceProvider(self.agent, 'https://example.com/verify')
        deferred = provider.verifyCredentials(authentication)

        [(request, responseDeferred)] = self.protocol.requests
        response = FakeResponse(ResponseDone(), 'Something bad happened',
                                code=BAD_REQUEST)
        responseDeferred.callback(response)
        error = yield self.assertFailure(deferred, ServiceProviderError)
        self.assertEqual(BAD_REQUEST, error.code)
        self.assertEqual('Something bad happened', error.payload)


class DelegatorTest(FluidinfoTestCase, FakeReactorAndConnectMixin):

    resources = [('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(DelegatorTest, self).setUp()
        self.agent = Agent(self.FakeReactor())
        self.transact = Transact(self.threadPool)
        createSystemData()

    @inlineCallbacks
    def testGetUser(self):
        """
        L{Delegator.getUser} returns a C{(User, data)} 2-tuple when the
        service provider successfully verifies credentials and a mapping
        between a Fluidinfo L{User} and the L{TwitterUser} being verified
        exists.
        """
        UserAPI().create([
            (u'consumer', 'secret', u'Consumer', u'consumer@example.com'),
            (u'user', 'secret', u'User', u'user@example.com')])
        TwitterUserAPI().create(u'user', 1984245)
        consumer = getUser(u'consumer')
        OAuthConsumerAPI().register(consumer)
        self.store.commit()

        self.agent._connect = self._connect
        authentication = 'OAuth oauth_consumer_key="...", ...'
        provider = ServiceProvider(self.agent, 'https://example.com/verify')
        delegator = Delegator(self.transact)
        deferred = delegator.getUser(u'consumer', provider, authentication)

        [(request, responseDeferred)] = self.protocol.requests
        response = FakeResponse(ResponseDone(), dumps({'id': 1984245}))
        responseDeferred.callback(response)
        result = yield deferred
        self.assertTrue(result['access-token'])
        self.assertTrue(result['renewal-token'])
        del result['access-token']
        del result['renewal-token']
        self.assertEqual({'username': u'user',
                          'new-user': False,
                          'missing-password': False,
                          'uid': 1984245,
                          'data': {u'id': 1984245}},
                         result)

    @inlineCallbacks
    def testGetUserWithNoPassword(self):
        """
        If a L{User} returned by L{Delegator.getUser} doesn't have a password,
        a C{missing-password} value is added to the result.
        """
        UserAPI().create([
            (u'consumer', 'secret', u'Consumer', u'consumer@example.com'),
            (u'user', None, u'User', u'user@example.com')])
        TwitterUserAPI().create(u'user', 1984245)
        consumer = getUser(u'consumer')
        OAuthConsumerAPI().register(consumer)
        self.store.commit()

        self.agent._connect = self._connect
        authentication = 'OAuth oauth_consumer_key="...", ...'
        provider = ServiceProvider(self.agent, 'https://example.com/verify')
        delegator = Delegator(self.transact)
        deferred = delegator.getUser(u'consumer', provider, authentication)

        [(request, responseDeferred)] = self.protocol.requests
        response = FakeResponse(ResponseDone(), dumps({'id': 1984245}))
        responseDeferred.callback(response)
        result = yield deferred
        self.assertTrue(result['access-token'])
        self.assertTrue(result['renewal-token'])
        del result['access-token']
        del result['renewal-token']
        self.assertEqual({'username': u'user',
                          'new-user': False,
                          'missing-password': True,
                          'uid': 1984245,
                          'data': {u'id': 1984245}},
                         result)

    @inlineCallbacks
    def testGetUserWithNewUser(self):
        """
        A new L{User} is created if L{Delegator.getUser} verifies the
        L{TwitterUser} but can't find a user matching the Twitter screen name.
        A C{new-user} value is returned to indicate this situation.
        """
        UserAPI().create([
            (u'consumer', 'secret', u'Consumer', u'consumer@example.com')])
        consumer = getUser(u'consumer')
        OAuthConsumerAPI().register(consumer)
        self.store.commit()

        self.agent._connect = self._connect
        authentication = 'OAuth oauth_consumer_key="...", ...'
        provider = ServiceProvider(self.agent, 'https://example.com/verify')
        delegator = Delegator(self.transact)
        deferred = delegator.getUser(u'consumer', provider, authentication)

        [(request, responseDeferred)] = self.protocol.requests
        response = FakeResponse(ResponseDone(), dumps({'id': 1984245,
                                                       'screen_name': u'john',
                                                       'name': u'John Doe'}))
        responseDeferred.callback(response)
        result = yield deferred
        self.assertTrue(result['new-user'])

        user = TwitterUserAPI().get(1984245)
        self.assertEqual(u'john', user.username)
        self.assertEqual(u'John Doe', user.fullname)

    @inlineCallbacks
    def testGetUserWithNewUserAndMixedCaseTwitterScreenName(self):
        """
        A new L{User} is created if L{Delegator.getUser} verifies the
        L{TwitterUser} but can't find a user matching the Twitter screen name.
        The Twitter user's screen name should be lowercased to make the
        new Fluidinfo username.
        """
        UserAPI().create([
            (u'consumer', 'secret', u'Consumer', u'consumer@example.com')])
        consumer = getUser(u'consumer')
        OAuthConsumerAPI().register(consumer)
        self.store.commit()

        self.agent._connect = self._connect
        authentication = 'OAuth oauth_consumer_key="...", ...'
        provider = ServiceProvider(self.agent, 'https://example.com/verify')
        delegator = Delegator(self.transact)
        deferred = delegator.getUser(u'consumer', provider, authentication)

        [(request, responseDeferred)] = self.protocol.requests
        response = FakeResponse(ResponseDone(),
                                dumps({'id': 1984245,
                                       'screen_name': u'MixedCaseName',
                                       'name': u'John Doe'}))
        responseDeferred.callback(response)
        result = yield deferred
        self.assertTrue(result['new-user'])
        user = TwitterUserAPI().get(1984245)
        self.assertEqual(u'mixedcasename', user.username)

    @inlineCallbacks
    def testGetUserWithUserConflict(self):
        """
        A L{DuplicateUserError} exception is raised if a L{User} with the same
        username as the Twitter user's screen name already exists, but is not
        associated with the Twitter UID.
        """
        UserAPI().create([
            (u'consumer', 'secret', u'Consumer', u'consumer@example.com'),
            (u'john', 'secret', u'John', u'john@example.com')])
        self.store.commit()

        self.agent._connect = self._connect
        authentication = 'OAuth oauth_consumer_key="...", ...'
        consumer = getUser(u'consumer')
        provider = ServiceProvider(self.agent, 'https://example.com/verify')
        delegator = Delegator(self.transact)
        deferred = delegator.getUser(consumer, provider, authentication)

        [(request, responseDeferred)] = self.protocol.requests
        response = FakeResponse(ResponseDone(), dumps({'id': 1984245,
                                                       'screen_name': u'john',
                                                       'name': u'John Doe'}))
        responseDeferred.callback(response)
        error = yield self.assertFailure(deferred, DuplicateUserError)
        self.assertEqual([u'john'], list(error.usernames))
