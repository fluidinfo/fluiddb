# -*- coding: utf-8 -*-

import json
import random
import urllib

from base64 import b64encode

from twisted.python import log
from twisted.web import http
from twisted.web.error import Error
from twisted.internet import defer, reactor
from twisted.internet.protocol import Protocol
from twisted.web.client import Agent, ResponseDone
from twisted.web.http_headers import Headers

from fluiddb.common import defaults, error, permissions
from fluiddb.common import paths
from fluiddb.common.types_thrift.ttypes import (
    TNonexistentTag, TNoInstanceOnObject)
from fluiddb.web.util import buildHeader

from integration.wsfe import base
from integration.wsfe.http import getPage, HTTPError
import txbase


class SimpleBodyProducer(object):

    def __init__(self, data):
        self.data = data
        self.length = len(data)
        self.d = None

    def startProducing(self, consumer):
        consumer.write(self.data)
        return defer.succeed(None)


class ResponseGetter(Protocol):
    _buffer = ''

    def __init__(self, finished):
        self._finished = finished

    def dataReceived(self, bytes):
        self._buffer += bytes

    def connectionLost(self, reason):
        reason.trap(ResponseDone)
        self._finished.callback(self._buffer)


class TagInstanceTest(txbase.TxFluidDBTest, base.HTTPTest):
    """
    A base class for our FluidDB tag instance tests.

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


class TestPOST(TagInstanceTest):

    verb = 'POST'

    @base.showFailures
    def testNotAllowed(self):
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage(base.randomObjectIdStr(), headers=headers)
        d.addErrback(self.checkErrorStatus, http.NOT_ALLOWED)
        self.failUnlessFailure(d, Error)
        return d


class TestGET(TagInstanceTest):

    verb = 'GET'

    @base.showFailures
    def testNonExistentObjectId(self):
        aboutPath = defaults.sep.join(paths.aboutPath())
        objectId = base.randomObjectIdStr()
        d = self.getTagValue(aboutPath, objectId)
        d.addErrback(self.checkErrorStatus, http.NOT_FOUND)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'): TNoInstanceOnObject.__name__})
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testNonType4ObjectId(self):
        aboutPath = defaults.sep.join(paths.aboutPath())
        d = self.getTagValue(aboutPath, base.nonType4ObjectIdStr())
        d.addErrback(self.checkErrorStatus, http.NOT_FOUND)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'): TNoInstanceOnObject.__name__})
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    @defer.inlineCallbacks
    def testPrimitiveTypes(self):
        path = 'fluiddb/testing/test1'
        objectId = yield self.createObject()
        try:
            for value in (True, False, 3, 4.5, ['4', '5', '6'], None):
                yield self.setTagValue(path, objectId, value)
                for acc in (None, defaults.contentTypeForPrimitiveJSON):
                    result = yield self.getTagValue(path, objectId, accept=acc)
                    if type(value) is list:
                        value = sorted(value)
                        result = sorted(result)
                    self.assertEqual(value, result)
        finally:
            yield self.deleteTagValue(path, objectId)

    @base.showFailures
    @defer.inlineCallbacks
    def testNotAcceptableMIMEvMIME(self):
        path = 'fluiddb/testing/test1'
        objectId = yield self.createObject()
        primitiveOrAnything = '%s, */*' % defaults.contentTypeForPrimitiveJSON

        # data is given as a tuple of tuples. Each sub-tuple has 3 things:
        # a value, the accept string with which to try GETting the value,
        # and a flag to indicate whether the GET is expected to succeed.
        # The value may be a (x, ct) pair, where x is the actual value to
        # be PUT and ct is the content-type to PUT it with.

        testdata = [
            (('xxx', 'application/pdf'), 'no/pdf', False),
            (('xxx', 'application/pdf'), 'application/pdf', True),
            (('xxx', 'application/pdf'), 'application/pdf, */*', True),
            (('xxx', 'yyy/zzz'), defaults.contentTypeForPrimitiveJSON, False),
        ]

        for value in (True, False, 4, 7.3, None, 'ducks', ['Hey', 'Jude']):
            for ct in ('application/pdf', 'text/plain', 'xx/yy, ii/jj; q=0.5'):
                testdata.append((value, ct, False))
            for ct in ('*/*', defaults.contentTypeForPrimitiveJSON,
                       primitiveOrAnything):
                testdata.append((value, ct, True))

        try:
            for value, accept, succeed in testdata:
                if type(value) is tuple:
                    value, ct = value
                    yield self.setTagValue(
                        path, objectId, value, contentType=ct)
                    d = self.getTagValueAndContentType(
                        path, objectId, accept=accept)
                    if succeed:
                        result, resultCt = yield d
                        self.assertEqual(value, result)
                        self.assertEqual(ct, resultCt)
                else:
                    yield self.setTagValue(path, objectId, value)
                    d = self.getTagValue(path, objectId, accept=accept)
                    if succeed:
                        result = yield d
                        self.assertEqual(value, result)

                if not succeed:
                    d.addErrback(self.checkErrorStatus, http.NOT_ACCEPTABLE)
                    d.addErrback(
                        self.checkErrorHeaders,
                        {buildHeader('Error-Class'):
                         error.NotAcceptable.__name__})
                    self.failUnlessFailure(d, Error)
                    yield d
        finally:
            yield self.deleteTagValue(path, objectId)


class TestHEAD(TagInstanceTest):

    verb = 'HEAD'

    @base.showFailures
    @defer.inlineCallbacks
    def testAdminNewTagOnNewObject(self):
        path = 'fluiddb/testing/test1'
        objectId = yield self.createObject()
        exists = yield self.hasTagValue(path, objectId)
        self.assertFalse(exists)
        try:
            yield self.setTagValue(path, objectId, '5')
            exists = yield self.hasTagValue(path, objectId)
            self.assertTrue(exists)
        finally:
            yield self.deleteTagValue(path, objectId)

    @base.showFailures
    @defer.inlineCallbacks
    def testRidiculousObjectId(self):
        aboutPath = defaults.sep.join(paths.aboutPath())
        exists = yield self.hasTagValue(aboutPath, 'dummy')
        self.assertFalse(exists)

    @base.showFailures
    @defer.inlineCallbacks
    def testNonExistentObjectId(self):
        aboutPath = defaults.sep.join(paths.aboutPath())
        objectId = base.randomObjectIdStr()
        exists = yield self.hasTagValue(aboutPath, objectId)
        self.assertFalse(exists)

    @base.showFailures
    @defer.inlineCallbacks
    def testNonType4ObjectId(self):
        aboutPath = defaults.sep.join(paths.aboutPath())
        exists = yield self.hasTagValue(aboutPath, base.nonType4ObjectIdStr())
        self.assertFalse(exists)

    @base.showFailures
    @defer.inlineCallbacks
    def testHEADSetsContentLengthAndType(self):
        """
        A HEAD request is supposed to return a Content-Length header
        indicating the size of the resource that a GET would return.  Here
        we do a simple check to see that the header is present and correct.

        This is a bit of a Frankenstein test. It uses the current testing
        framework to create a tag, an object, set the tag value, and remove
        the tag, but uses the new twisted.web.client Agent to make the HEAD
        request. The code would be ~4 times as long if I wrote it all to
        use the Agent for every API call.
        """
        value = 'i am the value'
        path = 'fluiddb/testing/test1'
        objectId = yield self.createObject()
        try:
            for value, contentType in (
                    (True, defaults.contentTypeForPrimitiveJSON),
                    (False, defaults.contentTypeForPrimitiveJSON),
                    (None, defaults.contentTypeForPrimitiveJSON),
                    (5, defaults.contentTypeForPrimitiveJSON),
                    (3.14, defaults.contentTypeForPrimitiveJSON),
                    ('hey', defaults.contentTypeForPrimitiveJSON),
                    (u'\u2345\uFDFA\u2619',
                     defaults.contentTypeForPrimitiveJSON),
                    ('opaque value', 'opaque/stuff')):

                yield self.setTagValue(path, objectId, value,
                                       contentType=contentType)
                URI = '%s/%s/%s/%s' % (self.endpoint,
                                       defaults.httpObjectCategoryName,
                                       str(objectId), path)
                headers = Headers({
                    'Authorization': ['Basic %s' % b64encode(
                        '%s:%s' % (defaults.adminUsername.encode('utf-8'),
                                   self.adminPassword))]})
                agent = Agent(reactor)
                response = yield agent.request('HEAD', URI, headers)
                self.assertEqual(http.OK, response.code)

                # Test the content length is as expected.
                receivedContentLen = int(response.headers.getRawHeaders(
                    'content-length')[0])
                if contentType == defaults.contentTypeForPrimitiveJSON:
                    # The content-length should be the length of the JSON
                    # encoded value (since the value was a primitive type).
                    expectedContentLen = len(json.dumps(value))
                else:
                    expectedContentLen = len(value)
                self.assertEqual(receivedContentLen, expectedContentLen)

                # Test the content type is as expected.
                receivedContentType = response.headers.getRawHeaders(
                    'content-type')[0]
                self.assertEqual(receivedContentType, contentType)
        finally:
            yield self.deleteTagValue(path, objectId)


class TestPUT(TagInstanceTest):

    verb = 'PUT'

    @base.showFailures
    @defer.inlineCallbacks
    def testPlausibleButNonExistentObjectId(self):
        # Here we use an object ID that is syntactically a UUID, though
        # it's guaranteed not to exist in FluidDB (see base.py).
        #
        # For now this succeeds as we do not require that an object exist
        # before you put a value onto it.
        path = 'fluiddb/testing/test1'
        value = 'floppy disks, FTW!'
        objectId = base.randomObjectIdStr()
        try:
            yield self.setTagValue(path, objectId, value)
            result = yield self.getTagValue(path, objectId)
            self.assertEqual(result, value)
        finally:
            yield self.deleteTagValue(path, objectId)

    @base.showFailures
    @defer.inlineCallbacks
    def testNonType4NonExistentObjectId(self):
        # Here we use an object ID that is syntactically a UUID, though
        # it's guaranteed not to exist in FluidDB.
        #
        # For now this succeeds as we do not require that an object exist
        # before you put a value onto it, and we do not check that object
        # ids obey type 4 rules. Should we? Or do we just not care?
        path = 'fluiddb/testing/test1'
        value = 5
        objectId = base.nonType4ObjectIdStr()
        try:
            yield self.setTagValue(path, objectId, value)
            result = yield self.getTagValue(path, objectId,)
            self.assertEqual(result, value)
        finally:
            result = yield self.deleteTagValue(path, objectId,)

    @base.showFailures
    @defer.inlineCallbacks
    def testPayloadWithNoContentType(self):
        headers = {}
        self.addBasicAuthHeader(headers)
        objectId = yield self.createObject()
        uri = '%s/%s/%s/dummy' % (
            self.endpoint,
            defaults.httpObjectCategoryName, str(objectId))
        d = getPage(uri, headers=headers, postdata=json.dumps('x'),
                    method='PUT')
        d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'): error.NoContentTypeHeader.__name__})
        self.failUnlessFailure(d, Error)
        yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testNonExistentTag(self):
        objectId = yield self.createObject()
        d = self.setTagValue('xx/yy/zz', objectId, '5')
        d.addErrback(self.checkErrorStatus, http.NOT_FOUND)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'): TNonexistentTag.__name__})
        self.failUnlessFailure(d, Error)
        yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testAdminAddTagTwiceOnNewObject(self):
        path = 'fluiddb/testing/test1'
        objectId = yield self.createObject()
        try:
            yield self.setTagValue(path, objectId, '5')
            yield self.setTagValue(path, objectId, '6')
        finally:
            yield self.deleteTagValue(path, objectId)

    @base.showFailures
    @defer.inlineCallbacks
    def testRoundtripPrimitiveTypes(self):
        path = 'fluiddb/testing/test1'
        objectId = yield self.createObject()
        try:
            for value in (True, False, None, 5, 3.14,
                          'hey', u'\u2345\uFDFA\u2619'):
                yield self.setTagValue(path, objectId, value)
                result = yield self.getTagValue(path, objectId)
                self.assertEqual(value, result)

            value = ['foobar', u'\u2345\uFDFA\u2619', 'D\xc3\xb8dheimsgard']
            yield self.setTagValue(path, objectId, value)
            result = yield self.getTagValue(path, objectId)
            # We need to sanitize the original value variable, a call to
            # sorted will trigger a call to equal between normal strings
            # and unicode
            sanitizedValue = []
            for s in value:
                if not isinstance(s, unicode):
                    s = s.decode("utf-8")
                sanitizedValue.append(s)
            sanitizedValue = sorted(sanitizedValue)
            result = sorted(result)
            self.assertEqual(sanitizedValue, result)
        finally:
            yield self.deleteTagValue(path, objectId)

    @base.showFailures
    @defer.inlineCallbacks
    def testAdminNewBinaryTagOnNewObject(self):

        def randBinary(n):
            # Make a random binary string of length n.
            values = '\x00\x01\x02\x03\x04'.split()
            return ''.join([random.choice(values) for _ in xrange(n)])
        path = 'fluiddb/testing/test1'
        objectId = yield self.createObject()
        try:
            for contentType in ('application/octet-stream', 'hello/world'):
                size = random.randint(1, 1000)
                value = randBinary(size)
                yield self.setTagValue(path, objectId, value,
                                       contentType=contentType)
                result = yield self.getTagValueAndContentType(path, objectId)
                self.assertEqual(result[0], value)
                self.assertEqual(result[1], contentType)
        finally:
            yield self.deleteTagValue(path, objectId)

    @base.showFailures
    @defer.inlineCallbacks
    def testAdminNewBinaryTagOnNewObjectJSONP(self):

        def randBinary(n):
            # Make a random binary string of length n.
            values = '\x00\x01\x02\x03\x04'.split()
            return ''.join([random.choice(values) for _ in xrange(n)])
        path = 'fluiddb/testing/test1'
        objectId = yield self.createObject()
        headers = {}
        self.addBasicAuthHeader(headers)
        try:
            for contentType in ('application/octet-stream', 'hello/world'):
                size = random.randint(1, 1000)
                value = randBinary(size)
                yield self.setTagValue(path, objectId, value,
                                       contentType=contentType)

                uri = '%s/%s' % (self.endpoint,
                                 defaults.httpObjectCategoryName)

                # Request a tag value without a callback arg
                uriValue = defaults.sep.join([uri, str(objectId), path])
                status, responseHeaders, responseValueNoCB = yield getPage(
                    uriValue, headers=headers)

                self.assertEqual(responseValueNoCB, value)
                self.assertEqual(responseHeaders['content-type'][0],
                                 contentType)

                # Request the same tag value with a callback arg
                callbackValue = 'bar'

                uriValueCB = uriValue + '?' + urllib.urlencode(
                    {'callback': callbackValue})

                try:
                    status, responseHeaders, responseValueCB = yield getPage(
                        uriValueCB, headers=headers)
                    self.fail("This should have failed, binary values can't "
                              "be retrieved using a callback")
                except HTTPError, e:
                    h = e.response_headers
                    self.assertEqual(h['x-fluiddb-error-class'][0],
                                     'UnwrappableBlob')
        finally:
            yield self.deleteTagValue(path, objectId)

    @base.showFailures
    @defer.inlineCallbacks
    def testAdminNewTagOnObjectWithAboutThenGET(self):
        path = 'fluiddb/testing/test1'
        aboutPath = defaults.sep.join(paths.aboutPath())
        # An object with an about.
        objectId = yield self.createObject('hello')
        value = '5'
        try:
            yield self.setTagValue(path, objectId, value)
            # Check the value is there.
            result = yield self.getTagValue(path, objectId)
            self.assertEqual(value, result)

            # Make sure the path is now in the tagPaths.
            objectInfo = yield self.getObject(str(objectId))
            aboutPath = defaults.sep.join(paths.aboutPath())
            self.assertIn(path, objectInfo['tagPaths'])
            self.assertIn(aboutPath, objectInfo['tagPaths'])
        finally:
            result = yield self.deleteTagValue(path, objectId)

    @base.showFailures
    @defer.inlineCallbacks
    def testAdminNewTagOnObjectWithoutAboutThenGET(self):
        path = 'fluiddb/testing/test1'
        # An object without an about.
        objectId = yield self.createObject()
        # Check we see no tags on the new object.
        objectInfo = yield self.getObject(str(objectId))
        self.assertEqual(objectInfo['tagPaths'], [])
        value = '5'
        try:
            yield self.setTagValue(path, objectId, value)
            # Check the value is there.
            result = yield self.getTagValue(path, objectId)
            self.assertEqual(value, result)

            # Make sure the path is now in the tagPaths.
            objectInfo = yield self.getObject(str(objectId))
            self.assertEqual(objectInfo['tagPaths'], [path])
        finally:
            yield self.deleteTagValue(path, objectId)

    @base.showFailures
    @defer.inlineCallbacks
    def testOpaqueMIMETypes(self):
        value = 'hey'
        contentTypes = ('text/plain; charset=utf-8',
                        'application/pdf',
                        'green/tea; leaves=no',
                        'text/plain; charset=utf-8 ',
                        ' TEXT/PLAIN; CHARSET=UTF-8 ',
                        'text/plain ; charset = utf-8 ')
        path = 'fluiddb/testing/test1'
        objectId = yield self.createObject()
        try:
            for contentType in contentTypes:
                yield self.setTagValue(path, objectId, value,
                                       contentType=contentType)
                result = yield self.getTagValueAndContentType(path, objectId)
                self.assertEqual(result[0], value)
                self.assertEqual(result[1], contentType.strip())
        finally:
            yield self.deleteTagValue(path, objectId)

    @base.showFailures
    @defer.inlineCallbacks
    def testMultipleSimultaneousCreates(self):
        path = 'fluiddb/testing/test1'
        objectId = yield self.createObject()
        deferreds = []
        try:
            for value in (3, None, True, 5.4, False, 'hey', ['a', 'b']):
                deferreds.append(self.setTagValue(path, objectId, value))
            results = yield defer.DeferredList(deferreds, consumeErrors=True)
            failed = False
            for result in results:
                if not result[0]:
                    failed = True
                    log.err(result[1])
            if failed:
                self.fail()
        finally:
            yield self.deleteTagValue(path, objectId)

    @base.showFailures
    @defer.inlineCallbacks
    def testMultipleSimultaneousUpdates(self):
        path = 'fluiddb/testing/test1'
        objectId = yield self.createObject()
        yield self.setTagValue(path, objectId, 5)
        deferreds = []
        try:
            for _ in range(10):
                for value in (7, True, None, 4.8, False, 'hi', ['aa', 'bb']):
                    deferreds.append(self.setTagValue(path, objectId, value))
            results = yield defer.DeferredList(deferreds, consumeErrors=True)
            failed = False
            for result in results:
                if not result[0]:
                    failed = True
                    log.err(result[1])
            if failed:
                self.fail()
        finally:
            yield self.deleteTagValue(path, objectId)

    @base.showFailures
    @defer.inlineCallbacks
    def testListContainingNonString(self):
        path = 'fluiddb/testing/test1'
        objectId = yield self.createObject()
        try:
            d = self.setTagValue(path, objectId, ['hi', 6])
            d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
            d.addErrback(
                self.checkErrorHeaders,
                {buildHeader('Error-Class'):
                 error.UnsupportedJSONType.__name__})
            self.failUnlessFailure(d, Error)
            yield d
        finally:
            yield self.deleteTagValue(path, objectId)

    @base.showFailures
    @defer.inlineCallbacks
    def testSetTagTwiceWithSameTypeButDifferentUsers(self):
        path = 'fluiddb/testing/test1'
        objectId = yield self.createObject()
        # Change permissions to let testuser1 create instances of
        # 'fluiddb/testing/test1' too.
        yield self.updatePermissions(
            defaults.sep.join(
                [defaults.httpTagInstanceSetCategoryName, path]),
            permissions.WRITE, 'closed', ['testuser1'])
        try:
            yield self.setTagValue(path, objectId, 5)
            yield self.setTagValue(path, objectId, 5,
                                   requesterUsername='testuser1',
                                   requesterPassword='secret')
        finally:
            yield self.deleteTagValue(path, objectId)
            # Change permissions to prevent testuser1 creating instances of
            # the tag.
            yield self.updatePermissions(
                defaults.sep.join(
                    [defaults.httpTagInstanceSetCategoryName, path]),
                permissions.WRITE, 'closed', [])

    @base.showFailures
    @defer.inlineCallbacks
    def testPrimitiveTypesWithCharsetAlsoInContentType(self):
        """
        This test is designed for https://oodl.es/trac/fluiddb/ticket/572
        In the scenario described there, if Javascript running in a browser
        tries to PUT a primitive value type, using the content type
        'application/vnd.fluiddb.value+json', the browser in fact sends
        'application/vnd.fluiddb.value+json; charset=utf-8'. In this case
        FluidDB should simply ignore the tags that follow the
        semicolon and treat the body as JSON (which doesn't need an
        encoding, as it's all ASCII by definition).

        So in the test below, we PUT a variety of primitive value types
        (everything except a set of strings) and send a Content-type header
        with some trailing junk. Then we do a GET and make sure that we get
        back just the 'application/vnd.fluiddb.value+json' content type as
        well as the JSON encoded value.  (The buggy version of FluidDB
        would instead return the originally submitted content-type.)
        """
        path = 'fluiddb/testing/test1'
        objectId = yield self.createObject()
        URI = '%s/%s/%s/%s' % (self.endpoint,
                               defaults.httpObjectCategoryName,
                               str(objectId),
                               urllib.quote(path.encode('utf-8')))
        try:
            for value in (True, False, None, 5, 3.14,
                          'hey', u'\u2345\uFDFA\u2619'):
                for contentTypeSuffix in ('charset=utf-8', 'rubbish'):

                    # PUT the value with the primitive Content-type
                    # followed by additional irrelevant stuff.
                    headers = Headers({
                        'Content-type': [
                            defaults.contentTypeForPrimitiveJSON +
                            ';' + contentTypeSuffix],
                        'Authorization': ['Basic %s' % b64encode(
                            '%s:%s' % (defaults.adminUsername.encode('utf-8'),
                                       self.adminPassword))]})
                    bodyProducer = SimpleBodyProducer(json.dumps(value))
                    agent = Agent(reactor)
                    response = yield agent.request('PUT', URI,
                                                   headers, bodyProducer)
                    self.assertEqual(http.NO_CONTENT, response.code)

                    # GET the value back and check it and its Content-type
                    # header.
                    headers = Headers({
                        'Authorization': ['Basic %s' % b64encode(
                            '%s:%s' % (defaults.adminUsername.encode('utf-8'),
                                       self.adminPassword))]})
                    agent = Agent(reactor)
                    response = yield agent.request('GET', URI, headers)
                    self.assertEqual(http.OK, response.code)
                    # Check received Content-type.
                    receivedContentType = response.headers.getRawHeaders(
                        'content-type')[0]
                    self.assertEqual(receivedContentType,
                                     defaults.contentTypeForPrimitiveJSON)
                    # Check the body has the JSON-encoded primitive value.
                    d = defer.Deferred()
                    bodyGetter = ResponseGetter(d)
                    response.deliverBody(bodyGetter)
                    body = yield d
                    valueReceived = json.loads(body)
                    self.assertEqual(valueReceived, value)
        finally:
            yield self.deleteTagValue(path, objectId)

    @base.showFailures
    @defer.inlineCallbacks
    def testPrimitiveTypesWithContentTypeSuffixed(self):
        """
        This test is also designed for
        https://oodl.es/trac/fluiddb/ticket/572. See the comment in the
        previous text for context.

        In the test below, we try to PUT a primitive value type but send a
        Content-type header with some trailing junk but no semicolon. Then
        we do a GET and make sure that we get back the exact content type
        we sent. In other words, FluidDB will have treated the value as
        being opaque, as it should.  This is designed to make sure that a
        value PUT request sending a content-type that has our
        contentTypeForPrimitiveJSON as a prefix gets treated as opaque.
        """
        path = 'fluiddb/testing/test1'
        objectId = yield self.createObject()
        URI = '%s/%s/%s/%s' % (self.endpoint,
                               defaults.httpObjectCategoryName,
                               str(objectId),
                               urllib.quote(path.encode('utf-8')))
        value = 5
        contentType = defaults.contentTypeForPrimitiveJSON + 'blah'
        try:
            # PUT the value with our primitive content-type as a prefix in
            # the Content-type header.
            headers = Headers({
                'Content-type': [contentType],
                'Authorization': ['Basic %s' % b64encode(
                    '%s:%s' % (defaults.adminUsername.encode('utf-8'),
                               self.adminPassword))]})
            bodyProducer = SimpleBodyProducer(json.dumps(value))
            agent = Agent(reactor)
            response = yield agent.request('PUT', URI,
                                           headers, bodyProducer)
            self.assertEqual(http.NO_CONTENT, response.code)

            # GET the value back and check its Content-type header.
            headers = Headers({
                'Authorization': ['Basic %s' % b64encode(
                    '%s:%s' % (defaults.adminUsername.encode('utf-8'),
                               self.adminPassword))]})
            agent = Agent(reactor)
            response = yield agent.request('GET', URI, headers)
            self.assertEqual(http.OK, response.code)
            # Check received Content-type.
            receivedContentType = response.headers.getRawHeaders(
                'content-type')[0]
            self.assertEqual(receivedContentType, contentType)
        finally:
            yield self.deleteTagValue(path, objectId)


class TestDELETE(TagInstanceTest):

    verb = 'DELETE'

    @base.showFailures
    @defer.inlineCallbacks
    def testSimple(self):
        path = 'fluiddb/testing/test1'
        objectId = yield self.createObject()
        try:
            yield self.setTagValue(path, objectId, '10')
        finally:
            yield self.deleteTagValue(path, objectId)

    @base.showFailures
    def testNonExistentObjectId(self):
        path = 'fluiddb/testing/test1'
        objectId = base.randomObjectIdStr()
        return self.deleteTagValue(path, objectId)

    @base.showFailures
    def testNonType4ObjectId(self):
        path = 'fluiddb/testing/test1'
        return self.deleteTagValue(path, base.nonType4ObjectIdStr())
