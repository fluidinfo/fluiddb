# -*- coding: utf-8 -*-

from xml.etree import ElementTree

from twisted.internet import defer

from fluiddb.common import defaults

from twisted.internet import reactor
from twisted.internet.protocol import Protocol
from twisted.web.client import Agent
from twisted.web import http

from integration.wsfe import base


class ResponseGetter(Protocol):
    __buffer = ''

    def __init__(self, finished):
        self._finished = finished

    def dataReceived(self, bytes):
        self.__buffer += bytes

    def connectionLost(self, reason):
        self._finished.callback(self.__buffer)


class TestCrossdomain(base.HTTPTest):

    def setUp(self):
        base.HTTPTest.setUp(self)
        self.uri = '%s/%s' % (self.endpoint, defaults.httpCrossdomainName)

    @defer.inlineCallbacks
    def testResponseCodeAndContentType(self):
        agent = Agent(reactor)
        response = yield agent.request('GET', self.uri)

        # Check we get the correct status.
        self.assertEqual(http.OK, response.code)

        # Check we get the correct MIME-type.
        self.assertTrue(
            'text/xml' in response.headers.getRawHeaders('Content-Type'))

    @defer.inlineCallbacks
    def testExpectedResponse(self):
        agent = Agent(reactor)
        response = yield agent.request('GET', self.uri)

        d = defer.Deferred()
        protocol = ResponseGetter(d)
        response.deliverBody(protocol)
        page = yield d

        # Check that the reponse is well-formed XML.
        try:
            tree = ElementTree.fromstring(page)
        except:
            self.fail('Could not parse crossdomain XML response: %r' % (tree,))

        # Explicitly test that we get exactly what's in
        # wsfe/service/web/root.py
        self.assertEqual(page, '''<?xml version="1.0"?>
        <!DOCTYPE cross-domain-policy SYSTEM "http://www.macromedia.com/xml/
        dtds/cross-domain-policy.dtd">
        <cross-domain-policy>
        <allow-http-request-headers-from domain="*" headers="*"/>
        </cross-domain-policy>''')
