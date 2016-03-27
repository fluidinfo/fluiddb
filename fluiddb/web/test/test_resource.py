from twisted.internet.defer import CancelledError
from twisted.python.failure import Failure
from twisted.trial.unittest import TestCase
from twisted.web.http import BAD_REQUEST, INTERNAL_SERVER_ERROR
from twisted.web.http_headers import Headers

from fluiddb.common.error import ContentSeekError
from fluiddb.testing.doubles import FakeSession
from fluiddb.web.resource import WSFEResource, handleRequestError


class FakeRequest(object):
    """
    A fake request suitable for use in place of C{twisted.web.http.Request}.

    @param method: The HTTP method being invoked such as C{GET} or C{POST}.
    """

    def __init__(self, method):
        self.method = method
        self.requestHeaders = Headers()
        self.responseHeaders = Headers()
        self._fluidDB_reqid = 'xxx'
        self.finished = False

    def finish(self):
        """
        Indicate that all response data has been written to this request.
        """
        self.finished = True

    def getResponseHeader(self, name):
        """
        Get the value of an HTTP response header.

        @param name: The name of the HTTP header to retrieve a value for.
        @return: The value set for the header or C{None} if a value is not
            available.
        """
        value = self.responseHeaders.getRawHeaders(name)
        if value is not None:
            return value[-1]

    def setHeader(self, name, value):
        """
        Set an HTTP header to include in the response returned to the client.

        @param name: The name of the header to set.
        @param value: The value to set.
        """
        self.responseHeaders.setRawHeaders(name, [value])

    def setResponseCode(self, code):
        """
        Set the HTTP response code to return to the client.

        @param code: An HTTP response code as defined in C{twisted.web.http}.
        """
        self.status = code


class HandleRequestErrorTest(TestCase):

    def setUp(self):
        super(HandleRequestErrorTest, self).setUp()
        facadeClient = None
        session = FakeSession()
        self.resource = WSFEResource(facadeClient, session)
        self.request = FakeRequest("GET")

    def testImmediateDisconnectDoesNotFinishRequest(self):
        """
        A L{ContentSeekError} exception is raised if content cannot be read
        from the request, such as when a client disconnected immediately.
        In such cases, the C{Request.finish} method is not invoked by the
        L{handleRequestError} handler to avoid causing a failure in
        Twisted.
        """
        failure = Failure(ContentSeekError("Client disconnected immediately."))
        handleRequestError(failure, self.request, self.resource)
        self.assertFalse(self.request.finished)

    def testDelayedDisconnectDoesNotFinishRequest(self):
        """
        A C{CancelledError} exception is raised if content cannot be read
        from the request midway through processing, due to the client
        disconnecting.  In such cases, the C{Request.finish} method is not
        invoked by the L{handleRequestError} handler to avoid causing a
        failure in Twisted.
        """
        failure = Failure(CancelledError("Client disconnected partway."))
        handleRequestError(failure, self.request, self.resource)
        self.assertFalse(self.request.finished)

    def testFailureFinishesRequest(self):
        """
        The C{Request.finish} method is invoked if a non-connection-related
        C{Failure} causes error handling logic to be invoked.
        """
        failure = Failure(Exception("Another failure occurred."))
        handleRequestError(failure, self.request, self.resource)
        self.assertTrue(self.request.finished)

    def testFailureReportsRequestID(self):
        """
        The unique request ID is included in HTTP response headers when a
        failure occurs.
        """
        failure = Failure(Exception("Another failure occurred."))
        handleRequestError(failure, self.request, self.resource)
        self.assertEqual(
            "xxx", self.request.getResponseHeader("X-FluidDB-Request-Id"))

    def testKnownErrorTypeReturnsAppropriateHTTPStatus(self):
        """
        If the exception that caused L{handleRequestError} to be invoked is
        of a wellknown type, the HTTP response code will be set
        appropriately.
        """
        failure = Failure(ContentSeekError("Client disconnected immediately."))
        handleRequestError(failure, self.request, self.resource)
        self.assertEqual(BAD_REQUEST, self.request.status)

    def testUnknownErrorTypeReturnsInternalServerErrorHTTPStatus(self):
        """
        If the exception that caused L{handleRequestError} to be invoked is
        of an unexpected type, the HTTP response code will be set to
        C{INTERNAL_SERVER_ERROR}.
        """
        failure = Failure(Exception("Unknown error occurred."))
        handleRequestError(failure, self.request, self.resource)
        self.assertEqual(INTERNAL_SERVER_ERROR, self.request.status)

    def testKnownErrorTypeReportsErrorClass(self):
        """
        If a known exception causes L{handleRequestError} to run the
        C{X-FluidDB-Error-Class} HTTP response header will be set with the
        name of the exception class.
        """
        failure = Failure(ContentSeekError("Client disconnected immediately."))
        handleRequestError(failure, self.request, self.resource)
        self.assertEqual(
            "ContentSeekError",
            self.request.getResponseHeader("X-FluidDB-Error-Class"))

    def testUnknownErrorTypeReportsInternalServerErrorClass(self):
        """
        If an unknown exception causes L{handleRequestError} to run the
        C{X-FluidDB-Error-Class} HTTP response header will be set to
        C{InternalServerError}.
        """
        failure = Failure(Exception("Unknown error occurred."))
        handleRequestError(failure, self.request, self.resource)
        self.assertEqual(
            "InternalServerError",
            self.request.getResponseHeader("X-FluidDB-Error-Class"))
