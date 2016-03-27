# -*- coding: utf-8 -*-
import os

from twisted.internet import defer
from twisted.trial import unittest
from twisted.internet import reactor
from twisted.internet.protocol import Protocol
from twisted.web.client import Agent
from twisted.web import http
from twisted.web.http_headers import Headers


class ResponseGetter(Protocol):
    __buffer = ''

    def __init__(self, finished):
        self._finished = finished

    def dataReceived(self, bytes):
        self.__buffer += bytes

    def connectionLost(self, reason):
        self._finished.callback(self.__buffer)


class TestOptions(unittest.TestCase):

    def setUp(self):
        endpoint = os.environ.get('FLUIDDB_ENDPOINT', 'http://localhost:9000')
        namespace_name = 'testuser1'
        toplevel = 'namespaces'
        self.uri = '%s/%s/%s' % (endpoint, toplevel, namespace_name)

    @defer.inlineCallbacks
    def testValidCORSRequest(self):
        """
        Sanity check to make sure we get the valid headers back for a CORS
        based request.
        """
        agent = Agent(reactor)
        headers = Headers()
        # The origin to use in the tests
        dummy_origin = 'http://foo.com'
        headers.addRawHeader('Origin', dummy_origin)
        response = yield agent.request('GET', self.uri, headers)

        # Check we get the correct status.
        self.assertEqual(http.OK, response.code)
        # Check we get the right headers back
        self.assertTrue(
            response.headers.hasHeader('Access-Control-Allow-Origin'))
        self.assertTrue(
            response.headers.hasHeader('Access-Control-Allow-Credentials'))
        self.assertTrue(
            dummy_origin in
            response.headers.getRawHeaders('Access-Control-Allow-Origin'))
