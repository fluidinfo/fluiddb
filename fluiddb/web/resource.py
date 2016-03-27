from cStringIO import StringIO
import logging
import os

from twisted.web import resource, http, server
from twisted.web.error import ErrorPage as TwistedErrorPage
from twisted.internet import defer
from twisted.internet.defer import CancelledError
from twisted.python import log

from fluiddb.application import getConfig
from fluiddb.common import defaults, error
from fluiddb.common.error import ContentSeekError, UnwrappableBlob
from fluiddb.common.types_thrift import ttypes
from fluiddb.common.types_thrift.ttypes import ThriftValueType
from fluiddb.common.util import thriftExceptions, dictSubset
from fluiddb.util.session import SessionStorage
from fluiddb.web.util import buildHeader

# The following Thrift exceptions will result in the given HTTP error
# codes.  Furthermore, the contents of their Thrift struct will be sent
# back to the client as a JSON dict. So don't add anything to this dict
# that could leak sensitive internal information.
#
# All other Thrift errors will return something more generic (probably
# INTERNAL_SERVER_ERROR) and give less information.
#

_thriftExceptionToHTTPCode = {
    ttypes.TTagAlreadyExists: http.PRECONDITION_FAILED,
    ttypes.TBadArgument: http.BAD_REQUEST,
    ttypes.TBadRequest: http.BAD_REQUEST,
    ttypes.TInvalidPath: http.BAD_REQUEST,
    ttypes.TInvalidPolicy: http.BAD_REQUEST,
    ttypes.TInvalidUsername: http.BAD_REQUEST,
    ttypes.TNamespaceAlreadyExists: http.PRECONDITION_FAILED,
    ttypes.TNamespaceNotEmpty: http.PRECONDITION_FAILED,
    ttypes.TNoInstanceOnObject: http.NOT_FOUND,
    ttypes.TNoSuchUser: http.NOT_FOUND,
    ttypes.TNonexistentTag: http.NOT_FOUND,
    ttypes.TNonexistentNamespace: http.NOT_FOUND,
    ttypes.TPasswordIncorrect: http.BAD_REQUEST,
    ttypes.TPathPermissionDenied: http.UNAUTHORIZED,
    ttypes.TSetTagInstanceGivingUp: http.CONFLICT,
    ttypes.TUnauthorized: http.UNAUTHORIZED,
    ttypes.TUniqueRangeError: http.PRECONDITION_FAILED,
    ttypes.TUserAlreadyExists: http.PRECONDITION_FAILED,
    ttypes.TUsernameTooLong: http.BAD_REQUEST,
    ttypes.TInvalidName: http.BAD_REQUEST,
    ttypes.TParseError: http.BAD_REQUEST,
}

# The following FluidDB exceptions (raised when checking the request)
# will result in the given HTTP error.

_exceptionToHTTPCode = {
    error.ContentLengthMismatch: http.BAD_REQUEST,
    error.ContentSeekError: http.BAD_REQUEST,
    error.InvalidPayloadField: http.BAD_REQUEST,
    error.InvalidUTF8Argument: http.BAD_REQUEST,
    error.MalformedPayload: http.BAD_REQUEST,
    error.MissingArgument: http.BAD_REQUEST,
    error.MissingPayload: http.BAD_REQUEST,
    error.MultipleArgumentValues: http.BAD_REQUEST,
    error.NoContentLengthHeader: http.LENGTH_REQUIRED,
    error.NoContentTypeHeader: http.BAD_REQUEST,
    error.NoOriginHeader: http.BAD_REQUEST,
    error.NoSuchObject: http.NOT_FOUND,
    error.NotAcceptable: http.NOT_ACCEPTABLE,
    error.PayloadFieldMissing: http.BAD_REQUEST,
    error.UnexpectedContentLengthHeader: http.BAD_REQUEST,
    error.UnknownAcceptType: http.BAD_REQUEST,
    error.UnknownArgument: http.BAD_REQUEST,
    error.UnknownContentType: http.BAD_REQUEST,
    error.UnknownPayloadField: http.BAD_REQUEST,
    error.UnsupportedJSONType: http.BAD_REQUEST,
    error.UnwrappableBlob: http.BAD_REQUEST,
    error.ContentChecksumMismatch: http.PRECONDITION_FAILED,
}

# These are the additional exception tags that we want to send back
# to the client during request processing. E.g., if UnknownPayloadField is
# raised then, as well as the error class information, we will also return
# the 'fieldName' tag of the error so our client can see which
# payload field was unknown. In other words, the following specifies the
# additional information to be returned (if any), depending on the problem
# with the request.
#
# Note that exceptions mentioned here must also appear above in
# _exceptionToHTTPCode.

_exceptionTags = {
    error.InvalidPayloadField: ('fieldName',),
    error.InvalidUTF8Argument: ('argument',),
    error.MalformedPayload: ('message',),
    error.MissingArgument: ('argument',),
    error.MultipleArgumentValues: ('argument',),
    error.PayloadFieldMissing: ('fieldName',),
    error.UnknownArgument: ('argument',),
    error.UnknownPayloadField: ('fieldName',),
}


class WSFEResource(resource.Resource):

    # 42 days ;-)
    ACCESS_CONTROL_MAX_AGE = 3628800

    primitiveTypeNames = {
        ThriftValueType.BOOLEAN_TYPE: 'boolean',
        ThriftValueType.FLOAT_TYPE: 'float',
        ThriftValueType.INT_TYPE: 'int',
        ThriftValueType.NONE_TYPE: 'null',
        ThriftValueType.STR_TYPE: 'string',
        ThriftValueType.SET_TYPE: 'list-of-strings',
    }

    def __init__(self, facadeClient, session):
        resource.Resource.__init__(self)
        self.facadeClient = facadeClient
        self.session = session

    def _getTypeHeader(self, thriftType):
        """
        Get the the value for C{X-FluidDB-Type} header given a
        L{ThriftValueType}.

        @param thriftType: An integer representing the L{ThriftValueType}.
        @return: A string containing the value for an X-FluidDB-Type header.
        """
        return self.primitiveTypeNames[thriftType]

    def render_GET(self, request):
        return self._handleRender(request)

    def render_POST(self, request):
        return self._handleRender(request)

    def render_HEAD(self, request):
        return self._handleRender(request)

    def render_DELETE(self, request):
        return self._handleRender(request)

    def render_PUT(self, request):
        return self._handleRender(request)

    def render_OPTIONS(self, request):
        return self._handleRender(request)

    def _handleRender(self, request):
        log.msg('Request %s: User %s: %s %r' % (
            request._fluidDB_reqid, self.session.auth.username,
            request.method, request.uri))
        headers = dictSubset(request.getAllHeaders(),
                             ('content-length', 'content-type', 'accept'))
        log.msg('Request %s: Headers: %r' % (request._fluidDB_reqid, headers))

        # Check the HTTP scheme, the X-Forwarded-Protocol must be set by the
        # frontend (e.g. Nginx) and it must be either http or https
        isSecure = False
        secureHeader = request.getHeader("X-Forwarded-Protocol")
        if secureHeader is not None:
            if secureHeader == "https":
                isSecure = True

        # This forces Request#isSecure() to return true if X-Forwarded-Protocol
        # if it's set to "https"
        request._forceSSL = isSecure

        # XXX hardcoded values
        if request.method == 'GET':
            try:
                verb = request.args['verb'][0]
                request.requestHeaders.removeHeader('Content-Type')
                request.requestHeaders.removeHeader('Content-Length')
                request.requestHeaders.removeHeader('Content-Encoding')

                if verb in ('POST', 'PUT'):
                    payload = request.args.get('payload')
                    payloadType = request.args.get('payload-type')
                    payloadEncoding = request.args.get('payload-encoding')
                    payloadLength = request.args.get('payload-length')

                    if payloadLength is not None:
                        payloadLength = payloadLength[0]
                        request.requestHeaders.addRawHeader(
                            'Content-Length', payloadLength)

                    if payload is not None:
                        payload = payload[0]
                        request.content = StringIO(payload)

                    if payloadType is not None:
                        payloadType = payloadType[0]
                        request.requestHeaders.addRawHeader(
                            'Content-Type', payloadType)

                    if payloadEncoding is not None:
                        payloadEncoding = payloadEncoding[0]
                        request.requestHeaders.addRawHeader(
                            'Content-Encoding', payloadEncoding)
            except KeyError:
                verb = request.method
        else:
            verb = request.method

        # If an origin header is sent we need to leap into CORS mode :-)
        origin = request.getHeader('Origin')
        if origin:
            # OPTIONS handling as per rfc2616 and CORS specification
            if verb == 'OPTIONS':
                return self._handleOptions(request, origin)
            else:
                # all responses must contain these headers for this to be a
                # valid CORS based request
                request.setHeader('Access-Control-Allow-Origin', origin)
                request.setHeader('Access-Control-Allow-Credentials', 'true')
                request.setHeader('Access-Control-Expose-Headers',
                                  ('X-FluidDB-Access-Token, '
                                   'X-FluidDB-Action, '
                                   'X-FluidDB-Argument, '
                                   'X-FluidDB-Category, '
                                   'X-FluidDB-Error-Class, '
                                   'X-FluidDB-Fieldname, '
                                   'X-FluidDB-Message, '
                                   'X-FluidDB-Name, '
                                   'X-FluidDB-New-User, '
                                   'X-FluidDB-ObjectId, '
                                   'X-FluidDB-Path, '
                                   'X-FluidDB-Query, '
                                   'X-FluidDB-Rangetype, '
                                   'X-FluidDB-Type, '
                                   'X-FluidDB-Username'))

        renderer = getattr(self, 'deferred_render_' + verb, None)

        if renderer:
            d = defer.maybeDeferred(renderer, request)
            if request.args.get('callback'):
                # Callback wrapping was requested in the URI, so arrange to
                # post-process the value.
                d.addCallback(self._wrapValueWithCallback, request)
            d.addCallback(self._finish, request)
            d.addErrback(handleRequestError, request, self)
            d.addBoth(self._stopSession)
            # Add a log.err errback, which ensures that any coding error in
            # handleRequestError will not totally disappear. Yes, this
            # just happened to me (Terry).
            d.addErrback(log.err)
            request.notifyFinish().addErrback(self._notifyFinishError,
                                              request, d)
            return server.NOT_DONE_YET
        else:
            request.setHeader(buildHeader('Request-Id'),
                              request._fluidDB_reqid)
            request.setHeader(buildHeader('Error-Class'),
                              'UnsupportedMethod')
            self._stopSession()
            from twisted.web.server import UnsupportedMethod
            raise UnsupportedMethod(getattr(self, 'allowedMethods', ()))

    def _stopSession(self, result=None):
        """Stop the session and persist it to disk.

        @param result: The result so far in the request processing.
            Note that this has a default C{None} value because this method
            can be called directly above (not as part of an errback chain).
        @return: the C{result} we were passed.
        """
        if not self.session.running:
            logging.warning('Trying to stop session %s twice.',
                            self.session.id)
            return result

        self.session.stop()
        config = getConfig()
        # FIXME This is a hack to avoid breaking old tests.
        if config:
            tracePath = config.get('service', 'trace-path')
            port = config.get('service', 'port')
            logPath = os.path.join(tracePath,
                                   'fluidinfo-api-trace-%s.log' % port)
            storage = SessionStorage()
            storage.dump(self.session, logPath)
            if self.session.duration.seconds > 0:
                logging.warning('Long request: %s. Time: %s.',
                                self.session.id, self.session.duration)
        return result

    def _handleOptions(self, request, origin):
        """
        Handles the incoming request that uses the HTTP OPTIONS method as per
        rfc2616 and the CORS specification. (If origin is set then the request
        is CORS based)
        """
        # check allowedMethods is defined for this class
        if not hasattr(self, 'allowedMethods'):
            raise RuntimeError(
                "'allowedMethods' must be defined by subclasses.")
        # The following two headers make us conform to rfc2616 wrt OPTIONS
        # *APART FROM* responding to a Request-URI that is an asterisk
        # ("*") where the OPTIONS request is intended to apply to the
        # server in general rather than to a specific resource.
        request.setResponseCode(http.OK)
        request.setHeader('Allow', ', '.join(self.allowedMethods))
        # The presence and validation of the Access-Control-Request-Method
        # header makes it a pre-flight request (in addition to the origin
        # header passed into this function).
        requestMethod = request.getHeader('Access-Control-Request-Method')
        # FluidDB's validation rules are to allow all origin values and
        # confirm that the request_method is appropriate for the resource
        if origin and requestMethod in self.allowedMethods:
            # Content-Type is set in the request headers so indicate
            # that it is allowed for this resource
            request.setHeader('Access-Control-Allow-Headers',
                              'Accept, Authorization, Content-Type, '
                              'X-FluidDB-Access-Token')
            # we have a valid pre-flight request - now add the
            # appropriate headers to the response sent to the client.
            request.setHeader('Access-Control-Allow-Origin', origin)
            request.setHeader('Access-Control-Max-Age',
                              str(self.ACCESS_CONTROL_MAX_AGE))
            request.setHeader('Access-Control-Allow-Credentials', 'true')
            request.setHeader('Access-Control-Allow-Methods',
                              ', '.join(self.allowedMethods))
        return ''

    def _notifyFinishError(self, reason, request, deferred):
        """
        Cancel a request due to a client disconnect.

        @param reason: A C{Failure} describing the cause of the error.
        @param request: The request instance used for the broken connection.
        @param deferred: The C{Deferred} that would have been fired to produce
                  the client response had the connection not been dropped.
                  It will now be cancelled.
        """
        log.msg('Request %s: client connection error: %s' %
                (request._fluidDB_reqid, reason))
        deferred.cancel()

    def _wrapValueWithCallback(self, value, request):
        """The request had a callback argument in the URI. Here we wrap the
        content (if any) in a call to that callback function.
        """
        # XXX unsure about this, I think the callback
        # arg can be used with any format, not just JSON
        if hasattr(request, '_fluiddb_jsonp_unwrappable'):
            raise UnwrappableBlob('Tag value is not wrappable.')
        callback = request.args.get('callback')[0]
        contentType = request.responseHeaders.getRawHeaders('Content-Type')

        if value is None or contentType is None:
            value = '%s()' % callback
        elif contentType[0] in ('application/json',
                                defaults.contentTypeForPrimitiveJSON):
            value = '%s(%s)' % (callback, value)
        else:
            raise error.InternalError('Content type not properly set.')

        request.setHeader('Content-Length', str(len(value)))
        request.setHeader('Content-Type', 'text/javascript')
        return value

    def _finish(self, value, request):
        # No responses may be cached. To be refined later.
        request.setHeader('Cache-Control', 'no-cache')
        if value is not None:
            request.write(value)
        request.finish()


def _addClientErrorHeaders(request, exception, headers):
    """
    When a client error causes an exception, we send an HTTP response with
    headers that indicate the type of exception that occurred and other
    details that might help in debugging. E.g. we might indicate that a
    permission denied error occurred and also give the path to the tag or
    namespace in question.

    In this function we set the Error-Class header and extract any relevant
    tags from the exception and set a header for each.

    @param request: the HTTP request that has resulted in the exception.
    @param exception: an instance of some kind of C{Exception}.
    @param headers: a dictionary of header names and values.
    """
    exceptionClass = exception.__class__
    headers['Error-Class'] = exceptionClass.__name__
    tags = (_exceptionTags.get(exceptionClass) or
            thriftExceptions.get(exceptionClass) or [])

    for tag in tags:
        value = getattr(exception, tag)
        if tag in headers:
            # Don't overwrite the already present value, just complain.
            log.msg('Request %s: Exception tag %r is already '
                    'an existing return header field. Current value %r, '
                    'value from exception %r.' %
                    (request._fluidDB_reqid, tag,
                     headers[tag], value))
            request.setResponseCode(http.INTERNAL_SERVER_ERROR)
        else:
            headers[tag] = value


def _logInternalError(request, exception, fail, resourceClass):
    """
    Log a FluidDB internal error. Apart from doing the obvious things, we
    also pull all relevant tags off any Thrift error (our internal
    errors tend to come from calls we've made to the facade service via
    Thrift) and log them too.
    """
    log.msg('Request %s: Exception calling %r#deferred_render_%r ' %
            (request._fluidDB_reqid, resourceClass.__class__.__name__,
             request.method))
    log.msg(exception)
    traceback = fail.getTraceback()

    # If we get a CancelledError, we only log it as a warning, this is not a
    # sever error and it causes too much noise in the log files.
    if fail.check(CancelledError):
        logging.warning(traceback)
    else:
        logging.error(traceback)

    tags = thriftExceptions.get(exception.__class__)
    if tags:
        msg = []
        for tag in tags:
            msg.append('Failure tag %r: %r' %
                       (tag, getattr(exception, tag)))
        if msg:
            log.msg('\n'.join(msg))


def handleRequestError(fail, request, resourceClass):
    """
    Deal with an error that occurred in processing a request. There are two
    main cases: the error is due to an internal FluidDB problem, or the
    error was due to the client request (e.g., a missing URI arg,
    permission denied on tag access).
    """
    exception = fail.value
    exceptionClass = exception.__class__
    HTTPErrorCode = (_exceptionToHTTPCode.get(exceptionClass) or
                     _thriftExceptionToHTTPCode.get(exceptionClass))
    headers = {'Request-Id': request._fluidDB_reqid}

    if HTTPErrorCode is None:
        # Internal FluidDB error.
        headers['Error-Class'] = 'InternalServerError'
        request.setResponseCode(http.INTERNAL_SERVER_ERROR)
        _logInternalError(request, exception, fail, resourceClass)
    else:
        # Client request error.
        request.setResponseCode(HTTPErrorCode)
        _addClientErrorHeaders(request, exception, headers)
        log.msg('Request %s: Client error: %r' %
                (request._fluidDB_reqid, headers))

    # Add the X-FluidDB prefix to all the headers created so far.
    for key, value in headers.items():
        if isinstance(value, unicode):
            value = value.encode('utf-8')
        else:
            value = str(value)
        request.setHeader(buildHeader(key), value)

    # Add a WWW-Authenticate header to 401 errors.
    # See section 1.2 of http://www.ietf.org/rfc/rfc2617.txt
    if HTTPErrorCode == http.UNAUTHORIZED:
        request.setHeader('WWW-Authenticate', 'Basic realm="Fluidinfo"')

    # Call request.finish if the client is still connected.
    #
    # We need to detect if the client has disconnected. If so and we
    # nevertheless call request.finish, an exception is raised by
    # twisted.web.server, which logs a message telling us to use
    # request.notifyFinish.
    #
    # It seems there are two code paths arriving in this errback
    # function when a disconnect has occurred:
    #
    # 1. When the client disconnects immediately, the seek on the
    # request content raises a ContentSeekError which arrives here
    # synchronously via the errback of the render resource, before
    # twisted.web has a chance to detect the disconnect and call the
    # notifyFinish errbacks.
    #
    # 2. If the client disconnects somewhat later, twisted.web detects
    # it and calls the notifyFinish errback, causing a
    # defer.CancelledError failure to arrive here.
    #
    # The fail.check below is therefore intended to take care of those
    # two code paths following client disconnection.

    if fail.check(defer.CancelledError, ContentSeekError):
        log.msg('Request %s: Not calling request.finish. Client '
                'apparently disconnected.' % request._fluidDB_reqid)
    else:
        request.finish()


class ErrorResource(resource.Resource):

    def __init__(self, status, errorClass, headers=None):
        resource.Resource.__init__(self)
        self.status = status
        self.errorClass = errorClass
        self.headers = headers or {}

    def render(self, request):
        msg = 'ErrorResource: status %r' % self.status
        request.setResponseCode(self.status)
        headers = self.headers
        headers.setdefault('Error-Class', self.errorClass.__name__)
        headers.setdefault('Request-Id', request._fluidDB_reqid)
        for key, value in headers.iteritems():
            request.setHeader(buildHeader(key), value)
            msg += (', %s=%r' % (key, value))
        log.msg(msg)
        request.finish()
        return server.NOT_DONE_YET

    def getChild(self, name, request):
        return self


class ErrorPage(TwistedErrorPage):

    def __init__(self, status, brief, detail, errorClassName):
        self.errorClassName = errorClassName
        TwistedErrorPage.__init__(self, status, brief, detail)

    def render(self, request):
        log.msg('Request %s: ErrorPage: status %s, class %s' % (
            request._fluidDB_reqid, self.code, self.errorClassName))
        request.setHeader(buildHeader('Error-Class'), self.errorClassName)
        request.setHeader(buildHeader('Request-Id'), request._fluidDB_reqid)
        return TwistedErrorPage.render(self, request)


class NoResource(TwistedErrorPage):

    def __init__(self, message='Sorry, we could not find that resource.'):
        TwistedErrorPage.__init__(self, http.NOT_FOUND,
                                  'No Such Resource', message)

    def render(self, request):
        log.msg('Request %s: NoResource: %s, status %s' % (
            request._fluidDB_reqid, request.uri, self.code))
        request.setResponseCode(self.code)
        request.setHeader(buildHeader('Error-Class'), 'NoSuchResource')
        request.setHeader(buildHeader('Request-Id'), request._fluidDB_reqid)
        request.setHeader('content-type', 'text/html')
        return ("""<html>
        <head><title>%s - %s</title></head>
        <body><h1>%s</h1>
            <p>%s</p>
        </body></html>\n\n""" %
                (self.code, self.brief, self.brief, self.detail))


# FIXME: This is an ugly monkey patch to make Twisted send the proper headers
# when authorization fails. If you find a cleaner way of doing this please fix
# let me know. --ceronman.
from twisted.web._auth import wrapper


class WSFEUnauthorizedResource(wrapper.UnauthorizedResource):
    """Render a resource when the user is not authorized."""

    def render(self, request):
        result = super(WSFEUnauthorizedResource, self).render(request)

        origin = request.getHeader('Origin')
        if origin:
            request.setHeader('Access-Control-Allow-Origin', origin)
            request.setHeader('Access-Control-Allow-Credentials', 'true')
            if request.method == 'OPTIONS':
                request.setResponseCode(http.OK)
                request.setHeader('Allow', 'DELETE, GET, HEAD, POST, PUT')
                request.setHeader('Access-Control-Allow-Headers',
                                  'Accept, Authorization, Content-Type, '
                                  'X-FluidDB-Access-Token')
                request.setHeader('Access-Control-Max-Age',
                                  str(WSFEResource.ACCESS_CONTROL_MAX_AGE))
                request.setHeader('Access-Control-Allow-Methods',
                                  'DELETE, GET, HEAD, POST, PUT')
            else:
                request.setHeader('Access-Control-Expose-Headers',
                                  ('X-FluidDB-Access-Token, '
                                   'X-FluidDB-Action, '
                                   'X-FluidDB-Argument, '
                                   'X-FluidDB-Category, '
                                   'X-FluidDB-Error-Class, '
                                   'X-FluidDB-Fieldname, '
                                   'X-FluidDB-Message, '
                                   'X-FluidDB-Name, '
                                   'X-FluidDB-New-User, '
                                   'X-FluidDB-ObjectId, '
                                   'X-FluidDB-Path, '
                                   'X-FluidDB-Query, '
                                   'X-FluidDB-Rangetype, '
                                   'X-FluidDB-Type, '
                                   'X-FluidDB-Username'))
        return result


wrapper.UnauthorizedResource = WSFEUnauthorizedResource
