"""OAuth 2.0 token renewal logic.

OAuth 2.0 provides a mechanism for applications to renew access tokens.  When
an L{OAuthConsumer} (using OAuth Echo, see L{fluiddb.security.oauthecho})
authenticates a L{User} they receive an L{OAuthAccessToken} and an
L{OAuthRenewalToken}.  The L{OAuthAccessToken} can be used to make requests on
behalf of the L{User}, but only for a limited period of time.  When it
expires, the L{OAuthRenewalToken} can be used to generate a new access token.

The OAuth 2.0 (draft) specification provides some details about this process:

  http://tools.ietf.org/html/draft-ietf-oauth-v2-22#section-1.4

In our specific case, a new L{OAuthRenewalToken} is generated each time a new
L{OAuthAccessToken} is requested.  A renewal token is valid for a longer
period of time than an access token, so this isn't strictly necessary, but it
means that a user using C{fluidinfo.com} always has a renewal token that was
created the last time they accessed the site.  This means that users that use
C{fluidinfo.com} on a regular basis won't be forced to authenticate unless
they don't use it for the period within which a renewal token is valid.

The logic in this module is related to the OAuth Echo logic in the
L{Delegator} class.
"""

from fluiddb.cache.user import cachingGetUser
from fluiddb.model.exceptions import UnknownConsumerError
from fluiddb.model.oauth import OAuthConsumerAPI, OAuthRenewalToken
from fluiddb.security.exceptions import InvalidOAuthTokenError


class SecureOAuthConsumerAPI(object):
    """The public API for L{OAuthConsumer}s in the security layer.

    Note that, unlike other security/model API classes, the interface provided
    by this class doesn't exactly match the one provided by
    L{OAuthConsumerAPI}.  This is because some functionality only belongs in
    the model layer, and also because one of the functions this class provides
    is converting L{OAuthAccessToken}s and L{OAuthRenewalToken}s to/from
    encrypted blobs, so that the model layer can work with stateful objects
    and not be concerned with encryption.
    """

    def renewToken(self, consumerUsername, encryptedToken):
        """Use an L{OAuthRenewalToken} to generate a new L{OAuthAccessToken}.

        @param encryptedToken: The encrypted L{OAuthRenewalToken} to use to
            generate a new L{OAuthAccessToken}.
        @raise InvalidOAuthTokenError: Raised if the encrypted
            L{OAuthRenewalToken} can't be decrypted.
        @raise UnknownConsumerError: Raised if C{consumerUser} doesn't have a
            matching L{OAuthConsumer} in the system.
        @raise UnknownUserError: Raised if the L{User} the token provides
            access on behalf of doesn't exist.
        @return: A C{(OAuthRenewalToken, OAuthAccessToken)} 2-tuple.
        """
        consumer = cachingGetUser(consumerUsername)
        if consumer is None:
            raise UnknownConsumerError(
                'Unknown consumer: %s' % consumerUsername)
        try:
            token = OAuthRenewalToken.decrypt(consumer, encryptedToken)
        except ValueError:
            raise InvalidOAuthTokenError("Couldn't decrypt renewal token.")
        renewalToken, accessToken = OAuthConsumerAPI().renewToken(token)
        return renewalToken.encrypt(), accessToken.encrypt()
