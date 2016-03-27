from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol
from twisted.web.client import ResponseDone


class ResponseConsumer(Protocol):
    """Receives the body of a response to an HTTP request."""

    def __init__(self):
        self.deferred = Deferred()
        self._bytes = []

    def dataReceived(self, bytes):
        """Handle more data from the response.

        @param bytes: Raw C{str} bytes received as part of the response.
        """
        self._bytes.append(bytes)

    def connectionLost(self, reason):
        """Handle a lost connection.

        The C{Deferred}'s callback is fired with the response payload if the
        connection was closed cleanly.  The errback is fired if the connection
        was lost for any other reason.

        @param reason: A twisted.python.failure C{Failure} instance with
            information about whether the connection was closed cleanly or
            not.
        """
        if reason.check(ResponseDone):
            self.deferred.callback(''.join(self._bytes))
        else:
            self.deferred.errback(reason)
