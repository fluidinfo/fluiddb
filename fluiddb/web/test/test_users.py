from json import dumps, loads

from twisted.internet import defer
from twisted.web import http
from twisted.web.http_headers import Headers
from twisted.web.server import NOT_DONE_YET

from fluiddb.api.facade import Facade
from fluiddb.application import FluidinfoSessionFactory
from fluiddb.data.system import createSystemData
from fluiddb.model.oauth import OAuthConsumerAPI
from fluiddb.model.user import UserAPI, getUser
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.doubles import FakeRequest
from fluiddb.testing.resources import (
    CacheResource, ConfigResource, DatabaseResource, LoggingResource,
    ThreadPoolResource, IndexResource)
from fluiddb.testing.session import login
from fluiddb.util.transact import Transact
from fluiddb.web.users import VerifyUserPasswordResource, ConcreteUserResource


class ConcreteUserResourceTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('client', IndexResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(ConcreteUserResourceTest, self).setUp()
        createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        factory = FluidinfoSessionFactory('API-9000')
        self.transact = Transact(self.threadPool)
        self.facade = Facade(self.transact, factory)
        self.store.commit()

    @defer.inlineCallbacks
    def testGET(self):
        """
        A GET request on /users/<username> returns the complete details about
        the user.
        """
        request = FakeRequest()
        with login(u'username', self.user.objectID, self.transact) as session:
            resource = ConcreteUserResource(self.facade, session, 'username')
            body = yield resource.deferred_render_GET(request)
            body = loads(body)
            expected = {"role": "USER",
                        "name": "User",
                        "id": str(self.user.objectID)}
            self.assertEqual(expected, body)
            self.assertEqual(http.OK, request.code)

    @defer.inlineCallbacks
    def testPUT(self):
        """
        A PUT request on C{/users/<username>} updates the data for the user.
        """
        body = dumps({'name': 'New name',
                      'email': 'new@example.com',
                      'role': 'USER_MANAGER'})

        headers = Headers({'content-length': [len(body)],
                           'content-type': ['application/json']})

        request = FakeRequest(body=body, headers=headers)
        with login(u'username', self.user.objectID, self.transact) as session:
            resource = ConcreteUserResource(self.facade, session, 'username')
            yield resource.deferred_render_PUT(request)
            self.assertEqual(http.NO_CONTENT, request.code)
            body = yield resource.deferred_render_GET(FakeRequest())
            body = loads(body)
            expected = {'role': 'USER_MANAGER',
                        'name': 'New name',
                        'id': str(self.user.objectID)}
            self.assertEqual(expected, body)

    @defer.inlineCallbacks
    def testPUTToUpdateRoleOnly(self):
        """
        A PUT request on C{/users/<username>} can update only the role for the
        user even if other arguments are not given.
        """
        body = dumps({'role': 'USER_MANAGER'})

        headers = Headers({'content-length': [len(body)],
                           'content-type': ['application/json']})

        request = FakeRequest(body=body, headers=headers)
        with login(u'username', self.user.objectID, self.transact) as session:
            resource = ConcreteUserResource(self.facade, session, 'username')
            yield resource.deferred_render_PUT(request)
            self.assertEqual(http.NO_CONTENT, request.code)
            body = yield resource.deferred_render_GET(FakeRequest())
            body = loads(body)
            expected = {'role': 'USER_MANAGER',
                        'name': 'User',
                        'id': str(self.user.objectID)}
            self.assertEqual(expected, body)


class VerifyUserPasswordResourceTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(VerifyUserPasswordResourceTest, self).setUp()
        self.transact = Transact(self.threadPool)
        createSystemData()
        UserAPI().create([
            (u'fluidinfo.com', 'secret', u'Fluidinfo', u'info@example.com'),
            (u'user', u'pass', u'Peter Parker', u'user@example.com')])
        consumer = getUser(u'anon')
        OAuthConsumerAPI().register(consumer)
        self.store.commit()

    @defer.inlineCallbacks
    def testPostWithCorrectPasswordReturnsCorrectKeys(self):
        """
        A C{POST} to C{/users/user/verify} with the correct password returns a
        JSON object with all the expected keys, including valid = True.
        """
        with login(None, None, self.transact) as session:
            resource = VerifyUserPasswordResource(None, session, 'user')
            payload = dumps({'password': 'pass'})
            headers = {'Content-Length': [str(len(payload))],
                       'Content-Type': ['application/json'],
                       'X-Forwarded-Protocol': ['https']}
            request = FakeRequest(method='POST', headers=Headers(headers),
                                  body=payload)
            self.assertEqual(NOT_DONE_YET, resource.render(request))

            yield resource.deferred
            self.assertEqual(request.code, http.OK)
            result = loads(request.response)
            self.assertEqual(
                ['accessToken', 'fullname', 'renewalToken', 'role', 'valid'],
                sorted(result.keys()))
            self.assertTrue(result['valid'])

    @defer.inlineCallbacks
    def testPostWithCorrectPasswordDoesNotCauseALogWarning(self):
        """
        A C{POST} to C{/users/user/verify} with the correct password should
        not cause a complaint about unknown return payload fields in the
        logging system.
        """
        with login(None, None, self.transact) as session:
            resource = VerifyUserPasswordResource(None, session, 'user')
            payload = dumps({'password': 'pass'})
            headers = {'Content-Length': [str(len(payload))],
                       'Content-Type': ['application/json'],
                       'X-Forwarded-Protocol': ['https']}
            request = FakeRequest(method='POST', headers=Headers(headers),
                                  body=payload)
            self.assertEqual(NOT_DONE_YET, resource.render(request))

            yield resource.deferred
            logOutput = self.log.getvalue()
            self.assertNotIn("unknown response payload field 'renewalToken'",
                             logOutput)
            self.assertNotIn("unknown response payload field 'accessToken'",
                             logOutput)

    @defer.inlineCallbacks
    def testPostWithCorrectPasswordReturnsCorrectRole(self):
        """
        A C{POST} to C{/users/user/verify} with the correct password returns a
        JSON object with the correct user role.
        """
        with login(None, None, self.transact) as session:
            resource = VerifyUserPasswordResource(None, session, 'user')
            payload = dumps({'password': 'pass'})
            headers = {'Content-Length': [str(len(payload))],
                       'Content-Type': ['application/json'],
                       'X-Forwarded-Protocol': ['https']}
            request = FakeRequest(method='POST', headers=Headers(headers),
                                  body=payload)
            self.assertEqual(NOT_DONE_YET, resource.render(request))

            yield resource.deferred
            self.assertEqual(request.code, http.OK)
            result = loads(request.response)
            self.assertEqual('USER', result['role'])

    @defer.inlineCallbacks
    def testPostWithCorrectPasswordReturnsCorrectFullname(self):
        """
        A C{POST} to C{/users/user/verify} with the correct password returns a
        JSON object with the user's correct full name.
        """
        with login(None, None, self.transact) as session:
            resource = VerifyUserPasswordResource(None, session, 'user')
            payload = dumps({'password': 'pass'})
            headers = {'Content-Length': [str(len(payload))],
                       'Content-Type': ['application/json'],
                       'X-Forwarded-Protocol': ['https']}
            request = FakeRequest(method='POST', headers=Headers(headers),
                                  body=payload)
            self.assertEqual(NOT_DONE_YET, resource.render(request))

            yield resource.deferred
            self.assertEqual(request.code, http.OK)
            result = loads(request.response)
            self.assertEqual(u'Peter Parker', result['fullname'])

    @defer.inlineCallbacks
    def testPostWithIncorrectPasswordReturnsFalse(self):
        """
        A C{POST} to C{/users/user/verify} with the incorrect password returns
        a C{{'valid': False}} response.
        """
        with login(None, None, self.transact) as session:
            resource = VerifyUserPasswordResource(None, session, 'user')
            payload = dumps({'password': 'wrong'})
            headers = {'Content-Length': [str(len(payload))],
                       'Content-Type': ['application/json'],
                       'X-Forwarded-Protocol': ['https']}
            request = FakeRequest(method='POST', headers=Headers(headers),
                                  body=payload)
            self.assertEqual(NOT_DONE_YET, resource.render(request))

            yield resource.deferred
            self.assertEqual(request.code, http.OK)
            self.assertEqual(loads(request.response), {'valid': False})

    @defer.inlineCallbacks
    def testPostWithUnknownUsernameReturnsNotFound(self):
        """
        A C{POST} to C{/users/user/verify} with an unknown username returns a
        404 Not Found.
        """
        with login(None, None, self.transact) as session:
            resource = VerifyUserPasswordResource(None, session, 'unknown')
            payload = dumps({'password': 'wrong'})
            headers = {'Content-Length': [str(len(payload))],
                       'Content-Type': ['application/json'],
                       'X-Forwarded-Protocol': ['https']}
            request = FakeRequest(method='POST', headers=Headers(headers),
                                  body=payload)
            self.assertEqual(NOT_DONE_YET, resource.render(request))

            yield resource.deferred
            self.assertEqual(request.code, http.NOT_FOUND)

    @defer.inlineCallbacks
    def testPostWithoutPasswordReturnsBadRequest(self):
        """
        A C{POST} to C{/users/user/verify} without a password returns a 400
        Bad Request.
        """
        with login(None, None, self.transact) as session:
            resource = VerifyUserPasswordResource(None, session, 'user')
            payload = ''
            headers = {'Content-Length': [str(len(payload))],
                       'Content-Type': ['application/json'],
                       'X-Forwarded-Protocol': ['https']}
            request = FakeRequest(method='POST', headers=Headers(headers),
                                  body=payload)
            self.assertEqual(NOT_DONE_YET, resource.render(request))

            yield resource.deferred
            self.assertEqual(request.code, http.BAD_REQUEST)

    @defer.inlineCallbacks
    def testPostWithExtraCrapInPayloadReturnsBadRequest(self):
        """
        A C{POST} to C{/users/user/verify} with unexpected data in the payload
        returns a 400 Bad Request.
        """
        with login(None, None, self.transact) as session:
            resource = VerifyUserPasswordResource(None, session, 'user')
            payload = dumps({'password': 'pass', 'foo': 'bar'})
            headers = {'Content-Length': [str(len(payload))],
                       'Content-Type': ['application/json'],
                       'X-Forwarded-Protocol': ['https']}
            request = FakeRequest(method='POST', headers=Headers(headers),
                                  body=payload)
            self.assertEqual(NOT_DONE_YET, resource.render(request))

            yield resource.deferred
            self.assertEqual(request.code, http.BAD_REQUEST)

    @defer.inlineCallbacks
    def testInsecurePostIsRejected(self):
        """A C{POST} via HTTP is rejected if not in development mode."""
        self.config.set('service', 'development', 'false')
        with login(None, None, self.transact) as session:
            resource = VerifyUserPasswordResource(None, session, 'user')
            payload = ''
            headers = {'Content-Length': [str(len(payload))],
                       'Content-Type': ['application/json']}
            request = FakeRequest(method='POST', headers=Headers(headers),
                                  body=payload)
            self.assertEqual(NOT_DONE_YET, resource.render(request))

            yield resource.deferred
            self.assertEqual(request.code, http.BAD_REQUEST)
            self.assertEqual(
                request.getResponseHeader('X-FluidDB-Message'),
                '/users/<username>/verify requests must use HTTPS')

    @defer.inlineCallbacks
    def testInsecurePostIsNotRejectedInDevelopmentMode(self):
        """A C{POST} via HTTP is not rejected when in development mode."""
        self.config.set('service', 'development', 'true')
        with login(None, None, self.transact) as session:
            resource = VerifyUserPasswordResource(None, session, 'user')
            payload = dumps({'password': 'pass'})
            headers = {'Content-Length': [str(len(payload))],
                       'Content-Type': ['application/json']}
            request = FakeRequest(method='POST', headers=Headers(headers),
                                  body=payload)
            self.assertEqual(NOT_DONE_YET, resource.render(request))

            yield resource.deferred
            self.assertEqual(request.code, http.OK)
