from hashlib import md5
import base64
from cStringIO import StringIO
import json
from zope.interface import implements

from twisted.trial import unittest
from twisted.internet import defer
from twisted.internet import interfaces
from twisted.internet.address import IPv4Address
from twisted.web import http
from twisted.web.http_headers import Headers

from fluiddb.common import error
from fluiddb.testing.doubles import FakeSession
from fluiddb.web.namespaces import NamespacesResource


class NoContent(object):
    """
    A class whose instances can be set as a content tag on a
    C{FakeRequest} to throw a C{ValueError} when an attempt to seek on it
    is made.
    """

    def seek(self, offset, whence):
        """
        Seek in our (fictional) content.  See sys.stdin.seek.__doc__ for
        more info.

        @param offset: bytes position.
        @param whence: from where should the seek originate.
        """
        raise ValueError()


class FakeRequest(object):
    """
    A fake request suitable for use in place of C{twisted.web.http.Request}.

    @param method: The HTTP method being invoked such as C{GET} or C{POST}.
    @param uri: The URI of the resource being requested.
    @param headers: A C{dict} of headers to send in the request.
    @param args: A C{dict} of arguments that should be appended to the URI in
        the request.
    """

    content = None

    def __init__(self, method, uri, headers=None, args=None):
        self.method = method
        self.uri = uri
        self.requestHeaders = Headers(headers)
        self.responseHeaders = Headers()
        self.args = {'verb': [method]}
        if args:
            self.args.update(args)
        self._fluidDB_reqid = 'xxx'
        self.finished = False

    def finish(self):
        """
        Indicate that all response data has been written to this request.
        """
        self.finished = True

    def getHeader(self, key):
        """
        Get the value of an HTTP request header.

        @param key: The name of the HTTP header to retrieve a value for.
        @return: The value set for the header or C{None} if a value is not
            available.
        """
        value = self.requestHeaders.getRawHeaders(key)
        if value is not None:
            return value[-1]

    def getResponseHeader(self, key):
        """
        Get the value of an HTTP response header.

        @param key: The name of the HTTP header to retrieve a value for.
        @return: The value set for the header or C{None} if a value is not
            available.
        """
        value = self.responseHeaders.getRawHeaders(key)
        if value is not None:
            return value[-1]

    def setHeader(self, name, value):
        """
        Set an HTTP header to include in the response returned to the client.

        @param name: The name of the header to set.
        @param value: The value to set.
        """
        self.responseHeaders.setRawHeaders(name, [value])

    def getAllHeaders(self):
        """
        Return all the request headers.

        @return: A C{dict} of all headers, with their values.
        """
        headers = {}
        for k, v in self.requestHeaders.getAllRawHeaders():
            headers[k.lower()] = v[-1]
        return headers

    def setResponseCode(self, code):
        """
        Set the HTTP response code to return to the client.

        @param code: An HTTP response code as defined in C{twisted.web.http}.
        """
        self.status = code

    def notifyFinish(self):
        """
        Return a C{twisted.internet.Deferred} that fires when the request
        finishes or errors if the client disconnects. Note that this method
        is needed as resource.py calls it, but we do not need to actually
        fire the returned deferred for our test (which causes a synchronous
        exception to immediately be returned to the request errback).

        @return: C{twisted.internet.Deferred}
        """
        return defer.succeed(None)


class DummyChannel(object):

    class TCP(object):
        port = 80
        disconnected = False

        def __init__(self):
            self.written = StringIO()
            self.producers = []

        def getPeer(self):
            return IPv4Address('TCP', '192.168.1.1', 12344)

        def write(self, bytes):
            assert isinstance(bytes, str)
            self.written.write(bytes)

        def writeSequence(self, iovec):
            map(self.write, iovec)

        def getHost(self):
            return IPv4Address('TCP', '10.0.0.1', self.port)

        def registerProducer(self, producer, streaming):
            self.producers.append((producer, streaming))

        def loseConnection(self):
            self.disconnected = True

    class SSL(TCP):
        implements(interfaces.ISSLTransport)

    def __init__(self):
        self.transport = self.TCP()

    def requestDone(self, request):
        pass


class FakeFacadeClient(object):

    def createNamespace(self, *args, **kwargs):
        return "foo"


class TestPayloads(unittest.TestCase):
    """
    Tests to check request payloads.
    """

    def testUnseekableContent(self):
        """
        Test that sending a request whose content cannot have seek called
        on it without raising a ValueError gets a 400 Bad Request status,
        with the appropriate C{X-FluidDB-Error-Class} value in the header.
        """
        request = FakeRequest('POST', 'namespaces/fluiddb')
        request.content = NoContent()
        resource = NamespacesResource(None, FakeSession())
        resource.render(request)
        self.assertFalse(request.finished)
        self.assertEqual(request.status, http.BAD_REQUEST)
        self.assertEqual(request.getResponseHeader('X-FluidDB-Error-Class'),
                         error.ContentSeekError.__name__)

    def testContentMD5OK(self):
        """
        Checks that an incoming requests whose payload matches the
        Content-MD5 header.
        """

        payload = {"description": "A namespace for tags that I'm using to"
                                  " add to people",
                   "name": "people"}
        content = json.dumps(payload)
        contentLength = len(content)
        md5Content = base64.standard_b64encode(md5(content).digest())
        request = http.Request(DummyChannel(), False)
        request.method = 'POST'
        request.requestHeaders.setRawHeaders("Content-MD5", [md5Content])
        request.requestHeaders.setRawHeaders("Content-Length",
                                             [str(contentLength)])
        request.requestHeaders.setRawHeaders("Content-Type",
                                             ["application/json"])
        request.requestHeaders.setRawHeaders("Host",
                                             ["fluiddb.fluidinfo.com"])
        request._fluidDB_reqid = 'xxx'
        request.args = dict()
        request.postpath = []
        request.content = StringIO(content)

        resource = NamespacesResource(FakeFacadeClient(), FakeSession())
        resource.render(request)
        self.assertEqual(request.code, http.CREATED)

    def testContentMD5DoesNotMatch(self):
        """
        Checks that an incoming requests whose payload doesn't match the
        Content-MD5 header and returns a PRECONDITION FAILED (412).
        """

        payload = {"description": "A namespace for tags that I'm using to"
                                  "add to people",
                   "name": "people"}
        content = json.dumps(payload)
        contentLength = len(content)
        request = http.Request(DummyChannel(), False)
        request.method = 'POST'
        request.requestHeaders.setRawHeaders("Content-MD5", ["bad-md5"])
        request.requestHeaders.setRawHeaders("Content-Length",
                                             [str(contentLength)])
        request.requestHeaders.setRawHeaders("Content-Type",
                                             ["application/json"])
        request._fluidDB_reqid = 'xxx'
        request.args = dict()
        request.postpath = []
        request.content = StringIO(content)

        resource = NamespacesResource(FakeFacadeClient(), FakeSession())
        resource.render(request)
        self.assertEqual(request.code, http.PRECONDITION_FAILED)
