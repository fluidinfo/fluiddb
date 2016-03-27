from cStringIO import StringIO
from zope.interface import implements

from twisted.trial import unittest
from twisted.internet import interfaces
from twisted.internet.address import IPv4Address
from twisted.web import http
from twisted.web._auth.basic import BasicCredentialFactory

from fluiddb.testing.doubles import FakeSession
from fluiddb.web.about import AboutObjectResource, AboutTagInstanceResource
from fluiddb.web.namespaces import NamespacesResource
from fluiddb.web.objects import (
    TagInstanceResource, ObjectsResource, ObjectResource)
from fluiddb.web.permissions import ConcretePermissionResource
from fluiddb.web.resource import WSFEUnauthorizedResource
from fluiddb.web.tags import TagsResource
from fluiddb.web.users import UsersResource, ConcreteUserResource
from fluiddb.web.values import ValuesResource
from fluiddb.web.values import WSFEResource


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
    """
    Copied verbatim from other modules in this directory
    """

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
    """
    Copied verbatim from other modules in this directory
    """

    def createNamespace(self, *args, **kwargs):
        return 'foo'


class TestOptions(unittest.TestCase):
    """
    Tests to check the OPTIONS http verb is correctly handled by each of the
    resources.
    """

    def _checkCORSPreFlightRequest(self, resource, requestMethod="GET"):
        """
        Makes a pre-flight request with the OPTIONS method. This is simply a
        sanity check to make sure the pre-flight works as expected and all the
        headers are returned with the correct values for the resource passed
        into this function
        """
        # The origin to use in the tests
        dummyOrigin = 'http://foo.com'
        # Some custom headers to check for
        dummyHeaders = ['x-FooBarBaz', 'Content-Type']

        # the good case
        request = http.Request(DummyChannel(), False)
        request.method = 'OPTIONS'
        request.requestHeaders.setRawHeaders('Origin', [dummyOrigin])
        request.requestHeaders.setRawHeaders(
            'Access-Control-Request-Method',
            [requestMethod])
        request.requestHeaders.setRawHeaders(
            'Access-Control-Request-Headers',
            dummyHeaders)
        request._fluidDB_reqid = 'xxx'
        request.args = dict()
        request.postpath = []
        request.content = NoContent()
        resource.render(request)
        # 200 OK
        self.assertEqual(request.code, http.OK)
        # check we have the required headers
        headers = request.responseHeaders
        self.assertTrue(headers.hasHeader('Allow'))
        self.assertTrue(headers.hasHeader('Access-Control-Allow-Origin'))
        self.assertTrue(headers.hasHeader('Access-Control-Max-Age'))
        self.assertTrue(
            headers.hasHeader('Access-Control-Allow-Credentials'))
        self.assertTrue(headers.hasHeader('Access-Control-Allow-Methods'))
        self.assertTrue(headers.hasHeader('Access-Control-Allow-Headers'))
        # check the header content
        # Content length = 0
        # Must be the same as the requestee's Origin header
        self.assertEqual(
            dummyOrigin,
            headers.getRawHeaders('Access-Control-Allow-Origin')[0])
        # Cache timeout to the default value
        self.assertEqual(
            str(resource.ACCESS_CONTROL_MAX_AGE),
            headers.getRawHeaders('Access-Control-Max-Age')[0])
        # Makes it possible to allow credentials
        self.assertEqual(
            'true',
            headers.getRawHeaders('Access-Control-Allow-Credentials')[0])
        # Check the access control allowed methods (those allowed for CORS)
        accessControlAllowedMethods = headers.getRawHeaders(
            'Access-Control-Allow-Methods')[0].split(', ')
        self.assertEqual(
            len(resource.allowedMethods),
            len(accessControlAllowedMethods))
        for item in resource.allowedMethods:
            self.assertTrue(item in accessControlAllowedMethods)
        # Check the allowed methods (including and in addition to those
        # allowed for CORS)
        allowedMethods = headers.getRawHeaders('Allow')[0].split(', ')
        self.assertEqual(
            len(resource.allowedMethods),
            len(allowedMethods))
        for item in resource.allowedMethods:
            self.assertTrue(item in allowedMethods)
        # Check the access control allowed headers
        allowedHeaders = headers.getRawHeaders(
            'Access-Control-Allow-Headers')[0].split(', ')
        # The content-type is not simple so it should be in the allowed headers
        # and only the content-type header should be returned since we don't
        # allow any other sort at the moment
        self.assertEqual(['Accept', 'Authorization', 'Content-Type',
                          'X-FluidDB-Access-Token'],
                         allowedHeaders)

    def testAllowedMethodsCheck(self):
        """
        Makes sure _handleOptions throws an exception if allowedMethods is not
        defined in the child class
        """
        request = http.Request(DummyChannel(), False)
        request.method = 'OPTIONS'
        request._fluidDB_reqid = 'xxx'
        request.args = dict()
        request.postpath = []
        request.content = NoContent()
        resource = WSFEResource(FakeFacadeClient(), FakeSession())
        self.assertRaises(RuntimeError, resource._handleOptions, request, None)

    def testInvalidCORSPreFlightRequestNoACRM(self):
        """
        The request has an Origin header but no
        Access-Control-Request-Method so check it returns a regular OPTIONS
        response.
        """
        # The origin to use in the tests
        dummyOrigin = 'http://foo.com'

        request = http.Request(DummyChannel(), False)
        request.method = 'OPTIONS'
        request.requestHeaders.setRawHeaders('Origin', [dummyOrigin])
        request._fluidDB_reqid = 'xxx'
        request.args = dict()
        request.postpath = []
        request.content = NoContent()
        resource = NamespacesResource(FakeFacadeClient(), FakeSession())
        resource._handleOptions(request, dummyOrigin)
        # 200 OK
        self.assertEqual(request.code, http.OK)
        # check we have the required headers
        headers = request.responseHeaders
        self.assertTrue(headers.hasHeader('Allow'))
        # Check the allowed methods (including and in addition to those
        # allowed for CORS)
        allowedMethods = headers.getRawHeaders('Allow')[0].split(', ')
        self.assertEqual(
            len(resource.allowedMethods),
            len(allowedMethods))
        for item in resource.allowedMethods:
            self.assertTrue(item in allowedMethods)
        # There are *NO* CORS related headers
        self.assertFalse(headers.hasHeader('Access-Control-Allow-Origin'))
        self.assertFalse(headers.hasHeader('Access-Control-Max-Age'))
        self.assertFalse(
            headers.hasHeader('Access-Control-Allow-Credentials'))
        self.assertFalse(headers.hasHeader('Access-Control-Allow-Methods'))

    def testInvalidCORSPreFlightRequestBadACRM(self):
        """
        The request has an Origin header but the
        Access-Control-Request-Method header contains an invalid value so
        check it returns a regular OPTIONS response.
        """
        # The origin to use in the tests
        dummyOrigin = 'http://foo.com'

        request = http.Request(DummyChannel(), False)
        request.method = 'OPTIONS'
        request.requestHeaders.setRawHeaders('Origin', [dummyOrigin])
        request.requestHeaders.setRawHeaders(
            'Access-Control-Request-Method',
            ['FOO'])
        request._fluidDB_reqid = 'xxx'
        request.args = dict()
        request.postpath = []
        request.content = NoContent()
        resource = NamespacesResource(FakeFacadeClient(), FakeSession())
        resource._handleOptions(request, dummyOrigin)
        # 200 OK
        self.assertEqual(request.code, http.OK)
        # check we have the required headers
        headers = request.responseHeaders
        self.assertTrue(headers.hasHeader('Allow'))
        # Check the allowed methods (including and in addition to those
        # allowed for CORS)
        allowedMethods = headers.getRawHeaders('Allow')[0].split(', ')
        self.assertEqual(
            len(resource.allowedMethods),
            len(allowedMethods))
        for item in resource.allowedMethods:
            self.assertTrue(item in allowedMethods)
        # There are *NO* CORS related headers
        self.assertFalse(headers.hasHeader('Access-Control-Allow-Origin'))
        self.assertFalse(headers.hasHeader('Access-Control-Max-Age'))
        self.assertFalse(
            headers.hasHeader('Access-Control-Allow-Credentials'))
        self.assertFalse(headers.hasHeader('Access-Control-Allow-Methods'))

    def testInvalidCORSPreFlightRequestNoOrigin(self):
        """
        The request has no Origin header so check it returns a regular OPTIONS
        response.
        """
        request = http.Request(DummyChannel(), False)
        request.method = 'OPTIONS'
        request.requestHeaders.setRawHeaders(
            'Access-Control-Request-Method',
            ['GET'])
        request._fluidDB_reqid = 'xxx'
        request.args = dict()
        request.postpath = []
        request.content = NoContent()
        resource = NamespacesResource(FakeFacadeClient(), FakeSession())
        resource._handleOptions(request, None)
        # 200 OK
        self.assertEqual(request.code, http.OK)
        # check we have the required headers
        headers = request.responseHeaders
        self.assertTrue(headers.hasHeader('Allow'))
        # Check the allowed methods (including and in addition to those
        # allowed for CORS)
        allowedMethods = headers.getRawHeaders('Allow')[0].split(', ')
        self.assertEqual(
            len(resource.allowedMethods),
            len(allowedMethods))
        for item in resource.allowedMethods:
            self.assertTrue(item in allowedMethods)
        # There are *NO* CORS related headers
        self.assertFalse(headers.hasHeader('Access-Control-Allow-Origin'))
        self.assertFalse(headers.hasHeader('Access-Control-Max-Age'))
        self.assertFalse(
            headers.hasHeader('Access-Control-Allow-Credentials'))
        self.assertFalse(headers.hasHeader('Access-Control-Allow-Methods'))

    def testRegularOptionsCall(self):
        """
        Validates that a regular non-CORS OPTIONS call returns an appropriate
        response
        """
        request = http.Request(DummyChannel(), False)
        request.method = 'OPTIONS'
        request._fluidDB_reqid = 'xxx'
        request.args = dict()
        request.postpath = []
        request.content = NoContent()
        resource = NamespacesResource(FakeFacadeClient(), FakeSession())
        resource._handleOptions(request, None)
        # 200 OK
        self.assertEqual(request.code, http.OK)
        # check we have the required headers
        headers = request.responseHeaders
        self.assertTrue(headers.hasHeader('Allow'))
        # Check the allowed methods (including and in addition to those
        # allowed for CORS)
        allowedMethods = headers.getRawHeaders('Allow')[0].split(', ')
        self.assertEqual(
            len(resource.allowedMethods),
            len(allowedMethods))
        for item in resource.allowedMethods:
            self.assertTrue(item in allowedMethods)
        # There are *NO* CORS related headers
        self.assertFalse(headers.hasHeader('Access-Control-Allow-Origin'))
        self.assertFalse(headers.hasHeader('Access-Control-Max-Age'))
        self.assertFalse(
            headers.hasHeader('Access-Control-Allow-Credentials'))
        self.assertFalse(headers.hasHeader('Access-Control-Allow-Methods'))

    def testUnauthorizedOptionsCall(self):
        """
        Validates that a regular non-CORS OPTIONS call returns an appropriate
        response
        """
        request = http.Request(DummyChannel(), False)
        request.method = 'OPTIONS'
        request._fluidDB_reqid = 'xxx'
        request.args = dict()
        request.postpath = []
        request.content = NoContent()
        request.requestHeaders.setRawHeaders('Origin', ['*'])
        resource = WSFEUnauthorizedResource([
            BasicCredentialFactory('example.com')])
        resource.render(request)
        self.assertEqual(http.OK, request.code)
        headers = request.responseHeaders
        self.assertEqual(
            'DELETE, GET, HEAD, POST, PUT',
            headers.getRawHeaders('Allow')[0])
        self.assertEqual(
            'Accept, Authorization, Content-Type, X-FluidDB-Access-Token',
            headers.getRawHeaders('Access-Control-Allow-Headers')[0])
        self.assertEqual(
            'DELETE, GET, HEAD, POST, PUT',
            headers.getRawHeaders('Access-Control-Allow-Methods')[0])

    """
    The following methods make sure that each resource is tested by
    _checkCORSPreFlightRequest defined above.

    This ensures that the CORS request is resulting in the correct headers for
    each of the resources we use (the allowed-methods header will be different
    for each resource).
    """

    def testAboutTagInstanceResource(self):
        resource = AboutTagInstanceResource(FakeFacadeClient(), FakeSession(),
                                            about='foo', path='bar/baz')
        self._checkCORSPreFlightRequest(resource)

    def testAboutObjectResource(self):
        resource = AboutObjectResource(FakeFacadeClient(), FakeSession(),
                                       about='foo')
        self._checkCORSPreFlightRequest(resource)

    def testNamespacesResource(self):
        resource = NamespacesResource(FakeFacadeClient(), FakeSession())
        self._checkCORSPreFlightRequest(resource)

    def testTagInstanceResource(self):
        resource = TagInstanceResource(FakeFacadeClient(), FakeSession(),
                                       objectId='1234', path='bar/baz')
        self._checkCORSPreFlightRequest(resource)

    def testConcretePermissionResource(self):
        resource = ConcretePermissionResource(FakeFacadeClient(),
                                              FakeSession())
        self._checkCORSPreFlightRequest(resource)

    def testTagsResource(self):
        resource = TagsResource(FakeFacadeClient(), FakeSession())
        self._checkCORSPreFlightRequest(resource)

    def testConcreteUserResource(self):
        resource = ConcreteUserResource(FakeFacadeClient(), FakeSession(),
                                        username='test')
        self._checkCORSPreFlightRequest(resource)

    def testValuesResource(self):
        resource = ValuesResource(FakeFacadeClient(), FakeSession())
        self._checkCORSPreFlightRequest(resource)

    def testObjectResource(self):
        resource = ObjectResource(FakeFacadeClient(), FakeSession(),
                                  objectId='1234')
        self._checkCORSPreFlightRequest(resource)

    def testObjectsResource(self):
        resource = ObjectsResource(FakeFacadeClient(), FakeSession())
        self._checkCORSPreFlightRequest(resource)

    def testUsersResource(self):
        resource = UsersResource(FakeFacadeClient(), FakeSession())
        self._checkCORSPreFlightRequest(resource, "POST")
