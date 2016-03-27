"""Delegator logic for the OAuth Echo process.

The Twitter API documentation has details about the OAuth Echo process that
you need to read to make sense of the logic in this module:

  https://dev.twitter.com/docs/auth/oauth/oauth-echo

There's a workflow diagram that's helpful when trying to understand the actors
and the sequence of events that occurs during the OAuth Echo process:

  http://scr.bi/bPUWSf

RFC 8549 has information about OAuth itself:

  http://tools.ietf.org/html/rfc5849

The logic in this module is related to the OAuth logic in the
L{SecureOAuthConsumerAPI} class.
"""

from json import loads

from twisted.web.http_headers import Headers

from fluiddb.model.oauth import OAuthConsumerAPI
from fluiddb.model.user import UserAPI, TwitterUserAPI, getUser
from fluiddb.util.agent import ResponseConsumer


# See endpoint docs for verify_credentials at
# https://dev.twitter.com/docs/api/1.1/get/account/verify_credentials
TWITTER_URL = 'https://api.twitter.com/1.1/account/verify_credentials.json'


class ServiceProviderError(Exception):
    """
    Raised if an error occurs while communicating with a service provider.
    """

    def __init__(self, code, payload):
        self.code = code
        self.payload = payload

    def __str__(self):
        return 'HTTP %s: %s' % (self.code, self.payload)


class ServiceProvider(object):
    """A service provider (for Twitter) in the OAuth Echo process.

    @param agent: The C{twisted.web.client.Agent} instance to use when making
        HTTP requests to the API endpoint.
    @param url: The URL to invoke when verifying credentials with the service
        provider.
    """

    def __init__(self, agent, url):
        self._agent = agent
        self._url = url

    def verifyCredentials(self, authentication):
        """Verify OAuch Echo credentials with Twitter.

        @param authentication: The C{X-Verify-Credentials-Authorization} value
            sent in the headers when an OAuth Echo request is made by a
            consumer.
        @return: A C{Deferred} that will fire a C{dict} with details about the
            Twitter user object sent in response to verifying credentials.  A
            L{ServiceProviderError} will be fired if the response doesn't
            include a C{200 OK} HTTP status code.
        """

        def unpackResponse(payload, response):
            """
            Unpack the user details response sent by the L{ServiceProvider}.
            """
            if response.code != 200:
                raise ServiceProviderError(response.code, payload)
            return loads(payload)

        def consumeResponse(response):
            """Read HTTP response data from the L{ServiceProvider}."""
            consumer = ResponseConsumer()
            consumer.deferred.addCallback(unpackResponse, response)
            response.deliverBody(consumer)
            return consumer.deferred

        headers = Headers({'Authorization': [authentication]})
        deferred = self._agent.request('GET', self._url, headers)
        return deferred.addCallback(consumeResponse)


class Delegator(object):
    """A delegator (for Fluidinfo) in the OAuth Echo process.

    @param transact: The L{Transact} instance to use when interacting with the
        database.
    """

    def __init__(self, transact):
        self._transact = transact

    def getUser(self, consumerUsername, provider, authorization):
        """Get user data for a consumer's credentials from a service provider.

        If the provider verifies the credentials, but there is no matching
        L{User}, a L{User} and linked L{TwitterUser} will be created
        automatically.

        @param consumerUsername: The L{User.username} of the consumer making
            an OAuth Echo request.
        @param provider: A L{ServiceProvider} instance.
        @param authorization: The C{X-Verify-Credentials-Authorization} value
            sent in the headers when an OAuth Echo request is made by a
            consumer.
        @raise DuplicateUserError: Raised by the C{Deferred} if a L{User} with
            the same name as a Twitter user exists but is not associated with
            it.
        @raise ServiceProviderError: Raised by the C{Deferred} if credentials
            cannot be verified.  Other exceptions from Twisted, related to a
            failing connection, may also be fired.
        @return: A C{Deferred} that will fire with a C{dict} matching the
            following format::

              {'username': <username>,
               'new-user': <bool>,
               'access-token': <token>,
               'renewal-token': <token>,
               'uid': <uid>,
               'data': <user>}

            The consumer can use C{<access-token>}, a C{str}, to make OAuth
            calls to Fluidinfo.  <user> is a C{dict} containing the user
            object returned by the service provider (ie, Twitter).
        """

        def run(userData):
            """
            Handle user data sent by the L{ServiceProvider} when credentials
            are successfully verified.
            """
            uid = userData['id']
            user = TwitterUserAPI().get(uid)
            if user is None:
                newUser = True
                username = userData['screen_name'].lower()
                fullname = userData['name']
                UserAPI().create([(username, None, fullname, None)])
                TwitterUserAPI().create(username, uid)
                user = TwitterUserAPI().get(uid)
            else:
                newUser = False

            # FIXME The calls to encrypt the tokens below aren't tested very
            # well.
            consumer = getUser(consumerUsername)
            accessToken = OAuthConsumerAPI().getAccessToken(consumer, user)
            renewalToken = OAuthConsumerAPI().getRenewalToken(consumer, user)
            return {'username': user.username,
                    'new-user': newUser,
                    'missing-password': (user.passwordHash == '!'),
                    'access-token': accessToken.encrypt(),
                    'renewal-token': renewalToken.encrypt(),
                    'uid': uid,
                    'data': userData}

        deferred = provider.verifyCredentials(authorization)
        return deferred.addCallback(lambda data: self._transact.run(run, data))
