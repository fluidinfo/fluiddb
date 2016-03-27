from random import sample
from string import ascii_letters, digits
import sys

from fluiddb.data.oauth import (
    OAuthConsumer, createOAuthConsumer, getOAuthConsumers)
from fluiddb.data.user import User, createUser
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import DatabaseResource


class CreateOAuthConsumerTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testCreateOAuthConsumer(self):
        """
        L{createOAuthConsumer} creates a new L{OAuthConsumer} with a secret
        for the specified L{User}.
        """
        user = createUser(u'username', u'secret', u'User', u'user@example.com')
        consumer = createOAuthConsumer(user)
        self.assertIdentical(user, consumer.user)
        self.assertEqual(16, len(consumer.secret))
        self.assertNotIdentical(None, consumer.secret)

    def testCreateOAuthConsumerGeneratesRandomSecret(self):
        """
        L{createOAuthConsumer} generates a random secret each time an
        L{OAuthConsumer} is created.
        """
        user1 = createUser(u'user1', u'secret', u'User1', u'user1@example.com')
        consumer1 = createOAuthConsumer(user1)
        user2 = createUser(u'user2', u'secret', u'User2', u'user2@example.com')
        consumer2 = createOAuthConsumer(user2)
        self.assertNotEqual(consumer1.secret, consumer2.secret)

    def testCreateOAuthConsumerWithCustomSecret(self):
        """
        L{createOAuthConsumer} will use a custom secret, when it's provided.
        """
        secret = ''.join(sample(ascii_letters + digits, 16))
        user = createUser(u'user1', u'secret', u'User1', u'user1@example.com')
        consumer = createOAuthConsumer(user, secret)
        self.assertEqual(secret, consumer.secret)

    def testCreateOAuthConsumerWithInvalidCustomSecret(self):
        """
        L{createOAuthConsumer} raises a C{ValueError} if the custom secret is
        not exactly 16-characters long.
        """
        user = createUser(u'user1', u'secret', u'User1', u'user1@example.com')
        self.assertRaises(ValueError, createOAuthConsumer, user,
                          'custom-secret')

    def testCreateOAuthConsumerAddsToStore(self):
        """
        L{createOAuthConsumer} adds the new L{OAuthConsumer} to the main
        store.
        """
        user = createUser(u'user', u'secret', u'User', u'user@example.com')
        consumer = createOAuthConsumer(user)
        self.assertIdentical(consumer, self.store.find(OAuthConsumer).one())


class GetOAuthConsumersTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testGetOAuthConsumersWithoutMatches(self):
        """
        L{getOAuthConsumers} returns an empty C{ResultSet} if there are no
        matches for the specified L{User.id}s.
        """
        consumer = getOAuthConsumers(userIDs=[sys.maxint]).one()
        self.assertIdentical(None, consumer)

    def testGetOAuthConsumers(self):
        """
        L{getOAuthConsumers} returns all L{OAuthConsumer}s in the database
        when no filtering options are provided.
        """
        user1 = createUser(u'user1', u'secret', u'User1', u'user1@example.com')
        consumer1 = createOAuthConsumer(user1)
        user2 = createUser(u'user2', u'secret', u'User2', u'user2@example.com')
        consumer2 = createOAuthConsumer(user2)
        self.assertEqual([(user1, consumer1), (user2, consumer2)],
                         list(getOAuthConsumers().order_by(User.username)))

    def testGetOAuthConsumersFilteredByUserID(self):
        """
        L{getOAuthConsumers} returns the L{User} and L{OAuthConsumer}
        instances that match the specified L{User.id}.
        """
        user1 = createUser(u'user1', u'secret', u'User1', u'user1@example.com')
        consumer1 = createOAuthConsumer(user1)
        user2 = createUser(u'user2', u'secret', u'User2', u'user2@example.com')
        createOAuthConsumer(user2)
        self.assertEqual((user1, consumer1),
                         getOAuthConsumers(userIDs=[user1.id]).one())
