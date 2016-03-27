from cStringIO import StringIO
import json
from zope.interface import implements

from twisted.trial import unittest
from twisted.internet import interfaces
from twisted.internet.address import IPv4Address
from twisted.web import http

from fluiddb.testing.doubles import FakeSession
from fluiddb.web.namespaces import NamespacesResource
from fluiddb.common.types_thrift.ttypes import TPathPermissionDenied


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
        return 'foo'


class TestCORSHeaders(unittest.TestCase):
    """
    Tests to check that the appropriate headers for CORS requests using
    methods other than OPTIONS return the correct result and that regular
    calls to FluidDB are not affected by CORS headers.
    """

    def testRegularCORSHeaders(self):
        """
        Validates that the headers are handled correctly for a CORS request
        that doesn't use the OPTIONS verb
        """
        # The origin to use in the tests
        dummyOrigin = 'http://foo.com'
        expectedHeaders = [
            'X-FluidDB-Error-Class', 'X-FluidDB-Path',
            'X-FluidDB-Message', 'X-FluidDB-ObjectId', 'X-FluidDB-Name',
            'X-FluidDB-Category', 'X-FluidDB-Action', 'X-FluidDB-Rangetype',
            'X-FluidDB-Fieldname', 'X-FluidDB-Argument',
            'X-FluidDB-Access-Token', 'X-FluidDB-Username',
            'X-FluidDB-New-User'
        ]
        payload = {'description': 'A namespace for tags that I add to people',
                   'name': 'people'}
        content = json.dumps(payload)
        contentLength = len(content)
        request = http.Request(DummyChannel(), False)
        request.method = 'POST'
        request.requestHeaders.setRawHeaders('Content-Length',
                                             [str(contentLength)])
        request.requestHeaders.setRawHeaders('Content-Type',
                                             ['application/json'])
        request.requestHeaders.setRawHeaders('Host',
                                             ['fluiddb.fluidinfo.com'])
        request.requestHeaders.setRawHeaders('Origin', [dummyOrigin])
        request._fluidDB_reqid = 'xxx'
        request.args = dict()
        request.postpath = []
        request.content = StringIO(content)
        resource = NamespacesResource(FakeFacadeClient(), FakeSession())
        resource.render(request)
        # 201 Created
        self.assertEqual(request.code, http.CREATED)
        # check we have the required headers
        headers = request.responseHeaders
        self.assertTrue(headers.hasHeader('Access-Control-Allow-Origin'))
        self.assertTrue(
            headers.hasHeader('Access-Control-Allow-Credentials'))
        self.assertTrue(
            headers.hasHeader('Access-Control-Expose-Headers'))
        # check the values of the required headers
        self.assertEqual(
            dummyOrigin,
            headers.getRawHeaders('Access-Control-Allow-Origin')[0])
        self.assertEqual(
            'true',
            headers.getRawHeaders('Access-Control-Allow-Credentials')[0])
        accessControlExposeHeaders = headers.getRawHeaders(
            'Access-Control-Expose-Headers')[0]
        # Make sure we haven't accidentally turned the header value into a
        # Python tuple by including a comma in its definition.
        self.assertTrue(isinstance(accessControlExposeHeaders, str))
        # Make sure we haven't accidentally left a comma space in the last
        # element of the Python header definition.
        self.assertFalse(accessControlExposeHeaders.endswith(', '))
        actualHeaders = accessControlExposeHeaders.split(', ')
        for header in expectedHeaders:
            self.assertTrue(header.startswith('X-FluidDB-'))
            self.assertTrue(header in actualHeaders)

    def testCorsHeadersDoNotAppearForRegularRequests(self):
        """
        Make sure CORS related headers do NOT appear in regular non-CORS
        requests
        """
        payload = {'description': 'A namespace for tags I add to people',
                   'name': 'people'}
        content = json.dumps(payload)
        contentLength = len(content)
        request = http.Request(DummyChannel(), False)
        request.method = 'POST'
        request.requestHeaders.setRawHeaders('Content-Length',
                                             [str(contentLength)])
        request.requestHeaders.setRawHeaders('Content-Type',
                                             ['application/json'])
        request.requestHeaders.setRawHeaders('Host',
                                             ['fluiddb.fluidinfo.com'])
        request._fluidDB_reqid = 'xxx'
        request.args = dict()
        request.postpath = []
        request.content = StringIO(content)
        resource = NamespacesResource(FakeFacadeClient(), FakeSession())
        resource.render(request)
        # 201 Created
        self.assertEqual(request.code, http.CREATED)
        # check we don't have the CORS related headers
        headers = request.responseHeaders
        self.assertFalse(headers.hasHeader('Access-Control-Allow-Origin'))
        self.assertFalse(
            headers.hasHeader('Access-Control-Allow-Credentials'))
        self.assertFalse(
            headers.hasHeader('Access-Control-Expose-Headers'))


class TestWWWAuthenticateHeader(unittest.TestCase):
    """
    Test that we send a WWW-Authenticate header with 401 requests.
    """

    def testHeaderNotPresentWhenNoError(self):
        """
        Check the WWW-Authenticate header is not present
        when we do not hit an error.
        """
        payload = {'description': 'A new namespace', 'name': 'people'}
        content = json.dumps(payload)
        contentLength = len(content)
        request = http.Request(DummyChannel(), False)
        request.method = 'POST'
        request.requestHeaders.setRawHeaders('Content-Length',
                                             [str(contentLength)])
        request.requestHeaders.setRawHeaders('Content-Type',
                                             ['application/json'])
        request.requestHeaders.setRawHeaders('Host',
                                             ['fluiddb.fluidinfo.com'])
        request._fluidDB_reqid = 'xxx'
        request.args = dict()
        request.postpath = []
        request.content = StringIO(content)
        resource = NamespacesResource(FakeFacadeClient(), FakeSession())
        resource.render(request)
        # Check the WWW-Authenticate header is absent.
        headers = request.responseHeaders
        self.assertFalse(headers.hasHeader('WWW-Authenticate'))

    def testHeaderPresentOn401Error(self):
        """
        Check the WWW-Authenticate header is present, with the expected
        value when we hit a 401 (Unauthorized) error.
        """

        class ExplodingPermissionDeniedFacade(object):
            """
            A fake facade whose C{createNamespace} method always
            raises TPathPermissionDenied.
            """

            def createNamespace(self, *args, **kwargs):
                """
                Make something (unspecified) appear to go wrong with perms
                checking.

                @param args: Positional arguments for the new namespace.
                @param kwargs: Keyword arguments for the new namespace.
                @raise C{TPathPermissionDenied} no matter what.
                """
                raise TPathPermissionDenied()

        payload = {'description': 'A new namespace', 'name': 'people'}
        content = json.dumps(payload)
        contentLength = len(content)
        request = http.Request(DummyChannel(), False)
        request.method = 'POST'
        request.requestHeaders.setRawHeaders('Content-Length',
                                             [str(contentLength)])
        request.requestHeaders.setRawHeaders('Content-Type',
                                             ['application/json'])
        request.requestHeaders.setRawHeaders('Host', ['fluiddb.fluidinfo.com'])
        request._fluidDB_reqid = 'xxx'
        request.args = dict()
        request.postpath = []
        request.content = StringIO(content)
        resource = NamespacesResource(ExplodingPermissionDeniedFacade(),
                                      FakeSession())
        resource.render(request)
        # Check the response code and header content.
        self.assertEqual(request.code, http.UNAUTHORIZED)
        headers = request.responseHeaders
        self.assertTrue(headers.hasHeader('WWW-Authenticate'))
        self.assertEqual('Basic realm="Fluidinfo"',
                         headers.getRawHeaders('WWW-Authenticate')[0])
