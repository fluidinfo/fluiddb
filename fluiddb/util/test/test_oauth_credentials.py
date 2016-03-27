from zope.interface.verify import verifyObject

from twisted.cred.error import LoginFailed
from twisted.internet.defer import inlineCallbacks
from twisted.web.iweb import ICredentialFactory

from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.doubles import FakeRequest
from fluiddb.util.oauth_credentials import (
    OAuthCredentialFactory, IOAuthCredentials)


class OAuthCredentialFactoryTest(FluidinfoTestCase):

    def setUp(self):
        super(OAuthCredentialFactoryTest, self).setUp()
        self.request = FakeRequest(path='/',
                                   uri='http://example.org/endpoint?arg1=foo')
        self.request.method = 'GET'
        self.realm = 'Example'
        self.consumerKey = '9djdj82h48djs9d2'
        self.token = 'kkk9d7dh3k39sjv7'
        self.signatureMethod = 'HMAC-SHA1'
        self.timestamp = '137131201'
        self.nonce = '7d8f3e4a'
        self.signature = 'h26XUyh8/zYpfmuWQVd3TeRilnM%3D'
        self.credentialFactory = OAuthCredentialFactory(self.realm)
        self.consumerSecret = 'consumer_secret'
        self.tokenSecret = 'token_secret'

    def testInterface(self):
        """
        L{BasicCredentialFactory} implements L{ICredentialFactory}.
        """
        self.assertTrue(
            verifyObject(ICredentialFactory, self.credentialFactory))

    @inlineCallbacks
    def testDecode(self):
        """
        L{OAuthCredentialFactory.decode} turns an OAuth authorization header
        response into an L{OAuthCredentials} object.
        """
        response = \
            """
            realm="%s", oauth_consumer_key="%s", oauth_token="%s",
            oauth_signature_method="%s", oauth_timestamp="%s",
            oauth_nonce="%s", oauth_signature="%s"
            """ % (self.realm, self.consumerKey, self.token,
                   self.signatureMethod, self.timestamp, self.nonce,
                   self.signature)

        creds = self.credentialFactory.decode(response, self.request)
        self.assertTrue(IOAuthCredentials.providedBy(creds))
        self.assertTrue(creds.verifySignature(self.consumerSecret))
        result = yield creds.verifySignature(self.consumerSecret + 'wrong')
        self.assertFalse(result)

    def testDecodeWithInvalidOAuthFormat(self):
        """
        L{OAuthCredentialFactory.decode} raises L{LoginFailed} if passed
        a response which doesn't match the OAuth format for requests.
        """
        response = 'x'
        self.assertRaises(
            LoginFailed, self.credentialFactory.decode, response, self.request)

    def testDecodeWithoutRequiredOAuthFields(self):
        """
        L{OAuthCredentialFactory.decode} raises L{LoginFailed} if passed
        a response which lacks any of the seven required OAuth fields.
        """
        response = \
            """
            realm="%s", oauth_token="%s",
            oauth_signature_method="%s", oauth_timestamp="%s",
            oauth_nonce="%s", oauth_signature="%s"
            """ % (self.realm, self.token, self.signatureMethod,
                   self.timestamp, self.nonce, self.signature)

        self.assertRaises(
            LoginFailed, self.credentialFactory.decode, response, self.request)

    def testDecodeWithoutRequiredOAuthFieldsAndVersionPresent(self):
        """
        L{OAuthCredentialFactory.decode} raises L{LoginFailed} if passed
        a response which lacks any of the seven required OAuth fields,
        even if the version is included, which is optional.
        """
        response = \
            """
            realm="%s", oauth_token="%s",
            oauth_signature_method="%s", oauth_timestamp="%s",
            oauth_nonce="%s", oauth_signature="%s", oauth_version="1.0"
            """ % (self.realm, self.token, self.signatureMethod,
                   self.timestamp, self.nonce, self.signature)

        self.assertRaises(
            LoginFailed, self.credentialFactory.decode, response, self.request)

    def testDecodeWithInvalidSignatureMethod(self):
        """
        L{OAuthCredentialFactory.verifySignature} raises L{NotImplementedError}
        if a signature method different from HMAC-SHA1 is passed.
        """
        response = \
            """
            realm="%s", oauth_consumer_key="%s", oauth_token="%s",
            oauth_signature_method="BOGUS-ALGORITHM", oauth_timestamp="%s",
            oauth_nonce="%s", oauth_signature="%s"
            """ % (self.realm, self.consumerKey, self.token,
                   self.timestamp, self.nonce, self.signature)

        creds = self.credentialFactory.decode(response, self.request)
        self.assertTrue(IOAuthCredentials.providedBy(creds))
        self.assertRaises(
            NotImplementedError, creds.verifySignature, self.consumerSecret)
