from base64 import b64encode
from json import dumps, loads

from twisted.internet.defer import inlineCallbacks
from twisted.web.client import Agent, ResponseDone
from twisted.web.http import OK, CONFLICT, SERVICE_UNAVAILABLE
from twisted.web.http_headers import Headers
from twisted.web.server import NOT_DONE_YET

from fluiddb.data.system import createSystemData
from fluiddb.model.oauth import OAuthConsumerAPI
from fluiddb.model.user import UserAPI, TwitterUserAPI
from fluiddb.security.oauthecho import TWITTER_URL
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.doubles import (
    FakeReactorAndConnectMixin, FakeRequest, FakeResponse)
from fluiddb.testing.session import login
from fluiddb.testing.resources import (
    ConfigResource, DatabaseResource, LoggingResource, ThreadPoolResource)
from fluiddb.util.transact import Transact
from fluiddb.web.oauthecho import OAuthEchoResource


class OAuthEchoResourceTest(FluidinfoTestCase, FakeReactorAndConnectMixin):

    resources = [('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(OAuthEchoResourceTest, self).setUp()
        self.agent = Agent(self.FakeReactor())
        self.transact = Transact(self.threadPool)
        system = createSystemData()
        self.anonymous = system.users[u'anon']
        OAuthConsumerAPI().register(self.anonymous)
        self.agent = Agent(self.FakeReactor())

    def testRenderWithMissingServiceProviderHeader(self):
        """
        A C{BAD_REQUEST} HTTP status code is returned if the
        C{X-Auth-Service-Provider} header is not in the request, and the
        C{X-Fluiddb-*} response headers indicate that the header is missing.
        """
        headers = {'X-Verify-Credentials-Authorization': ['OAuth ...']}
        request = FakeRequest(headers=Headers(headers))
        with login(u'anon', self.anonymous.objectID, self.transact) as session:
            resource = OAuthEchoResource(session)
            self.assertEqual('', resource.render_GET(request))
            headers = dict(request.responseHeaders.getAllRawHeaders())
            yield resource.deferred
            self.assertEqual(
                {'X-Fluiddb-Error-Class': ['MissingHeader'],
                 'X-Fluiddb-Header': ['X-Auth-Service-Provider'],
                 'X-Fluiddb-Request-Id': [session.id]},
                headers)

    def testRenderWithUnknownServiceProvider(self):
        """
        A C{BAD_REQUEST} HTTP status code is returned if the
        C{X-Auth-Service-Provider} in the header is not supported.
        """
        headers = {'X-Verify-Credentials-Authorization': ['OAuth ...'],
                   'X-Auth-Service-Provider': ['https://example.com/1/verify']}
        request = FakeRequest(headers=Headers(headers))
        with login(u'anon', self.anonymous.objectID, self.transact) as session:
            resource = OAuthEchoResource(session)
            self.assertEqual('', resource.render_GET(request))
            headers = dict(request.responseHeaders.getAllRawHeaders())
            yield resource.deferred
            self.assertEqual(
                {'X-Fluiddb-Error-Class': ['UnknownServiceProvider'],
                 'X-Fluiddb-Request-Id': [session.id]},
                headers)

    def testRenderWithMissingAuthorizationHeader(self):
        """
        A C{BAD_REQUEST} HTTP status code is returned if the
        C{X-Verify-Credentials-Authorization} header is not in the request,
        and the C{X-Fluiddb-*} response headers indicate that the header is
        missing.
        """
        headers = {'X-Auth-Service-Provider': [TWITTER_URL]}
        request = FakeRequest(headers=Headers(headers))
        with login(u'anon', self.anonymous.objectID, self.transact) as session:
            resource = OAuthEchoResource(session)
            self.assertEqual('', resource.render_GET(request))
            headers = dict(request.responseHeaders.getAllRawHeaders())
            yield resource.deferred
            self.assertEqual(
                {'X-Fluiddb-Error-Class': ['MissingHeader'],
                 'X-Fluiddb-Header': ['X-Verify-Credentials-Authorization'],
                 'X-Fluiddb-Request-Id': [session.id]},
                headers)

    def testRenderWithUnsupportedAuthorizationHeader(self):
        """
        A C{BAD_REQUEST} HTTP status code is returned if the
        C{X-Verify-Credentials-Authorization} in the header doesn't use the
        C{OAuth} scheme.
        """
        headers = {'X-Verify-Credentials-Authorization': ['Basic ...'],
                   'X-Auth-Service-Provider': [TWITTER_URL]}
        request = FakeRequest(headers=Headers(headers))
        with login(u'anon', self.anonymous.objectID, self.transact) as session:
            resource = OAuthEchoResource(session)
            self.assertEqual('', resource.render_GET(request))
            headers = dict(request.responseHeaders.getAllRawHeaders())
            yield resource.deferred
            self.assertEqual(
                {'X-Fluiddb-Error-Class': ['BadHeader'],
                 'X-Fluiddb-Header': ['X-Verify-Credentials-Authorization'],
                 'X-Fluiddb-Request-Id': [session.id]},
                headers)

    @inlineCallbacks
    def testRenderWithSuccessfulVerification(self):
        """
        An C{OK} HTTP status code is returned if the authorization is
        successfully verified by the service provider.  The results of the
        call to the service provider to verify credentials are returned to the
        user.
        """
        UserAPI().create([(u'john', 'secret', u'John', u'john@example.com')])
        TwitterUserAPI().create(u'john', 1984245)
        self.store.commit()

        self.agent._connect = self._connect
        headers = {'X-Verify-Credentials-Authorization': ['OAuth ...'],
                   'X-Auth-Service-Provider': [TWITTER_URL]}
        request = FakeRequest(headers=Headers(headers))
        with login(u'anon', self.anonymous.objectID, self.transact) as session:
            resource = OAuthEchoResource(session, self.agent)
            self.assertEqual(NOT_DONE_YET, resource.render_GET(request))

            [(_, responseDeferred)] = self.protocol.requests
            data = {'id': 1984245, 'screen_name': u'john', 'name': u'John'}
            response = FakeResponse(ResponseDone(), dumps(data))
            responseDeferred.callback(response)
            result = yield resource.deferred
            self.assertTrue(result['access-token'])
            self.assertTrue(result['renewal-token'])
            del result['access-token']
            del result['renewal-token']
            self.assertEqual({'username': u'john',
                              'new-user': False,
                              'missing-password': False,
                              'data': data,
                              'uid': 1984245},
                             result)
            self.assertEqual(OK, request.code)
            self.assertEqual(data, loads(request.written.getvalue()))

    @inlineCallbacks
    def testRenderWithNewUser(self):
        """
        Missing L{User}s are created automatically and linked to
        L{TwitterUser}s for authorized UIDs.
        """
        self.assertNotIn(u'john', UserAPI().get([u'john']))
        self.store.commit()

        self.agent._connect = self._connect
        headers = {'X-Verify-Credentials-Authorization': ['OAuth ...'],
                   'X-Auth-Service-Provider': [TWITTER_URL]}
        request = FakeRequest(headers=Headers(headers))
        with login(u'anon', self.anonymous.objectID, self.transact) as session:
            resource = OAuthEchoResource(session, self.agent)
            self.assertEqual(NOT_DONE_YET, resource.render_GET(request))

            [(_, responseDeferred)] = self.protocol.requests
            data = {'id': 1984245, 'screen_name': u'john', 'name': u'John'}
            response = FakeResponse(ResponseDone(), dumps(data))
            responseDeferred.callback(response)
            result = yield resource.deferred
            self.assertTrue(result['access-token'])
            self.assertTrue(result['renewal-token'])
            del result['access-token']
            del result['renewal-token']
            self.assertEqual({'username': u'john',
                              'new-user': True,
                              'missing-password': True,
                              'data': data,
                              'uid': 1984245},
                             result)
            self.assertEqual(OK, request.code)
            self.assertEqual(data, loads(request.written.getvalue()))
            headers = dict(request.responseHeaders.getAllRawHeaders())
            self.assertTrue(headers['X-Fluiddb-Access-Token'])
            self.assertTrue(headers['X-Fluiddb-Renewal-Token'])
            del headers['X-Fluiddb-Access-Token']
            del headers['X-Fluiddb-Renewal-Token']
            self.assertEqual(
                {'X-Fluiddb-New-User': ['true'],
                 'X-Fluiddb-Missing-Password': ['true'],
                 'X-Fluiddb-Username': ['am9obg==']},  # username is in base64.
                headers)

            self.store.rollback()
            self.assertIn(u'john', UserAPI().get([u'john']))

    @inlineCallbacks
    def testRenderWithUserConflict(self):
        """
        A C{CONFLICT} HTTP status code is returned if the authorization is
        successfully verified by the service provider, but the username
        clashes with an existing L{User} that isn't linked to the Twitter UID.
        The offending username is returned UTF-8 and base64 encoded.
        """
        username = u'john\N{HIRAGANA LETTER A}'
        UserAPI().create([(username, 'secret', u'John', u'john@example.com')])
        self.store.commit()

        self.agent._connect = self._connect
        headers = {'X-Verify-Credentials-Authorization': ['OAuth ...'],
                   'X-Auth-Service-Provider': [TWITTER_URL]}
        request = FakeRequest(headers=Headers(headers))
        with login(u'anon', self.anonymous.objectID, self.transact) as session:
            resource = OAuthEchoResource(session, self.agent)
            self.assertEqual(NOT_DONE_YET, resource.render_GET(request))

            [(_, responseDeferred)] = self.protocol.requests
            data = {'id': 1984245, 'screen_name': username, 'name': u'John'}
            response = FakeResponse(ResponseDone(), dumps(data))
            responseDeferred.callback(response)
            yield resource.deferred
            self.assertEqual(CONFLICT, request.code)
            headers = dict(request.responseHeaders.getAllRawHeaders())
            encodedUsername = b64encode(username.encode('utf-8'))
            self.assertEqual(
                {'X-Fluiddb-Error-Class': ['UsernameConflict'],
                 'X-Fluiddb-Username': [encodedUsername],
                 'X-Fluiddb-Request-Id': [session.id]},
                headers)

    @inlineCallbacks
    def testRenderWithFailingServiceProviderCall(self):
        """
        A C{SERVICE_UNAVAILABLE} HTTP status code is returned if an error
        occurs while communicating with the L{ServiceProvider}.
        """
        UserAPI().create([(u'user', 'secret', u'User', u'user@example.com')])
        TwitterUserAPI().create(u'user', 1984245)
        self.store.commit()

        self.agent._connect = self._connect
        headers = {'X-Verify-Credentials-Authorization': ['OAuth ...'],
                   'X-Auth-Service-Provider': [TWITTER_URL]}
        request = FakeRequest(headers=Headers(headers))
        with login(u'anon', self.anonymous.objectID, self.transact) as session:
            resource = OAuthEchoResource(session, self.agent)
            self.assertEqual(NOT_DONE_YET, resource.render_GET(request))

            [(_, responseDeferred)] = self.protocol.requests
            response = FakeResponse(RuntimeError(), None)
            responseDeferred.callback(response)
            yield resource.deferred
            self.assertEqual(SERVICE_UNAVAILABLE, request.code)
