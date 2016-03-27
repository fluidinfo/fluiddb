from fluiddb.data.exceptions import UnknownUserError
from fluiddb.data.user import createUser
from fluiddb.security.authentication import AuthenticationError, authenticate
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    DatabaseResource, ConfigResource, CacheResource)


class AuthenticateTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def testAuthenticate(self):
        """
        L{authenticate} will be successful if the C{username} and the
        plaintext C{password} passed match a L{User} in the database.
        """
        user = createUser(u'fred', u'fred-secret', u'Fred',
                          u'fred@example.com')
        self.assertIdentical(user, authenticate(u'fred', u'fred-secret'))

    def testAuthenticateFailsWithIncorrectPassword(self):
        """
        L{authenticate} will be unsuccessful if the C{username} and the
        plaintext C{password} passed don't match a L{User} in the database.
        """
        createUser(u'fred', u'fred-secret', u'Fred', u'fred@example.com')
        self.assertRaises(AuthenticationError,
                          authenticate, u'fred', u'bad-secret')

    def testAuthenticateFailsWithUnknownUser(self):
        """
        L{authenticate} will be unsuccessful if the C{username} and the
        plaintext C{password} passed don't match a L{User} in the database.
        """
        error = self.assertRaises(UnknownUserError,
                                  authenticate, u'unknown', u'bad-secret')
        self.assertEqual([u'unknown'], error.usernames)
