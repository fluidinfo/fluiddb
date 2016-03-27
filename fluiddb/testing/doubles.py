from cStringIO import StringIO
from uuid import uuid4

from twisted.internet.defer import succeed, Deferred
from twisted.internet.protocol import Protocol
from twisted.internet.task import Clock
from twisted.python.failure import Failure
from twisted.test.proto_helpers import MemoryReactor
from twisted.web.http import OK
from twisted.web.http_headers import Headers

from fluiddb.web.util import requestId


class FakeThreadPool(object):
    """
    A fake C{twisted.python.threadpool.ThreadPool} that runs a function inside
    the main thread, to make testing easier.
    """

    def callInThreadWithCallback(self, onResult, function, *args, **kwargs):
        """
        A dummy version of Twisted's C{ThreadPool.callInThreadWithCallback}.
        """
        success = True
        try:
            result = function(*args, **kwargs)
        except:
            result = Failure()
            success = False

        onResult(success, result)


class FakeRequest(object):
    """
    A fake C{twisted.web.http.Request} implementation, suitable for use in
    tests.
    """

    def __init__(self, args=None, postpath=None, prepath=None, path=None,
                 uri=None, method='GET', headers=None, body=''):
        self.args = {} if args is None else args
        self.written = StringIO()
        self.finished = False
        self.code = None
        self.method = method
        self.path = path
        self.postpath = postpath
        self.prepath = prepath
        self.requestHeaders = Headers({}) if headers is None else headers
        self.responseHeaders = Headers({})
        self.uri = uri
        self._fluidDB_reqid = requestId()
        self.content = StringIO(body)

    def write(self, content):
        """Write data as a result of an HTTP request.

        @param content: A C{str} containing the bytes to send as part of the
            response body.
        """
        if not isinstance(content, str):
            raise RuntimeError('Only strings can be written.')
        self.written.write(content)

    def finish(self):
        """Indicate that all response data has been written to this request."""
        if self.code is None:
            self.code = 200
        self.finished = True

    def setResponseCode(self, code):
        """Set the HTTP response code.

        @param code: An C{int} HTTP status code.
        """
        self.code = code

    def setHeader(self, key, value):
        """Set an HTTP response header.

        @param key: The name of the response header.
        @param value: The value for the response header.
        """
        self.responseHeaders.setRawHeaders(key, [value])

    def getHeader(self, key):
        """
        Get a header from the request. This is copied from Twisted's
        C{twisted.web.http.Request} class.

        @param key: A C{str} indicating the header to return.
        @return: The C{str} header value from the request if it exists,
            else C{None}.
        """
        value = self.requestHeaders.getRawHeaders(key)
        if value is not None:
            return value[-1]

    def getResponseHeader(self, key):
        """Get a header from the response.

        @param key: A C{str} indicating the header to return.
        @return: The C{str} header value from the response if it exists,
            else C{None}.
        """
        value = self.responseHeaders.getRawHeaders(key)
        if value is not None:
            return value[-1]

    @property
    def response(self):
        """The HTTP response body."""
        return self.written.getvalue()

    def getAllHeaders(self):
        """
        Get all the request headers. This is copied from Twisted's
        C{twisted.web.http.Request} class.

        @return: A C{dict} of request header name -> value.
        """
        headers = {}
        for k, v in self.requestHeaders.getAllRawHeaders():
            headers[k.lower()] = v[-1]
        return headers

    def notifyFinish(self):
        """
        Return a C{twisted.internet.Deferred} that fires when the request
        finishes or errors if the client disconnects. Note that this method
        is needed as resource.py calls it, but we do not need to actually
        fire the returned deferred for our tests (which cause synchronous
        exceptions to immediately be returned to the request errback).

        @return: A C{Deferred} as just described.
        """
        return succeed(None)

    def isSecure(self):
        """Is the request secure?

        @return: a C{bool} that is C{True} if the request is secure.
        """
        # The way we tell if a request is secure is based on a header set
        # for us by nginx. Our Twisted web service only handles plain http
        # requests that are forwarded to it by nginx (via haproxy).
        secureHeader = self.getHeader('X-Forwarded-Protocol')
        return (secureHeader == 'https')


class FakeSession(object):
    """
    A fake session that is compatible with both L{AuthenticatedSession} and
    L{FluidinfoSession}.
    """

    id = 'id'
    username = 'Lex Luther'
    running = True

    class auth(object):

        username = 'Lex Luther'
        objectId = uuid4()

    def stop(self):
        """Stop the session."""
        self.running = False


# The FakeHTTPProtocol, FakeReactor and FakeReactorAndConnectMixin are all
# copied (and slightly modified) from twisted.web.test.test_webclient.  They
# can't be imported from the version of Twisted installed by system packages
# or from an egg downloadd from PyPI because the module is not included.

class FakeHTTPProtocol(Protocol):
    """
    A protocol like L{HTTP11ClientProtocol} but which does not actually know
    HTTP/1.1 and only collects requests in a list.

    @ivar requests: A C{list} of two-tuples.  Each time a request is made, a
        tuple consisting of the request and the L{Deferred} returned from the
        request method is appended to this list.
    """
    def __init__(self):
        self.requests = []

    def request(self, request):
        """Capture the given request for later inspection.

        @return: A L{Deferred} which this code will never fire.
        """
        result = Deferred()
        self.requests.append((request, result))
        return result


class FakeReactorAndConnectMixin(object):
    """
    A test mixin providing a testable C{Reactor} class and a dummy
    C{Agent._connect} method.
    """

    class FakeReactor(MemoryReactor, Clock):
        """A fake C{Reactor} for use in tests."""

        def __init__(self):
            MemoryReactor.__init__(self)
            Clock.__init__(self)

    def _connect(self, scheme, host, port):
        """
        Fake implementation of L{Agent._connect} which synchronously
        succeeds with an instance of L{FakeHTTPProtocol} for ease of
        testing.
        """
        protocol = FakeHTTPProtocol()
        protocol.makeConnection(None)
        self.protocol = protocol
        return succeed(protocol)


class FakeResponse(object):
    """A fake C{Response} that can stream a response payload to a consumer.

    @param reason: An exception instance describing the reason the connection
        was lost.
    @param body: The response payload to deliver to the consumer.
    @param code: Optionally, the HTTP status code for this request.  Default
        is C{200} (OK).
    @param headers: Optionally, a C{Headers} instance with the response
        headers.
    """

    code = OK
    headers = Headers({})

    def __init__(self, reason, body, code=None, headers=None):
        self.reason = reason
        self.body = body
        if code:
            self.code = code
        if headers:
            self.headers = headers

    def deliverBody(self, protocol):
        """Deliver the canned response payload to the consumer.

        The connection is closed with the canned reason, after the body has
        been delivered.

        @param protocol: The C{Protocol} instance to deliver the response
            payload to.
        """
        protocol.dataReceived(self.body)
        protocol.connectionLost(Failure(self.reason))
