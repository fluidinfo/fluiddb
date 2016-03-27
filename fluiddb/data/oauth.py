from random import sample

from storm.locals import Storm, DateTime, Int, RawStr, Reference, AutoReload

from fluiddb.data.store import getMainStore
from fluiddb.data.user import User, ALPHABET


class OAuthConsumer(Storm):
    """A L{User} that interacts with Fluidinfo using OAuth.

    @param userID: The L{User.id} associated with the key and secret.
    @param secret: The C{str} consumer secret.
    """

    __storm_table__ = 'oauth_consumers'

    userID = Int('user_id', primary=True, allow_none=False)
    secret = RawStr('secret', allow_none=False)
    creationTime = DateTime('creation_time', default=AutoReload)

    user = Reference(userID, 'User.id')

    def __init__(self, userID, secret):
        self.userID = userID
        self.secret = secret


def createOAuthConsumer(user, secret=None):
    """Create a new L{OAuthConsumer} with a randomly generated secret.

    A 16-character secret is generated randomly, if one isn't explicitly
    provided.  It's combined with the Fluidinfo C{access-secret} to generate
    the final 32-character key that is used to generate a
    C{fluiddb.util.minitoken} token.

    @param user: The L{User} to associated with the L{OAuthConsumer}.
    @param secret: Optionally, a C{str} with a secret. If not passed, a random
        secret is generated.
    @return: A new L{OAuthConsumer} instance persisted in the main store.
    """
    store = getMainStore()
    if secret is None:
        secret = ''.join(sample(ALPHABET, 16))
    elif len(secret) != 16:
        raise ValueError('Consumer secret must be exactly 16 characters in '
                         'length.')
    return store.add(OAuthConsumer(user.id, secret))


def getOAuthConsumers(userIDs=None):
    """Get C{(User, OAuthConsumer)} 2-tuples matching specified L{User.id}s.

    @param userIDs: Optionally, a sequence of L{User.id}s to filter the
        results with.
    @return: A C{ResultSet} with matching C{(User, OAuthConsumer)} results.
    """
    store = getMainStore()
    where = []

    if userIDs:
        where.append(OAuthConsumer.userID.is_in(userIDs))
    return store.find((User, OAuthConsumer),
                      OAuthConsumer.userID == User.id,
                      *where)
