from base64 import b64encode
from zope.interface.verify import verifyObject

from twisted.cred.error import LoginFailed
from twisted.web.iweb import ICredentialFactory
from twisted.web.http_headers import Headers

from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.doubles import FakeRequest
from fluiddb.util.oauth2_credentials import (
    OAuth2Credentials, OAuth2CredentialFactory, IOAuth2Credentials)


class OAuth2CredentialsTest(object):

    def testAttributes(self):
        """
        The arguments passed to C{OAuth2Credentials} should be
        available as atttributes of the instance.
        """
        credentials = OAuth2Credentials('user', 'pass', 'token')
        self.assertEqual('user', credentials.consumerKey)
        self.assertEqual('pass', credentials.consumerPassword)
        self.assertEqual('token', credentials.token)

    def testVerifySignature(self):
        """
        C{OAuth2Credentials}.verifySignature must return C{True}.
        """
        credentials = OAuth2Credentials('user', 'pass', 'token')
        self.assertEqual(True, credentials.verifySignature())


class OAuth2CredentialFactoryTest(FluidinfoTestCase):

    def setUp(self):
        """Common set-up for the tests in this class."""
        super(OAuth2CredentialFactoryTest, self).setUp()
        self.realm = 'Example'
        self.credentialFactory = OAuth2CredentialFactory(self.realm)

    def testGetChallenge(self):
        """The challenge must include a correct 'realm' key."""
        self.assertEqual({'realm': self.realm},
                         self.credentialFactory.getChallenge(request=None))

    def testInterface(self):
        """L{BasicCredentialFactory} must implement L{ICredentialFactory}."""
        self.assertTrue(verifyObject(ICredentialFactory,
                                     self.credentialFactory))

    def testRequestWithoutHeader(self):
        """
        Non-HTTPS requests (with no C{X-Forwarded-Protocol} header) raise a
        L{LoginFailed} error.
        """
        request = FakeRequest(
            path='/', uri='https://example.org/xx?arg=1',
            headers=Headers({'X-FluidDB-Access-Token': ['xxx']}))
        response = b64encode('anon:anon')
        self.assertRaises(LoginFailed, self.credentialFactory.decode,
                          response, request)

    def testRequestWithHeader(self):
        """
        Non-HTTPS requests (with an C{X-Forwarded-Protocol} header that does
        not contain 'https') raise a L{LoginFailed} error.
        """
        request = FakeRequest(
            path='/', uri='https://example.org/xx?arg=1',
            headers=Headers({'X-FluidDB-Access-Token': ['xxx'],
                             'X-Forwarded-Protocol': ['http']}))
        response = b64encode('anon:anon')
        self.assertRaises(LoginFailed, self.credentialFactory.decode,
                          response, request)

    def testRequestWithoutHeaderInDevelopmentMode(self):
        """
        Non-HTTPS requests (with no C{X-Forwarded-Protocol} header) don't
        raise a L{LoginFailed} error when development mode is enabled.
        """
        request = FakeRequest(
            path='/', uri='https://example.org/xx?arg=1',
            headers=Headers({'X-FluidDB-Access-Token': ['xxx']}))
        response = b64encode('anon:anon')
        factory = OAuth2CredentialFactory(self.realm, development=True)
        credentials = factory.decode(response, request)
        self.assertTrue(IOAuth2Credentials.providedBy(credentials))
        self.assertEqual(u'anon', credentials.consumerKey)
        self.assertEqual(u'anon', credentials.consumerPassword)
        self.assertEqual('xxx', credentials.token)

    def testRequestWithHeaderInDevelopmentMode(self):
        """
        Non-HTTPS requests (with an C{X-Forwarded-Protocol} header that does
        not contain 'https') don't raise a L{LoginFailed} error when
        development mode is enabled.
        """
        request = FakeRequest(
            path='/', uri='https://example.org/xx?arg=1',
            headers=Headers({'X-FluidDB-Access-Token': ['xxx'],
                             'X-Forwarded-Protocol': ['http']}))
        response = b64encode('anon:anon')
        factory = OAuth2CredentialFactory(self.realm, development=True)
        credentials = factory.decode(response, request)
        self.assertTrue(IOAuth2Credentials.providedBy(credentials))
        self.assertEqual(u'anon', credentials.consumerKey)
        self.assertEqual(u'anon', credentials.consumerPassword)
        self.assertEqual('xxx', credentials.token)

    def testDecodeWithUnsplittableBasicAuthCredentials(self):
        """
        L{OAuth2CredentialFactory.decode} raises L{LoginFailed} if passed
        Basic Auth credentials that cannot be split on ':'.
        """
        response = 'unsplittable'
        request = FakeRequest(
            path='/', uri='https://example.org/xx?arg=1',
            headers=Headers({'X-FluidDB-Access-Token': ['xxx'],
                             'X-Forwarded-Protocol': ['https']}))
        self.assertRaises(
            LoginFailed, self.credentialFactory.decode, response, request)

    def testDecode(self):
        """
        A successful call to L{OAuthCredentialFactory.decode} turns a response
        and request into an L{IOAuth2Credentials} providing object with
        consumer key, consumer password, and token attributes.
        """
        response = b64encode('user123:password456')
        request = FakeRequest(
            path='/', uri='https://example.org/xx?arg=1',
            headers=Headers({'X-FluidDB-Access-Token': ['xxx'],
                             'X-Forwarded-Protocol': ['https']}))
        creds = self.credentialFactory.decode(response, request)
        self.assertTrue(IOAuth2Credentials.providedBy(creds))
        self.assertEqual(u'user123', creds.consumerKey)
        self.assertEqual(u'password456', creds.consumerPassword)
        self.assertEqual('xxx', creds.token)

    def testDecodeEmtpyResponseToAnon(self):
        """
        Ensure decode returns credentials for the anon user when the response
        is empty.
        """
        response = ''
        request = FakeRequest(
            path='/', uri='https://example.org/xx?arg=1',
            headers=Headers({'X-FluidDB-Access-Token': ['xxx'],
                             'X-Forwarded-Protocol': ['https']}))
        creds = self.credentialFactory.decode(response, request)
        self.assertEqual(u'anon', creds.consumerKey)
        self.assertEqual(None, creds.consumerPassword)
