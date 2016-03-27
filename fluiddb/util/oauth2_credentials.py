import binascii

from twisted.cred.credentials import ICredentials
from twisted.cred.error import LoginFailed
from twisted.web.iweb import ICredentialFactory

from zope.interface import implements


class IOAuth2Credentials(ICredentials):
    """I encapsulate an OAuth authentication request.

    This credential is used when an OAuth token is received in an
    X-FluidDB-Access-Token header from the party requesting authentication.
    """

    def verifySignature(secret):
        """Validate these credentials against the correct shared secret.

        @param secret: A C{str} with the shared OAuth secret.
        @return: C{True} if the credentials held in self match the passed
            secret, C{False} if they do not.
        """


class OAuth2Credentials(object):
    """Encapsulate an OAuth2 authentication request.

    This credential is used for OAuth2 authentication, which is used when
    an OAuth token is given in an X-FluidDB-Access-Token request header.

    @param consumerKey: The C{unicode} Fluidinfo username of the consumer.
    @param consumerPassword: The C{unicode} Fluidinfo password of the consumer.
    @param token: A C{str} token passed in the C{X-FluidDB-Access-Token}
        header which will contain the username of user on whose behalf the
        OAuth request is being made.
    """

    implements(IOAuth2Credentials)

    def __init__(self, consumerKey, consumerPassword, token):
        self.consumerKey = consumerKey
        self.consumerPassword = consumerPassword
        self.token = token

    def verifySignature(self, secret):
        """Check an OAuth signature.

        OAuth2 does not use signatures. This method is provided to be
        compatible with C{fluiddb.model.oauth.OAuthConsumerAPI.authenticate}.

        @param secret: A C{str} consumer secret. Unused.
        @return: a C{bool} to indicate signature verification success.
        """
        return True


class OAuth2CredentialFactory(object):
    """
    Credential factory for OAuth2.  Add this factory to a L{Portal} to
    guard resources with OAuth2.

    @param authenticationRealm: The name of the authentication realm.
    @param development: Optionally, a flag to indicate that the system is
        running in development mode.  When C{True} checks to ensure that only
        HTTPS connections are allowed are disabled.  Default is C{False}.
    """

    implements(ICredentialFactory)
    scheme = 'oauth2'

    def __init__(self, authenticationRealm, development=None):
        self.authenticationRealm = authenticationRealm
        self.development = development

    def getChallenge(self, request):
        """
        Return a challenge with the HTTP authentication realm with which
        this factory was created.

        @param request: The incoming HTTP request.
        @return: A C{dict} indicating our realm.
        """
        return {'realm': self.authenticationRealm}

    def decode(self, response, request):
        """Parse the Authorization header and also extract the OAuth token.

        The authorization response must contain a base64-encoded,
        colon-separated username and password. The response parsing code
        below is from C{twisted.web._auth.basic.BasicCredentialFactory} (as
        opposed to using the more modern base64 module). We also look for
        the C{X-FluidDB-Access-Token} header.  OAuth2 requests must be made
        over a secure transport.

        @param response: The value of the HTTP Authorization header. If
            this is empty this is an anonymous 'anon' user request.
        @param request: The incoming HTTP request.
        @raise LoginFailed: If the Authorization header is not valid
            base64, or if the Authorization header cannot be split into 2
            pieces by ':', or if the request is not via https, or if the
            C{X-FluidDB-Access-Token} header is not present or empty.
        @return: an L{OAuth2Credentials} instance.
        """
        # Make sure the request is via HTTPS. We can only tell that by
        # looking for the header NGinx sets for us when it processes HTTPS
        # requests.

        if not self.development:
            secureHeader = request.getHeader('X-Forwarded-Protocol')
            if secureHeader != 'https':
                raise LoginFailed('OAuth2 requests must use https.')

        if response:
            try:
                credentials = binascii.a2b_base64(response + '===')
            except binascii.Error:
                raise LoginFailed('Non-base64 credentials.')

            try:
                username, password = credentials.split(':', 1)
            except ValueError:
                raise LoginFailed('Credentials could not be split on colon.')

            try:
                username = username.decode('utf-8')
                password = password.decode('utf-8')
            except UnicodeDecodeError:
                raise LoginFailed('Invalid UTF-8 in credentials.')
        else:
            username = u'anon'
            password = None

        token = request.getAllHeaders().get('x-fluiddb-access-token')
        if not token:
            raise LoginFailed('X-FluidDB-Access-Token header missing/empty.')

        return OAuth2Credentials(username, password, token)
