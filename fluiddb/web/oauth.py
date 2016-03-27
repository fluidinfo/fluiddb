import logging

from twisted.web.http import (
    BAD_REQUEST, INTERNAL_SERVER_ERROR, OK, UNAUTHORIZED)
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET

from fluiddb.model.exceptions import (
    ExpiredOAuthTokenError, UnknownConsumerError)
from fluiddb.security.exceptions import InvalidOAuthTokenError
from fluiddb.security.oauth import SecureOAuthConsumerAPI


# FIXME This class is a copy of OAuthEchoRequestError.  It'd be nice to unify
# them, since they both perform the same function. -jkakar
class OAuthTokenRequestError(Exception):
    """
    Raised when an OAuth token renewal request is missing required information.

    @param errorClass: A C{str} name for the type of request error that has
        been detected.
    @param badHeader: Optionally, the C{str} name of the relevant header.
    """

    def __init__(self, errorClass, badHeader=None):
        self.errorClass = errorClass
        self.badHeader = badHeader

    def __str__(self):
        message = self.errorClass
        if self.badHeader:
            message += ' with bad header %s' % self.badHeader
        return message


class RenewOAuthTokenResource(Resource):
    """Handler for the C{/renew-oauth-token} API endpoint.

    @param session: The L{FluidinfoSession} instance to use while handling a
        request.
    """

    isLeaf = True

    def __init__(self, session):
        self._session = session

    def render_GET(self, request):
        """Handle an OAuth token renewal request.

        @param request: The HTTP request.
        @return: Either an empty string (in the case of an error), or
            C{NOT_DONE_YET} to indicate processing is ongoing.
        """
        consumerUsername = self._session.auth.username

        def succeeded(result):
            """Handle successful token renewal."""
            renewalToken, accessToken = result
            request.setHeader('X-FluidDB-Access-Token', accessToken)
            request.setHeader('X-FluidDB-Renewal-Token', renewalToken)
            request.setResponseCode(OK)
            request.finish()
            return result

        def failed(failure):
            """
            Handle a failure that occurred while attempting to verify
            credentials with the L{ServiceProvider}.
            """
            if failure.check(UnknownConsumerError):
                logging.warning('Received renewal request for unknown '
                                'consumer:')
                logging.exception(failure.value)
                request.setHeader('X-FluidDB-Username', consumerUsername)
                request.setHeader('X-FluidDB-Error-Class', 'UnknownConsumer')
                request.setResponseCode(BAD_REQUEST)
            elif failure.check(ExpiredOAuthTokenError):
                logging.warning('Received renewal request with expired token:')
                logging.exception(failure.value)
                request.setHeader('X-FluidDB-Username', consumerUsername)
                request.setHeader('X-FluidDB-Error-Class',
                                  'ExpiredOAuth2RenewalToken')
                request.setResponseCode(UNAUTHORIZED)
            elif failure.check(InvalidOAuthTokenError):
                logging.warning('Received renewal request with invalid token:')
                logging.exception(failure.value)
                request.setHeader('X-FluidDB-Username', consumerUsername)
                request.setHeader('X-FluidDB-Error-Class',
                                  'InvalidOAuth2RenewalToken')
                request.setResponseCode(BAD_REQUEST)
            else:
                logging.warning('Could not complete OAuth renewal request:')
                logging.exception(failure.value)
                request.setResponseCode(INTERNAL_SERVER_ERROR)
            request.setHeader('X-FluidDB-Request-Id', self._session.id)
            request.finish()

        def crashed(failure):
            """
            Handle an unexpected failure that occurred while attempting to
            handle this request.
            """
            logging.error('Unexpected error handling OAuth token renewal '
                          'request:')
            logging.exception(failure.value)
            request.setResponseCode(INTERNAL_SERVER_ERROR)
            request.finish()

        try:
            renewalToken = self._getParameters(request)
        except OAuthTokenRequestError as error:
            request.setResponseCode(BAD_REQUEST)
            request.setHeader('X-FluidDB-Request-Id', self._session.id)
            request.setHeader('X-FluidDB-Error-Class', error.errorClass)
            if error.badHeader:
                request.setHeader('X-FluidDB-Header', error.badHeader)
            return ''

        def renewToken():
            """Get a new access token using the provided renewal token."""
            return SecureOAuthConsumerAPI().renewToken(consumerUsername,
                                                       renewalToken)

        self.deferred = self._session.transact.run(renewToken)
        self.deferred.addCallbacks(succeeded, failed)
        self.deferred.addErrback(crashed)
        return NOT_DONE_YET

    def _getParameters(self, request):
        """Unpack OAuth token parameters from the request.

        @param request: A C{Request} containing OAuth Echo request headers.
        @raise OAuthTokenRequestError: Raised if the C{X-FluidDB-Renewal-Token}
            headers is not available.
        @return: An encrypted L{OAuthRenewalToken} blob.
        """
        token = request.getHeader('X-FluidDB-Renewal-Token')
        if not token:
            raise OAuthTokenRequestError('MissingHeader',
                                         'X-FluidDB-Renewal-Token')
        return token
