from oauth2 import Consumer, Request, SignatureMethod_HMAC_SHA1

from urllib import unquote

from twisted.cred.credentials import ICredentials
from twisted.cred.error import LoginFailed
from twisted.web.iweb import ICredentialFactory

from zope.interface import implements


class IOAuthCredentials(ICredentials):
    """I encapsulate an OAuth authentication request.

    This credential is used when an OAuth signature is received from the party
    requesting authentication. CredentialCheckers which check this kind of
    credential must store the shared OAuth secret so that they can be verified
    according to https://tools.ietf.org/html/rfc5849#section-3.2
    """

    def verifySignature(secret):
        """Validate these credentials against the correct shared secret.

        @param secret: A C{str} with the shared OAuth secret.
        @return: C{True} if the credentials represented by this object match
            the given secret, C{False} if they do not.
        """


class OAuthCredentials(object):
    """See L{IOAuthCredentials}."""

    implements(IOAuthCredentials)

    # This is probably too indirect. The OAuth parameters don't use
    # camel case, but our coding style does
    oauthMapping = {
        'realm': 'realm',
        'oauth_consumer_key': 'consumerKey',
        'oauth_token': 'token',
        'oauth_signature_method': 'signatureMethod',
        'oauth_signature': 'signature',
        'oauth_timestamp': 'timestamp',
        'oauth_nonce': 'nonce',
        'oauth_version': 'version'
    }

    def __init__(self, realm, consumerKey, token, signatureMethod, signature,
                 timestamp, nonce, method, url, headers, arguments,
                 version=None):
        # OAuth headers
        self.realm = realm
        self.consumerKey = consumerKey
        self.token = token
        self.signatureMethod = signatureMethod
        self.signature = signature
        self.timestamp = timestamp
        self.nonce = nonce
        self.version = version

        # Request information
        self.method = method
        self.url = url

        # Request parameters
        self.headers = headers

        # Request URI paramters
        self.arguments = arguments

    def verifySignature(self, secret):
        """See L{IOAuthCredentials#verifySignature}."""
        consumer = Consumer(key=self.consumerKey, secret=secret)
        oauthRequest = Request.from_request(
            self.method, self.url, headers=self.headers,
            query_string=self.arguments)

        # verify the request has been oauth authorized, we only support
        # HMAC-SHA1, reject OAuth signatures if they use a different method
        if self.signatureMethod != 'HMAC-SHA1':
            raise NotImplementedError(
                'Unknown signature method: %s' % self.signatureMethod)
        signatureMethod = SignatureMethod_HMAC_SHA1()
        result = signatureMethod.check(oauthRequest, consumer, None,
                                       self.signature)
        return result


class OAuthCredentialFactory(object):
    """
    Credential Factory for OAuth authorization. Add this factory to a L{Portal}
    to guard resources with OAuth.
    """
    implements(ICredentialFactory)

    scheme = 'oauth'

    def __init__(self, authenticationRealm):
        self.authenticationRealm = authenticationRealm

    def getChallenge(self, request):
        """
        Return a challenge including the HTTP authentication realm with which
        this factory was created.

        @param request: The incoming HTTP request.
        """
        return {'realm': self.authenticationRealm}

    def decode(self, response, request):
        """
        Parse the Authorization header to retrieve the OAuth components.

        @param response: The value of the HTTP Authorization header.
        @param request: The incoming HTTP request.

        @return: an L{OAuthCredentials}.
        @raise L{LoginFailed}: if the format of the Authorization header
            is not valid.
        """
        creds = response.split(',')
        # There are seven required OAuth headers, only version is optional
        if len(creds) >= 7:
            parameters = {}
            for cred in creds:
                parameter, value = cred.split('=')
                parameter = parameter.strip(' \r\n"')
                value = value.strip(' \r\n"')

                key = OAuthCredentials.oauthMapping.get(parameter)
                if key is None:
                    raise LoginFailed('Invalid credentials')
                parameters[key] = unquote(value)

            # Apart from the OAuth header, we also need the URL and the method
            # of the incoming request
            parameters['url'] = request.uri
            parameters['method'] = request.method
            parameters['headers'] = request.getAllHeaders()
            parameters['version'] = parameters.get('version')

            arguments = {}
            for key, value in request.args.iteritems():
                arguments[key.lower()] = value[-1]
            parameters['arguments'] = arguments

            # Check that all parameters are present, otherwise raise an
            # exception
            if len(parameters) == 12:
                return OAuthCredentials(**parameters)
        raise LoginFailed('Invalid credentials')
