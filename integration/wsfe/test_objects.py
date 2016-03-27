# -*- coding: utf-8 -*-

import json
import urllib
import re
from base64 import b64encode

from urllib import urlencode

from twisted.web import http
from twisted.web.error import Error
from twisted.internet import defer, reactor
from twisted.python import log
from twisted.internet.protocol import Protocol
from twisted.web.client import Agent, ResponseDone
from twisted.web.http_headers import Headers

from fluiddb.common import error, defaults
from fluiddb.common import paths
from fluiddb.common.types_thrift.ttypes import TParseError
from fluiddb.web.util import buildHeader

from integration.wsfe import base
import txbase
from integration.wsfe.http import getPage


class ResponseGetter(Protocol):
    _buffer = ''

    def __init__(self, finished):
        self._finished = finished

    def dataReceived(self, bytes):
        self._buffer += bytes

    def connectionLost(self, reason):
        reason.trap(ResponseDone)
        self._finished.callback(self._buffer)


class ObjectsTest(txbase.TxFluidDBTest, base.HTTPTest):
    """
    A base class for our FluidDB objects tests.

    Note: for the time being this class still inherits from base.HTTPTest
    so that we can have tests that use both txFluidDB and the methods in
    base.HTTPTest. Once we have replaced everything from base.HTTPTest,
    this class will disappear entirely.
    """

    toplevel = defaults.httpObjectCategoryName

    def setUp(self):
        """
        Initialize both our superclasses.
        """
        txbase.TxFluidDBTest.setUp(self)
        base.HTTPTest.setUp(self)


class TestPOST(ObjectsTest):
    """
    Use POST to test the creation of new objects.

    NOTE: This will subclass base.TxFluidDBTest once we get rid of
    base.HTTPTest.
    """

    # NOTE: verb will go away once we get rid of base.HTTPTest.
    verb = 'POST'

    @defer.inlineCallbacks
    def testViaAgent(self):
        """
        This is a manual check of a POST to /objects which uses
        L{twisted.web.client.Agent} to make the request. We do not use
        txFluidDB because we need to check that a Location header is
        received and that we receive both a 'URI' and an 'id' in the JSON
        response payload.
        """
        URI = self.txEndpoint.getRootURL() + defaults.httpObjectCategoryName
        basicAuth = 'Basic %s' % b64encode('%s:%s' % ('testuser1', 'secret'))
        headers = Headers({'accept': ['application/json'],
                           'authorization': [basicAuth]})
        agent = Agent(reactor)
        response = yield agent.request('POST', URI, headers)
        self.assertEqual(http.CREATED, response.code)
        self.assertTrue(response.headers.hasHeader('location'))
        d = defer.Deferred()
        bodyGetter = ResponseGetter(d)
        response.deliverBody(bodyGetter)
        body = yield d
        responseDict = json.loads(body)
        self.assertIn('URI', responseDict)
        self.assertIn('id', responseDict)

    @base.showFailures
    @defer.inlineCallbacks
    def testMultipleSimultaneousCreateSameAbout(self):
        deferreds = []
        for _ in range(100):
            deferreds.append(self.createObject(about='xx'))
        results = yield defer.DeferredList(deferreds, consumeErrors=True)
        failed = False
        objectId = None
        for result in results:
            if result[0]:
                if objectId is None:
                    objectId = result[1]
                else:
                    self.assertEqual(objectId, result[1])
            else:
                failed = True
                log.err(result[1])
        if failed:
            self.fail()

    @base.showFailures
    @defer.inlineCallbacks
    def testMultipleSimultaneousUpdateSameAbout(self):
        aboutValue = 'yy'
        objectId = yield self.createObject(about=aboutValue)
        deferreds = []
        for _ in range(100):
            deferreds.append(self.createObject(about=aboutValue))
        results = yield defer.DeferredList(deferreds, consumeErrors=True)
        failed = False
        for result in results:
            if result[0]:
                self.assertEqual(objectId, result[1])
            else:
                failed = True
                log.err(result[1])
        if failed:
            self.fail()

    @defer.inlineCallbacks
    def testSimpleJSONP(self):
        basicAuth = 'Basic %s' % b64encode('%s:%s' % ('testuser1', 'secret'))
        headers = {'accept': 'application/json',
                   'authorization': basicAuth}
        uri = '%s/%s' % (self.endpoint, defaults.httpObjectCategoryName)
        callback = 'foo'
        params = {
            'callback': callback,
            'verb': 'POST',
        }

        uriCB = uri + '?' + urlencode(params)

        status, responseHeaders, responseCB = yield getPage(uriCB,
                                                            headers=headers)

        m = re.match('%s\((.*)\)' % callback, responseCB)

        self.assertNotEqual(None, m)

        # XXX JSON hardcoded
        d = json.loads(m.group(1))

        # XXX hardcoded id field
        # Test that the id can be turned into a UUID
        import uuid
        self.assertNotEqual(None, uuid.UUID(d['id']))

    @defer.inlineCallbacks
    def testSimpleAboutJSONP(self):
        basicAuth = 'Basic %s' % b64encode('%s:%s' % ('testuser1', 'secret'))
        headers = {'accept': 'application/json',
                   'authorization': basicAuth}
        uri = '%s/%s' % (self.endpoint, defaults.httpObjectCategoryName)
        aboutStr = 'random string'
        data = {'about': aboutStr}
        callback = 'foo'
        payload = json.dumps(data)

        params = {
            'callback': callback,
            'verb': 'POST',
            'payload': payload,
            'payload-type': 'application/json',
            'payload-length': len(payload),
        }

        uriCB = uri + '?' + urlencode(params)
        status, responseHeaders, responseCB = yield getPage(uriCB,
                                                            headers=headers)
        m = re.match('%s\((.*)\)' % callback, responseCB)

        self.assertNotEqual(None, m)

        # XXX JSON hardcoded
        d = json.loads(m.group(1))

        # XXX hardcoded id field
        oid = str(d['id'])

        uriValue = defaults.sep.join([uri, oid,
                                      defaults.sep.join(paths.aboutPath())])
        status, responseHeaders, responseValue = yield getPage(uriValue)
        # XXX JSON hardcoded
        self.assertEqual(aboutStr, json.loads(responseValue))

    @base.showFailures
    def testNoAbout(self):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        data = {}
        d = getPage(
            '%s/%s' % (self.endpoint, defaults.httpObjectCategoryName),
            headers=headers, method='POST', postdata=json.dumps(data))
        d.addCallback(self.checkStatus, http.CREATED)
        d.addCallback(self.checkPayloadHas, dict.fromkeys(['id', 'URI']))
        d.addCallback(self.checkHeaders, dict.fromkeys(['location']))
        return d

    @base.showFailures
    def testNoAboutNoPayload(self):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = getPage(
            '%s/%s' % (self.endpoint, defaults.httpObjectCategoryName),
            headers=headers, method='POST')
        d.addCallback(self.checkStatus, http.CREATED)
        return d

    @base.showFailures
    def testNoAcceptHeader(self):
        headers = {
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        data = {
            'about': 'wee-hoo',
        }
        d = getPage(
            '%s/%s' % (self.endpoint, defaults.httpObjectCategoryName),
            headers=headers, method='POST', postdata=json.dumps(data))
        d.addCallback(self.checkHeaders, {'content-type': 'application/json'})
        return d

    @base.showFailures
    def testUnknownPayloadField(self):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        data = {
            'xxx_about': 'wee-hoo',
        }
        d = getPage(
            '%s/%s' % (self.endpoint, defaults.httpObjectCategoryName),
            headers=headers, method='POST', postdata=json.dumps(data))
        d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'):
             error.UnknownPayloadField.__name__})
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    @defer.inlineCallbacks
    def testBadTypes(self):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        for field in ('about',):
            data = {
                'about': 'Nicholas Radcliffe, Esq.',
            }
            for value in (None, 3, 6.7, True, False, ['a', 'list'], {'x': 3}):
                data[field] = value
                d = self.getPage('', headers=headers,
                                 postdata=json.dumps(data))
                d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
                d.addErrback(
                    self.checkErrorHeaders,
                    {buildHeader('Error-Class'):
                     error.InvalidPayloadField.__name__})
                self.failUnlessFailure(d, Error)
                yield d

    @defer.inlineCallbacks
    def testUnicodeAbout(self):
        """
        Try to create an object with a Unicode about value.
        """
        objectId = yield self.createObject(u'\xf8')
        self.assertTrue(objectId is not None)


class TestGET(ObjectsTest):

    verb = 'GET'

    @base.showFailures
    @defer.inlineCallbacks
    def testQueryParseErrorNoPath(self):
        # This query does not parse because 'big' is not a path (no slash).
        query = 'has big'
        d = self.query(query)
        d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'): TParseError.__name__})
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Query'): query})
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Message'): "Illegal character u'b'."})
        self.failUnlessFailure(d, Error)
        yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testQueryParseErrorExtraParen(self):
        query = 'has big/feet except has (big/ears'
        d = self.query(query)
        d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'): TParseError.__name__})
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Query'): query})
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Message'): "Syntax error: production.value = u'('"})
        self.failUnlessFailure(d, Error)
        yield d

    @base.showFailures
    def testNoAcceptHeader(self):
        headers = {}
        self.addBasicAuthHeader(headers)
        q = '%s = "xxx"' % defaults.sep.join(paths.aboutPath())
        d = getPage(
            '%s/%s?query=%s' % (self.endpoint,
                                defaults.httpObjectCategoryName,
                                urllib.quote_plus(q)),
            headers=headers, method='GET')
        d.addCallback(self.checkHeaders, {'content-type': 'application/json'})
        return d

    @base.showFailures
    def testNoQuery(self):
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = getPage('%s/%s' % (self.endpoint, defaults.httpObjectCategoryName),
                    headers=headers, method='GET')
        d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'): error.MissingArgument.__name__})
        self.failUnlessFailure(d, Error)
        return d

    @defer.inlineCallbacks
    def testHasJSONP(self):
        objectId = yield self.createObject()
        yield self.setTagValue('fluiddb/testing/test1', objectId, 'a string')

        try:
            headers = {}
            self.addBasicAuthHeader(headers)

            params = {
                'query': 'has fluiddb/testing/test1'.encode('utf-8'),
            }
            uri = '%s/%s' % (self.endpoint, defaults.httpObjectCategoryName)

            uriNoCB = uri + '?' + urlencode(params)
            status, responseHeaders, responseNoCB = yield getPage(
                uriNoCB, headers=headers)

            callback = 'foo'
            params['callback'] = callback.encode('utf-8')

            uriCB = uri + '?' + urlencode(params)
            status, responseHeaders, responseCB = yield getPage(
                uriCB, headers=headers)

            self.assertEqual('%s(%s)' % (callback, responseNoCB), responseCB)
        finally:
            yield self.deleteTagValue('fluiddb/testing/test1', objectId)

    @base.showFailures
    @defer.inlineCallbacks
    def testQueryUnicodeAbout(self):
        aboutStr = u'\xf8'
        objectId = yield self.createObject(about=aboutStr)
        results = yield self.query(
            '%s = "%s"' % (defaults.sep.join(paths.aboutPath()), aboutStr))
        self.assertEqual(len(results), 1)
        self.assertEqual(objectId, results[0])
        objectInfo = yield self.getObject(str(objectId), showAbout=True)
        self.assertEqual(objectInfo['about'], aboutStr)

    @defer.inlineCallbacks
    def testQueryUnicodePath(self):
        """A query on a non-existent Unicode tag, should 404. Part of the
        point here is to make sure that no other error occurs due to
        passing in a Unicode tag path.
        """
        path = u'çóñ/汉ﻱλ'
        query = '%s = "hi"' % path
        URI = '%s/%s?query=%s' % (
            self.endpoint,
            defaults.httpObjectCategoryName,
            urllib.quote(query.encode('utf-8')))

        headers = Headers({'accept': ['application/json']})

        agent = Agent(reactor)
        response = yield agent.request('GET', URI, headers)

        self.assertEqual(http.NOT_FOUND, response.code)

    @defer.inlineCallbacks
    def testQueryMalformedUTF8ViaAgent(self):
        """Sending malformed UTF-8 should get us a BAD_REQUEST response as
        the facade will not be able to decode the (bad) UTF-8 into Unicode
        in order to pass it to the query parser.
        """
        URI = '%s/%s?query=\xFF' % (self.endpoint,
                                    defaults.httpObjectCategoryName)
        headers = Headers({'accept': ['application/json']})

        agent = Agent(reactor)
        response = yield agent.request('GET', URI, headers)

        self.assertEqual(http.BAD_REQUEST, response.code)


class TestPUT(ObjectsTest):

    verb = 'PUT'

    @base.showFailures
    def testNotImplemented(self):
        d = self.getPage(base.randomObjectIdStr())
#        TODO: Nginx returns 411 in this case. See Bug #676947.
#        d.addErrback(self.checkErrorStatus, http.NOT_IMPLEMENTED)
        self.failUnlessFailure(d, Error)
        return d


class TestDELETE(ObjectsTest):

    verb = 'DELETE'

    @base.showFailures
    def testNotImplemented(self):
        d = self.getPage(base.randomObjectIdStr())
        d.addErrback(self.checkErrorStatus, http.NOT_IMPLEMENTED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    @defer.inlineCallbacks
    def testTagNotPresent(self):
        objectId = yield self.createObject()
        yield self.deleteTagValue(defaults.sep.join(paths.aboutPath()),
                                  objectId)

    @base.showFailures
    def testNonExistentObjectId(self):
        objectId = base.randomObjectIdStr()
        return self.deleteTagValue(defaults.sep.join(paths.aboutPath()),
                                   objectId)

    @base.showFailures
    def testRidiculousObjectId(self):
        objectId = 'hey!'
        d = self.deleteTagValue(defaults.sep.join(paths.aboutPath()), objectId)
        d.addErrback(self.checkErrorStatus, http.NOT_FOUND)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'): error.NoSuchResource.__name__})
        self.failUnlessFailure(d, Error)
        return d
