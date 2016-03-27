from json import dumps
import logging

from twisted.internet.defer import succeed
from twisted.web.http import BAD_REQUEST, OK, UNAUTHORIZED

from fluiddb.common import error, defaults
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.web.payloads import (
    extractPayload, parseJSONPayload, CONTENT_TYPE_RE)
from fluiddb.web.resource import WSFEResource
from fluiddb.web.util import buildHeader


JSONRPC_INVALID_REQUEST = -32600
JSONRPC_METHOD_NOT_FOUND = -32601
JSONRPC_INVALID_PARAMS = -32602
JSONRPC_INTERNAL_ERROR = -32603
JSONRPC_PARSE_ERROR = -32700


class JSONRPCError(Exception):
    """Raised to indicate an expected error from a JSON-RPC method."""


class JSONRPCResource(WSFEResource):
    """Handler for the C{/jsonrpc} API endpoint.

    @param facadeClient: a client for talking to the facade service.
    @param session: an L{AuthenticatedSession} instance.
    @param methods: a C{dict} mapping method names to RPC methods.
    """

    allowedMethods = ('POST', 'OPTIONS')
    isLeaf = True

    def __init__(self, facadeClient, session):
        WSFEResource.__init__(self, facadeClient, session)

    def deferred_render_POST(self, request):
        """Render a response to a C{POST} request to C{/jsonrpc}.

        This endpoint follows the JSONRPC 2.0 specification at
        http://www.simple-is-better.org/json-rpc/jsonrpc20.html
        Error codes are taken from the specification.

        @param request: A C{twisted.web.server.Request} specifying
            meta-information about the request.
        @return: A C{Deferred} that will fire with the body of the
            response from the JSON RPC command, or the body of a
            JSON RPC failure.
        """

        def _prepareErrorResponse(requestID, code, message,
                                  requestPayload=None):
            """Handle a failure in the request.

            @param requestID: Either the request id from the incoming
                request or C{None} if the request had no id.
            @param code: An C{int} error code.
            @param message: A C{str} error message.
            @param requestPayload: A C{str} with the request payload, or
                C{None} if no payload was present or extractable.
            @return: The C{str} body of a JSON RPC error response.
            """
            errorHeader = buildHeader('Request-Id')
            body = dumps({
                'id': requestID,
                'error': {
                    'code': code,
                    'message': message},
                'jsonrpc': '2.0'})

            requestPayload = requestPayload or '<Payload empty or unparseable>'
            if len(requestPayload) > 500:
                requestPayload = (requestPayload[:500] +
                                  ' ... <payload truncated for logging>')
            logging.info('JSON RPC error. Request payload: %s. '
                         'Response payload: %s' % (requestPayload, body))
            request.setHeader('Content-length', str(len(body)))
            request.setHeader('Content-type', 'application/json')
            request.setHeader(errorHeader, request._fluidDB_reqid)
            request.setResponseCode(OK)
            return body

        def _synchronousError(requestID, code, message, requestPayload=None):
            """Handle a synchronous error in the request.

            @param requestID: Either the request id from the incoming
                request or C{None} if the request had no id.
            @param code: An C{int} error code.
            @param message: A C{str} error message.
            @param requestPayload: A C{str} with the request payload, or
                C{None} if no payload was present or extractable.
            @return: a C{Deferred} that has already been fired with
                a serialized JSON RPC error response string.
            """
            body = _prepareErrorResponse(requestID, code, message,
                                         requestPayload)
            return succeed(body)

        # Fail if the content-type header isn't correct.
        contentType = request.getHeader('content-type')

        if contentType is None:
            return _synchronousError(None, JSONRPC_PARSE_ERROR,
                                     'Missing Content-Type header.')

        match = CONTENT_TYPE_RE.match(contentType)
        if match is None:
            return _synchronousError(None, JSONRPC_PARSE_ERROR,
                                     'Unparseable Content-Type header.')

        contentType, charset = match.groups()
        charset = charset or defaults.charset
        if contentType != 'application/json':
            return _synchronousError(None, JSONRPC_PARSE_ERROR,
                                     'Unknown Content-Type.')

        # Get the raw payload bytes from the request.
        try:
            rawPayload = extractPayload(request)
        except (error.ContentLengthMismatch,
                error.ContentChecksumMismatch) as exc:
            return _synchronousError(
                None, JSONRPC_PARSE_ERROR,
                'Invalid payload: %s.' % exc.__class__.__name__)

        # Fail if there was no payload.
        if rawPayload is None:
            return _synchronousError(
                None, JSONRPC_PARSE_ERROR,
                'Missing Content-Length header or empty payload.')

        # Fail if the payload is not valid JSON.
        try:
            payload = parseJSONPayload(rawPayload, charset)
        except error.MalformedPayload:
            return _synchronousError(None, JSONRPC_PARSE_ERROR,
                                     'Payload was not valid JSON.',
                                     requestPayload=rawPayload)

        # Fail if the payload was not a dict (i.e., a JSON object).
        if not isinstance(payload, dict):
            return _synchronousError(None, JSONRPC_PARSE_ERROR,
                                     'Payload was not a JSON object.',
                                     requestPayload=rawPayload)

        requestID = payload.get('id')

        # Fail if the request had no id. See JSONRPC spec.
        if requestID is None:
            return _synchronousError(None, JSONRPC_INVALID_REQUEST,
                                     "Request had no 'id' argument.",
                                     requestPayload=rawPayload)

        version = payload.get('jsonrpc')

        # Fail if the request had no JSON RPC version. See JSONRPC spec.
        if version is None:
            return _synchronousError(requestID, JSONRPC_INVALID_REQUEST,
                                     "Request had no 'jsonrpc' argument.",
                                     requestPayload=rawPayload)

        # Fail if the jsonrpc version is not supported.
        if version != '2.0':
            return _synchronousError(
                requestID, JSONRPC_INVALID_REQUEST,
                "Only JSON RPC version 2.0 is supported.",
                requestPayload=rawPayload)

        methodName = payload.get('method')

        # Fail if the request has no method name. See JSONRPC spec.
        if methodName is None:
            return _synchronousError(requestID, JSONRPC_INVALID_REQUEST,
                                     "Request had no 'method' argument.",
                                     requestPayload=rawPayload)

        method = getattr(self, 'jsonrpc_' + methodName, None)
        # Fail if we don't have a method by that name. See JSONRPC spec.
        if method is None:
            return _synchronousError(requestID, JSONRPC_METHOD_NOT_FOUND,
                                     "Unknown method %r." % methodName,
                                     requestPayload=rawPayload)

        # Parameters (optional) for the call can either be a dict or a list.
        # See which one we got (if any).

        params = payload.get('params')

        if params is None:
            args = []
            kwargs = {}
        elif isinstance(params, dict):
            args = []
            kwargs = params
        elif isinstance(params, list):
            args = params
            kwargs = {}
        else:
            # Fail: the parameters are neither a dict nor a list.
            # See JSONRPC spec.
            return _synchronousError(requestID, JSONRPC_INVALID_PARAMS,
                                     'Params not an object or a list.',
                                     requestPayload=rawPayload)

        # Define call/errbacks to handle processing the method call.

        def _failure(failure, requestID):
            """Handle a failure caused by processing a valid request.

            @param requestID: the id from the incoming request.
            @param failure: a Twisted C{Failure} instance with a value that is
                a C{dict} containing an error response, as specified in
                http://www.simple-is-better.org/json-rpc/jsonrpc20.html
            """
            if failure.check(PermissionDeniedError):
                code = UNAUTHORIZED
                message = 'Access denied.'
            elif failure.check(JSONRPCError):
                code = BAD_REQUEST
                message = str(failure.value)
            else:
                # An internal (non-client) error.
                code = JSONRPC_INTERNAL_ERROR
                message = 'Internal error.'
                logging.error('JSON RPC internal error: %s' %
                              failure.getTraceback())
            body = _prepareErrorResponse(requestID, code, message,
                                         requestPayload=rawPayload)
            return body

        def _success(result, requestID):
            """Finishing handling a successful request.

            @param requestID: the id from the incoming request.
            @param result: a C{dict} containing the result, as specified
                in http://www.simple-is-better.org/json-rpc/jsonrpc20.html
            """
            body = dumps({
                'id': requestID,
                'jsonrpc': '2.0',
                'result': result
            })
            request.setHeader('Content-length', str(len(body)))
            request.setHeader('Content-type', 'application/json')
            request.setResponseCode(OK)
            return body

        def _internalError(failure, requestID):
            """Handle a failure caused by one of our callbacks.

            This method will only be called if one of '_failure' or
            '_success' above unexpectedly fails due to being incorrectly
            written or because an error or result argument cannot be
            serialized by C{dumps}.

            @param failure: a Twisted C{Failure} instance.
            @param requestID: The id from the incoming JSON RPC request.
            """
            logging.error('Internal error processing JSON RPC call. '
                          'Request id %s' % request._fluidDB_reqid)
            logging.exception(failure.value)
            body = _prepareErrorResponse(requestID, JSONRPC_INTERNAL_ERROR,
                                         'Error processing deferred callback.',
                                         requestPayload=rawPayload)
            return body

        # Call the method, passing the session and the parameters we
        # received.  Arrange to process the result.

        deferred = method(self.session, *args, **kwargs)
        deferred.addCallbacks(_success, _failure,
                              callbackArgs=(requestID,),
                              errbackArgs=(requestID,))
        deferred.addErrback(_internalError, requestID)
        return deferred
