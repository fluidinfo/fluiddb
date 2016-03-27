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
    """
    Copied verbatim from other test modules in this directory
    """

    __buffer = ''

    def __init__(self, finished):
        self._finished = finished

    def dataReceived(self, bytes):
        self.__buffer += bytes

    def connectionLost(self, reason):
        self._finished.callback(self.__buffer)


class TestOptions(unittest.TestCase):
    """
    Integration tests to sanity check the handling of OPTIONS based requests
    """

    def setUp(self):
        endpoint = os.environ.get('FLUIDDB_ENDPOINT', 'http://localhost:9000')
        toplevel = 'namespaces'
        namespace_name = 'fluiddb'
        self.uri = '%s/%s/%s' % (endpoint, toplevel, namespace_name)

    @defer.inlineCallbacks
    def testValidCORSRequest(self):
        """
        Checks a valid CORS request results in the correct headers being set in
        the response.
        """
        agent = Agent(reactor)
        headers = Headers()
        # The origin to use in the tests
        dummyOrigin = 'http://foo.com'
        headers.addRawHeader('Origin', dummyOrigin)
        headers.addRawHeader('Access-Control-Request-Method', 'GET')
        headers.addRawHeader('Access-Control-Request-Headers', 'Content-Type')
        response = yield agent.request('OPTIONS', self.uri, headers)

        # Check we get the correct status.
        self.assertEqual(http.OK, response.code)

        # Check we get the correct length
        self.assertEqual(0, response.length)

        # Check we get the right headers back
        self.assertTrue(response.headers.hasHeader('Allow'))
        self.assertTrue(
            response.headers.hasHeader('Access-Control-Allow-Origin'))
        self.assertTrue(response.headers.hasHeader('Access-Control-Max-Age'))
        self.assertTrue(
            response.headers.hasHeader('Access-Control-Allow-Credentials'))
        self.assertTrue(
            response.headers.hasHeader('Access-Control-Allow-Methods'))
        self.assertTrue(
            response.headers.hasHeader('Access-Control-Allow-Headers'))
        self.assertTrue(
            dummyOrigin in
            response.headers.getRawHeaders('Access-Control-Allow-Origin'))
        self.assertTrue(
            'Content-Type' in
            response.headers.getRawHeaders('Access-Control-Allow-Headers')[0])
        self.assertTrue(
            'Authorization' in
            response.headers.getRawHeaders('Access-Control-Allow-Headers')[0])
        self.assertTrue(
            'Accept' in
            response.headers.getRawHeaders('Access-Control-Allow-Headers')[0])

    @defer.inlineCallbacks
    def testCORSRequestWithoutAccessControlRequestHeaders(self):
        """
        Checks a valid CORS request results in the correct headers being set in
        the response but without including Access-Control-Request-Headers (for
        the sake of reproducing a Webkit based bug).
        """
        agent = Agent(reactor)
        headers = Headers()
        # The origin to use in the tests
        dummyOrigin = 'http://foo.com'
        headers.addRawHeader('Origin', dummyOrigin)
        headers.addRawHeader('Access-Control-Request-Method', 'GET')
        response = yield agent.request('OPTIONS', self.uri, headers)

        # Check we get the correct status.
        self.assertEqual(http.OK, response.code)

        # Check we get the correct length
        self.assertEqual(0, response.length)

        # Check we get the right headers back
        self.assertTrue(response.headers.hasHeader('Allow'))
        self.assertTrue(
            response.headers.hasHeader('Access-Control-Allow-Origin'))
        self.assertTrue(response.headers.hasHeader('Access-Control-Max-Age'))
        self.assertTrue(
            response.headers.hasHeader('Access-Control-Allow-Credentials'))
        self.assertTrue(
            response.headers.hasHeader('Access-Control-Allow-Methods'))
        self.assertTrue(
            response.headers.hasHeader('Access-Control-Allow-Headers'))
        self.assertTrue(
            dummyOrigin in
            response.headers.getRawHeaders('Access-Control-Allow-Origin'))
        self.assertTrue(
            'Content-Type' in
            response.headers.getRawHeaders('Access-Control-Allow-Headers')[0])
        self.assertTrue(
            'Authorization' in
            response.headers.getRawHeaders('Access-Control-Allow-Headers')[0])

    @defer.inlineCallbacks
    def testValidOptionsRequest(self):
        """
        Makes sure that a "regular" OPTIONS request doesn't include the CORS
        specific headers in the response.
        """
        agent = Agent(reactor)
        headers = Headers({'origin': ['http://localhost']})
        response = yield agent.request('OPTIONS', self.uri, headers)

        # Check we get the correct status.
        self.assertEqual(http.OK, response.code)

        # Check we get the correct length
        self.assertEqual(0, response.length)

        # Check we get the right headers back
        self.assertTrue(response.headers.hasHeader('Allow'))
        self.assertFalse(
            response.headers.hasHeader('Access-Control-Allow-Origin'))
        self.assertFalse(response.headers.hasHeader('Access-Control-Max-Age'))
        self.assertFalse(
            response.headers.hasHeader('Access-Control-Allow-Credentials'))
        self.assertFalse(
            response.headers.hasHeader('Access-Control-Allow-Methods'))
