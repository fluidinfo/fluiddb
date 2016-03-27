from base64 import b64encode
from json import dumps
import logging

from twisted.internet import reactor
from twisted.web.client import Agent
from twisted.web.http import (
    BAD_REQUEST, CONFLICT, INTERNAL_SERVER_ERROR, OK, SERVICE_UNAVAILABLE)
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET

from fluiddb.data.exceptions import DuplicateUserError
from fluiddb.security.oauthecho import Delegator, ServiceProvider, TWITTER_URL


class OAuthEchoRequestError(Exception):
    """Raised when an OAuth Echo request is missing required information.

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


class OAuthEchoResource(Resource):
    """Handler for the C{/oauthecho} API endpoint.

    @param session: The L{FluidinfoSession} instance to use while handling a
        request.
    @param agent: Optionally, the C{Agent} instance to use with a
        L{ServiceProvider} when verifying credentials.  Default is an C{Agent}
        instance instantiated with the global C{Reactor}.
    """

    isLeaf = True

    def __init__(self, session, agent=None):
        self._session = session
        self._agent = agent or Agent(reactor)

    def render_GET(self, request):
        """Handle an OAuth Echo request.

        Call the original service provider's endpoint to verify credentials
        (at least that's what Twitter calls it) and return the result, along
        with appropriate Fluidinfo-specific headers.  The client invoking this
        method is the consumer, Fluidinfo is the delegator and Twitter is the
        service provider, in the OAuth Echo process.

        A C{deferred} attribute is set on the instance for testing purposes.
        It will fire with the result of a call to L{Delegator.getUser}.

        @param request: The HTTP request.
        @return: Either an empty string (in the case of an error), or
            C{NOT_DONE_YET} to indicate processing is ongoing.
        """

        def succeeded(result):
            """
            Handle successful credentials verification with the
            L{ServiceProvider}.
            """
            # FIXME UTF-8 encode and base64 the username.
            username = result['username']
            if result['new-user']:
                request.setHeader('X-FluidDB-New-User', 'true')
            if result['missing-password']:
                request.setHeader('X-FluidDB-Missing-Password', 'true')
            encodedUsername = b64encode(username.encode('utf-8'))
            request.setHeader('X-FluidDB-Username', encodedUsername)
            request.setHeader('X-FluidDB-Access-Token', result['access-token'])
            request.setHeader('X-FluidDB-Renewal-Token',
                              result['renewal-token'])
            request.write(dumps(result['data']))
            request.setResponseCode(OK)
            request.finish()
            return result

        def failed(failure):
            """
            Handle a failure that occurred while attempting to verify
            credentials with the L{ServiceProvider}.
            """
            if failure.check(DuplicateUserError):
                logging.warning('Could not authenticate duplicate user:')
                logging.exception(failure.value)
                [username] = list(failure.value.usernames)
                encodedUsername = b64encode(username.encode('utf-8'))
                request.setHeader('X-FluidDB-Username', encodedUsername)
                request.setHeader('X-FluidDB-Error-Class', 'UsernameConflict')
                request.setResponseCode(CONFLICT)
            else:
                logging.warning('Could not complete OAuth Echo request:')
                logging.exception(failure.value)
                request.setResponseCode(SERVICE_UNAVAILABLE)
            request.setHeader('X-FluidDB-Request-Id', self._session.id)
            request.finish()

        def crashed(failure):
            """
            Handle an unexpected failure that occurred while attempting to
            handle this request.
            """
            logging.error('Unexpected error handling OAuth Echo request:')
            logging.exception(failure.value)
            request.setResponseCode(INTERNAL_SERVER_ERROR)
            request.finish()

        try:
            url, authorization = self._getParameters(request)
        except OAuthEchoRequestError as error:
            request.setResponseCode(BAD_REQUEST)
            request.setHeader('X-FluidDB-Request-Id', self._session.id)
            request.setHeader('X-FluidDB-Error-Class', error.errorClass)
            if error.badHeader:
                request.setHeader('X-FluidDB-Header', error.badHeader)
            return ''
        else:
            consumerUsername = self._session.auth.username
            provider = ServiceProvider(self._agent, url)
            delegator = Delegator(self._session.transact)
            self.deferred = delegator.getUser(consumerUsername, provider,
                                              authorization)
            self.deferred.addCallbacks(succeeded, failed)
            self.deferred.addErrback(crashed)
            return NOT_DONE_YET

    def _getParameters(self, request):
        """Unpack OAuth Echo parameters from the request.

        The URL and the authorization string needed to verify credentials are
        extracted from the request and returned.

        @param request: A C{Request} containing OAuth Echo request headers.
        @raise OAuthEchoRequestError: Raised if the C{X-Auth-Service-Provider}
            or C{X-Verify-Credentials-Authorization} headers are not
            available, or if they contain bad or unusable information.
        @return: A C{(url, authorization)} 2-tuple.
        """
        url = request.getHeader('X-Auth-Service-Provider')
        if not url:
            raise OAuthEchoRequestError('MissingHeader',
                                        'X-Auth-Service-Provider')
        elif url != TWITTER_URL:
            raise OAuthEchoRequestError('UnknownServiceProvider')

        authorization = request.getHeader('X-Verify-Credentials-Authorization')
        if not authorization:
            raise OAuthEchoRequestError('MissingHeader',
                                        'X-Verify-Credentials-Authorization')
        elif not authorization.startswith('OAuth'):
            raise OAuthEchoRequestError('BadHeader',
                                        'X-Verify-Credentials-Authorization')

        return url, authorization
