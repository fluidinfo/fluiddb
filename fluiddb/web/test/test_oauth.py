from datetime import datetime, timedelta

from twisted.internet.defer import inlineCallbacks
from twisted.web.http import BAD_REQUEST, OK, UNAUTHORIZED
from twisted.web.http_headers import Headers
from twisted.web.server import NOT_DONE_YET

from fluiddb.data.oauth import OAuthConsumer
from fluiddb.data.system import createSystemData
from fluiddb.model.oauth import OAuthConsumerAPI
from fluiddb.model.user import UserAPI, getUser
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.doubles import FakeRequest
from fluiddb.testing.session import login
from fluiddb.testing.resources import (
    ConfigResource, DatabaseResource, LoggingResource, ThreadPoolResource,
    CacheResource)
from fluiddb.util.transact import Transact
from fluiddb.web.oauth import RenewOAuthTokenResource


class RenewOAuthTokenResourceTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(RenewOAuthTokenResourceTest, self).setUp()
        self.transact = Transact(self.threadPool)
        createSystemData()

    @inlineCallbacks
    def testRenderWithSuccessfulVerification(self):
        """
        An C{OK} HTTP status code is returned, along with new access and
        renewal tokens, if a renewal request is successful.
        """
        UserAPI().create(
            [(u'consumer', 'secret', u'Consumer', u'consumer@example.com'),
             (u'user', 'secret', u'User', u'user@example.com')])
        consumer = getUser(u'consumer')
        user = getUser(u'consumer')
        api = OAuthConsumerAPI()
        api.register(consumer)
        token = api.getRenewalToken(consumer, user)
        self.store.commit()

        headers = {'X-FluidDB-Renewal-Token': [token.encrypt()]}
        request = FakeRequest(headers=Headers(headers))
        with login(u'consumer', consumer.objectID, self.transact) as session:
            resource = RenewOAuthTokenResource(session)
            self.assertEqual(NOT_DONE_YET, resource.render_GET(request))

            yield resource.deferred
            headers = dict(request.responseHeaders.getAllRawHeaders())
            self.assertTrue(headers['X-Fluiddb-Access-Token'])
            self.assertTrue(headers['X-Fluiddb-Renewal-Token'])
            self.assertEqual(OK, request.code)

    @inlineCallbacks
    def testRenderWithUnknownConsumer(self):
        """
        A C{BAD_REQUEST} HTTP status code is returned if an
        L{OAuthRenewalToken} for an unknown L{OAuthConsumer} is used in a
        renewal request.
        """
        UserAPI().create(
            [(u'consumer', 'secret', u'Consumer', u'consumer@example.com'),
             (u'user', 'secret', u'User', u'user@example.com')])
        consumer = getUser(u'consumer')
        user = getUser(u'consumer')
        api = OAuthConsumerAPI()
        api.register(consumer)
        token = api.getRenewalToken(consumer, user)
        headers = {'X-FluidDB-Renewal-Token': [token.encrypt()]}
        self.store.find(OAuthConsumer).remove()
        self.store.commit()

        request = FakeRequest(headers=Headers(headers))
        with login(u'consumer', consumer.objectID, self.transact) as session:
            resource = RenewOAuthTokenResource(session)
            self.assertEqual(NOT_DONE_YET, resource.render_GET(request))
            yield resource.deferred
            headers = dict(request.responseHeaders.getAllRawHeaders())
            self.assertEqual(
                {'X-Fluiddb-Error-Class': ['UnknownConsumer'],
                 'X-Fluiddb-Username': ['consumer'],
                 'X-Fluiddb-Request-Id': [session.id]},
                headers)
            self.assertEqual(BAD_REQUEST, request.code)

    @inlineCallbacks
    def testRenderWithExpiredRenewalToken(self):
        """
        An C{UNAUTHORIZED} HTTP status code is returned if an expired
        L{OAuthRenewalToken} is used in a renewal request.
        """
        UserAPI().create(
            [(u'consumer', 'secret', u'Consumer', u'consumer@example.com'),
             (u'user', 'secret', u'User', u'user@example.com')])
        consumer = getUser(u'consumer')
        user = getUser(u'consumer')
        api = OAuthConsumerAPI()
        api.register(consumer)
        creationTime = datetime.utcnow() - timedelta(hours=200)
        token = api.getRenewalToken(consumer, user, now=lambda: creationTime)
        self.store.commit()

        headers = {'X-FluidDB-Renewal-Token': [token.encrypt()]}
        request = FakeRequest(headers=Headers(headers))
        with login(u'consumer', consumer.objectID, self.transact) as session:
            resource = RenewOAuthTokenResource(session)
            self.assertEqual(NOT_DONE_YET, resource.render_GET(request))
            yield resource.deferred
            headers = dict(request.responseHeaders.getAllRawHeaders())
            self.assertEqual(
                {'X-Fluiddb-Error-Class': ['ExpiredOAuth2RenewalToken'],
                 'X-Fluiddb-Username': ['consumer'],
                 'X-Fluiddb-Request-Id': [session.id]},
                headers)
            self.assertEqual(UNAUTHORIZED, request.code)

    @inlineCallbacks
    def testRenderWithInvalidRenewalToken(self):
        """
        A C{BAD_REQUEST} HTTP status code is returned if an invalid
        L{OAuthRenewalToken} is used in a renewal request.
        """
        UserAPI().create(
            [(u'consumer', 'secret', u'Consumer', u'consumer@example.com'),
             (u'user', 'secret', u'User', u'user@example.com')])
        consumer = getUser(u'consumer')
        api = OAuthConsumerAPI()
        api.register(consumer)
        self.store.commit()

        headers = {'X-FluidDB-Renewal-Token': ['invalid']}
        request = FakeRequest(headers=Headers(headers))
        with login(u'consumer', consumer.objectID, self.transact) as session:
            resource = RenewOAuthTokenResource(session)
            self.assertEqual(NOT_DONE_YET, resource.render_GET(request))
            yield resource.deferred
            headers = dict(request.responseHeaders.getAllRawHeaders())
            self.assertEqual(
                {'X-Fluiddb-Error-Class': ['InvalidOAuth2RenewalToken'],
                 'X-Fluiddb-Username': ['consumer'],
                 'X-Fluiddb-Request-Id': [session.id]},
                headers)
            self.assertEqual(BAD_REQUEST, request.code)
