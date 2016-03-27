from json import dumps, loads

from twisted.internet.defer import succeed, fail, inlineCallbacks
from twisted.web.http_headers import Headers

from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.doubles import FakeRequest
from fluiddb.testing.resources import LoggingResource
from fluiddb.web.jsonrpc import (
    JSONRPCResource, JSONRPC_PARSE_ERROR, JSONRPC_INVALID_REQUEST,
    JSONRPC_INTERNAL_ERROR, JSONRPC_METHOD_NOT_FOUND, JSONRPC_INVALID_PARAMS)


class TestResource(JSONRPCResource):

    def jsonrpc_pass(self, session, *args, **kwargs):
        return succeed({'args': args, 'kwargs': kwargs})

    def jsonrpc_fail(self, session, *args, **kwargs):
        return fail(RuntimeError())


class JSONRPCResourceTest(FluidinfoTestCase):

    resources = [('log', LoggingResource())]

    @inlineCallbacks
    def testIncorrectContentLength(self):
        """
        An incorrect content-length headers causes a JSONRPC_PARSE_ERROR error
        which is logged.
        """
        headers = Headers({'Content-Length': ['100'],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual(JSONRPC_PARSE_ERROR, response['error']['code'])
        message = 'Invalid payload: ContentLengthMismatch.'
        self.assertEqual(message, response['error']['message'])
        self.assertIn(message, self.log.getvalue())
        self.assertIn('<Payload empty or unparseable>', self.log.getvalue())

    @inlineCallbacks
    def testMissingContentLength(self):
        """
        A missing Content-Length header causes a JSONRPC_PARSE_ERROR error
        which is logged.
        """
        headers = Headers({'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual(JSONRPC_PARSE_ERROR, response['error']['code'])
        message = 'Missing Content-Length header or empty payload.'
        self.assertEqual(message, response['error']['message'])
        self.assertIn(message, self.log.getvalue())
        self.assertIn('<Payload empty or unparseable>', self.log.getvalue())

    @inlineCallbacks
    def testMissingContentType(self):
        """
        A missing Content-Type header causes a JSONRPC_PARSE_ERROR error
        which is logged.
        """
        headers = Headers({'Content-Length': ['0']})
        request = FakeRequest(headers=headers)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual(JSONRPC_PARSE_ERROR, response['error']['code'])
        message = 'Missing Content-Type header.'
        self.assertEqual(message, response['error']['message'])
        self.assertIn(message, self.log.getvalue())
        self.assertIn('<Payload empty or unparseable>', self.log.getvalue())

    @inlineCallbacks
    def testUnparseableContentType(self):
        """
        A malformed Content-Type header causes a JSONRPC_PARSE_ERROR error
        which is logged.
        """
        headers = Headers({'Content-Type': ['papier-mache']})
        request = FakeRequest(headers=headers)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual(JSONRPC_PARSE_ERROR, response['error']['code'])
        message = 'Unparseable Content-Type header.'
        self.assertEqual(message, response['error']['message'])
        self.assertIn(message, self.log.getvalue())
        self.assertIn('<Payload empty or unparseable>', self.log.getvalue())

    @inlineCallbacks
    def testUnknownContentType(self):
        """
        An unknown Content-Type header causes a JSONRPC_PARSE_ERROR error.
        which is logged.
        """
        headers = Headers({'Content-Length': ['0'],
                           'Content-Type': ['text/papier-mache']})
        request = FakeRequest(headers=headers)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual(JSONRPC_PARSE_ERROR, response['error']['code'])
        message = 'Unknown Content-Type.'
        self.assertEqual(message, response['error']['message'])
        self.assertIn(message, self.log.getvalue())
        self.assertIn('<Payload empty or unparseable>', self.log.getvalue())

    @inlineCallbacks
    def testIncorrectContentMD5(self):
        """
        An incorrect Content-MD5 header causes a JSONRPC_PARSE_ERROR error
        which is logged.
        """
        body = dumps({'something': 42})
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-MD5': ['omg'],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual(JSONRPC_PARSE_ERROR, response['error']['code'])
        message = 'Invalid payload: ContentChecksumMismatch.'
        self.assertEqual(message, response['error']['message'])
        self.assertIn(message, self.log.getvalue())
        self.assertIn('<Payload empty or unparseable>', self.log.getvalue())

    @inlineCallbacks
    def testNonJSONPayload(self):
        """
        A non-JSON payload causes a JSONRPC_PARSE_ERROR error which is logged.
        """
        body = 'Invalid JSON'
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual(JSONRPC_PARSE_ERROR, response['error']['code'])
        message = 'Payload was not valid JSON.'
        self.assertEqual(message, response['error']['message'])
        self.assertIn(message, self.log.getvalue())
        self.assertIn('Request payload: Invalid JSON.', self.log.getvalue())

    @inlineCallbacks
    def testNonJSONObjectPayload(self):
        """
        A JSON payload that's not an object causes a JSONRPC_PARSE_ERROR error
        which is logged.
        """
        body = dumps('Not a dict')
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual(JSONRPC_PARSE_ERROR, response['error']['code'])
        message = 'Payload was not a JSON object.'
        self.assertEqual(message, response['error']['message'])
        self.assertIn(message, self.log.getvalue())
        self.assertIn('Request payload: "Not a dict".', self.log.getvalue())

    @inlineCallbacks
    def testPayloadWithNoRequestId(self):
        """
        A payload with no id causes a JSONRPC_INVALID_REQUEST error which is
        logged.

        The JSON RPC spec actually allows a request to not have an id, in
        which case it's a "notification". Let's relax our code when/if we
        get to the point of sending notifications (which don't require
        responses).
        """
        body = dumps({})
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual(JSONRPC_INVALID_REQUEST, response['error']['code'])
        message = "Request had no 'id' argument."
        self.assertEqual(message, response['error']['message'])
        self.assertIn(message, self.log.getvalue())
        self.assertIn('Request payload: {}.', self.log.getvalue())

    @inlineCallbacks
    def testPayloadWithNoJSONRPCVersion(self):
        """
        A payload with no JSON RPC version causes a JSONRPC_INVALID_REQUEST
        error which is logged.
        """
        body = dumps({'id': 100})
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual(JSONRPC_INVALID_REQUEST, response['error']['code'])
        message = "Request had no 'jsonrpc' argument."
        self.assertEqual(message, response['error']['message'])
        self.assertIn(message, self.log.getvalue())
        self.assertIn('Request payload: {"id": 100}.', self.log.getvalue())

    @inlineCallbacks
    def testPayloadWithIncorrectJSONRPCVersion(self):
        """
        A payload with an incorrect JSON RPC version causes a
        JSONRPC_INVALID_REQUEST error which is logged.
        """
        body = dumps({'id': 100, 'jsonrpc': '1.0'})
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual(JSONRPC_INVALID_REQUEST, response['error']['code'])
        message = 'Only JSON RPC version 2.0 is supported.'
        self.assertEqual(message, response['error']['message'])
        self.assertIn(message, self.log.getvalue())

    @inlineCallbacks
    def testPayloadWithNoMethodName(self):
        """
        A payload with no method name causes a JSONRPC_INVALID_REQUEST error
        which is logged.
        """
        body = dumps({'id': 100, 'jsonrpc': '2.0'})
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual(JSONRPC_INVALID_REQUEST, response['error']['code'])
        message = "Request had no 'method' argument."
        self.assertEqual(message, response['error']['message'])
        self.assertIn(message, self.log.getvalue())

    @inlineCallbacks
    def testPayloadWithUnknownMethod(self):
        """
        A payload with a method that's unknown causes a
        JSONRPC_METHOD_NOT_FOUND error which is logged.
        """
        body = dumps({'id': 100, 'jsonrpc': '2.0', 'method': 'bagpipes'})
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual(JSONRPC_METHOD_NOT_FOUND, response['error']['code'])
        message = "Unknown method u'bagpipes'."
        self.assertEqual(message, response['error']['message'])
        self.assertIn(message, self.log.getvalue())

    @inlineCallbacks
    def testPayloadWithNonDictNonListParams(self):
        """
        A payload with a method that has a params argument that is not a
        C{dict} or a C{list} causes a JSONRPC_INVALID_PARAMS error which is
        logged.
        """
        body = dumps({'id': 100, 'jsonrpc': '2.0', 'method': 'pass',
                      'params': 6})
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual(JSONRPC_INVALID_PARAMS, response['error']['code'])
        message = 'Params not an object or a list.'
        self.assertEqual(message, response['error']['message'])
        self.assertIn(message, self.log.getvalue())

    @inlineCallbacks
    def testSimpleEchoMethodReturnsId(self):
        """
        A successful method call should include the id from the request in
        its body.
        """
        body = dumps({'id': 300, 'jsonrpc': '2.0', 'method': 'pass',
                      'params': [39, 'steps']})
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual(300, response['id'])

    @inlineCallbacks
    def testSimpleEchoMethodReturnsVersion(self):
        """
        A successful method call should have the JSON RPC version in its body.
        """
        body = dumps({'id': 100, 'jsonrpc': '2.0', 'method': 'pass',
                      'params': [39, 'steps']})
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual('2.0', response['jsonrpc'])

    @inlineCallbacks
    def testSimpleEchoMethodWithListOfArgs(self):
        """A called method should be passed C{list} params."""
        body = dumps({'id': 100, 'jsonrpc': '2.0', 'method': 'pass',
                      'params': [39, 'steps']})
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual({'args': [39, 'steps'], 'kwargs': {}},
                         response['result'])

    @inlineCallbacks
    def testSimpleEchoMethodWithKeywordArgs(self):
        """A called method should be passed C{dict} params."""
        body = dumps({'id': 100, 'jsonrpc': '2.0', 'method': 'pass',
                      'params': {'ingredient1': 'sugar',
                                 'ingredient2': 'spice'}})
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual({'args': [], 'kwargs': {'ingredient1': 'sugar',
                                                 'ingredient2': 'spice'}},
                         response['result'])

    @inlineCallbacks
    def testSimpleFailingMethodReturnsId(self):
        """
        A failing method call should include the id from the request in its
        body.
        """
        body = dumps({'id': 300, 'jsonrpc': '2.0', 'method': 'fail',
                      'params': [39, 'steps']})
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual(300, response['id'])

    @inlineCallbacks
    def testSimpleFailingMethodReturnsVersion(self):
        """
        A failing method call should have the JSON RPC version in its body.
        """
        body = dumps({'id': 100, 'jsonrpc': '2.0', 'method': 'fail',
                      'params': [39, 'steps']})
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual('2.0', response['jsonrpc'])

    @inlineCallbacks
    def testSimpleFailingMethodReturnsErrorWithCodeAndMessage(self):
        """
        A failing method should return an error dictionary containing a
        code and a message.
        """
        body = dumps({'id': 100, 'jsonrpc': '2.0', 'method': 'fail',
                      'params': {}})
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertTrue('code' in response['error'])
        self.assertTrue('message' in response['error'])

    @inlineCallbacks
    def testSimpleFailingMethodReturnsRequestIDInResponseHeader(self):
        """A failing method returns an X-FluidDB-Request-Id HTTP header."""
        body = dumps({'id': 100, 'jsonrpc': '2.0', 'method': 'fail',
                      'params': {}})
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        yield resource.deferred_render_POST(request)
        self.assertTrue(request.responseHeaders.hasHeader(
            'X-FluidDB-Request-Id'))

    @inlineCallbacks
    def testSimpleFailingMethodLogsJSONRPCError(self):
        """A failing method logs a JSON RPC error."""
        body = dumps({'id': 100, 'jsonrpc': '2.0', 'method': 'fail',
                      'params': {}})
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        yield resource.deferred_render_POST(request)
        self.assertIn('JSON RPC error.', self.log.getvalue())

    @inlineCallbacks
    def testSimpleFailingMethodLogsTheRequestPayload(self):
        """A failing method logs the request payload."""
        body = dumps({'id': 100, 'jsonrpc': '2.0', 'method': 'fail',
                      'params': {}})
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        yield resource.deferred_render_POST(request)
        self.assertIn('Request payload: ', self.log.getvalue())

    @inlineCallbacks
    def testLongRequestPayloadIsTruncatedInErrorLog(self):
        """
        A failing call that sends a long payload must have the request
        payload truncated in the log.
        """
        body = dumps({'id': 100, 'jsonrpc': '2.0', 'method': 'fail',
                      'params': {'long': '+' * 1000}})
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        yield resource.deferred_render_POST(request)
        self.assertIn('... <payload truncated for logging>',
                      self.log.getvalue())

    @inlineCallbacks
    def testSimpleFailingMethodLogsTheResponsePayload(self):
        """A failing method logs the response payload."""
        body = dumps({'id': 100, 'jsonrpc': '2.0', 'method': 'fail',
                      'params': {}})
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        yield resource.deferred_render_POST(request)
        self.assertIn('Response payload: ', self.log.getvalue())

    @inlineCallbacks
    def testFailureReturnsInternalErrorCode(self):
        """
        A method that raises an exception results in a
        C{JSONRPC_INTERNAL_ERROR} error code.  A message is written to the
        log.
        """
        body = dumps({'id': 100, 'jsonrpc': '2.0', 'method': 'fail',
                      'params': {}})
        headers = Headers({'Content-Length': [str(len(body))],
                           'Content-Type': ['application/json']})
        request = FakeRequest(headers=headers, body=body)
        resource = TestResource(None, None)
        result = yield resource.deferred_render_POST(request)
        response = loads(result)
        self.assertEqual({'code': JSONRPC_INTERNAL_ERROR,
                          'message': 'Internal error.'},
                         response['error'])
        self.assertIn('exceptions.RuntimeError', self.log.getvalue())
