from string import letters, digits

from storm.exceptions import IntegrityError

from fluiddb.data.exceptions import DuplicateUserError
from fluiddb.data.user import (
    User, TwitterUser, Role, createUser, createTwitterUser,
    getUsers, getTwitterUsers, hashPassword, isValidUsername, validateEmail)
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import DatabaseResource


class CreateUserTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testCreateUser(self):
        """L{createUser} creates a new L{User}."""
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        self.assertEqual(u'username', user.username)
        self.assertEqual(Role.USER, user.role)
        self.assertNotIdentical(None, user.objectID)
        self.assertNotIdentical(None, user.creationTime)

    def testCreateUserAddsToStore(self):
        """L{createUser} adds the new L{User} to the main store."""
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        self.assertIdentical(user, self.store.find(User).one())

    def testCreateUserWithDuplicateName(self):
        """
        A L{DuplicateUserError} is raised if an attempt to create a L{User}
        with an existing username is made.
        """
        createUser(u'username', u'password', u'User', u'user@example.com')
        self.assertRaises(DuplicateUserError,
                          createUser, u'username', u'password', u'User',
                          u'user@example.com')

    def testCreateUserWithCustomRole(self):
        """A custom role can optionally be passed to L{createUser}."""
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com', Role.SUPERUSER)
        self.assertEqual(Role.SUPERUSER, user.role)

    def testCreateUserWithoutPassword(self):
        """
        L{createUser} returns a disabled L{User.password} if no password is
        specified.
        """
        user = createUser(u'username', None, u'User',
                          u'user@example.com', Role.SUPERUSER)
        self.assertEqual('!', user.passwordHash)

    def testCreateUserWithoutEmail(self):
        """L{createUser} can create a L{User} without an email address."""
        user = createUser(u'username', u'password', u'User',
                          None, Role.SUPERUSER)
        self.assertIdentical(None, user.email)


class GetUsersTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testGetUsers(self):
        """L{getUsers} returns all L{User}s in the database, by default."""
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        self.assertIdentical(user, getUsers().one())

    def testGetUsersByUsernames(self):
        """
        When L{User.username}s are provided L{getUsers} returns matching
        L{User}s.
        """
        createUser(u'username1', u'password', u'User1', u'user1@example.com')
        user = createUser(u'username2', u'password', u'User2',
                          u'user2@example.com')
        result = getUsers(usernames=[u'username2'])
        self.assertIdentical(user, result.one())

    def testGetUsersByID(self):
        """
        When L{User.id}s are provided L{getUsers} returns matching L{User}s.
        """
        createUser(u'username1', u'password', u'User1', u'user1@example.com')
        user = createUser(u'username2', u'password', u'User2',
                          u'user2@example.com')
        result = getUsers(ids=[user.id])
        self.assertIdentical(user, result.one())

    def testGetUsersByObjectID(self):
        """
        When L{User.objectID}s are provided L{getUsers} returns matching
        L{User}s.
        """
        createUser(u'username1', u'password', u'User1', u'user1@example.com')
        user = createUser(u'username2', u'password', u'User2',
                          u'user2@example.com')
        result = getUsers(objectIDs=[user.objectID])
        self.assertIdentical(user, result.one())


class UserTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testIsAnonymous(self):
        """
        L{User.isAnonymous} returns C{True} if the L{User} has the
        L{Role.ANONYMOUS}.
        """
        user = self.store.add(User(u'username', 'password-hash', u'John Doe',
                                   u'john@example.com', Role.ANONYMOUS))
        self.assertTrue(user.isAnonymous())
        self.assertFalse(user.isSuperuser())
        self.assertFalse(user.isUser())

    def testIsSuperuser(self):
        """
        L{User.isSuperuser} returns C{True} if the L{User} has the
        L{Role.SUPERUSER}.
        """
        user = self.store.add(User(u'username', 'password-hash', u'John Doe',
                                   u'john@example.com', Role.SUPERUSER))
        self.assertTrue(user.isSuperuser())
        self.assertFalse(user.isAnonymous())
        self.assertFalse(user.isUser())

    def testIsUser(self):
        """
        L{User.isUser} returns C{True} if the L{User} has the L{Role.USER}.
        """
        user = self.store.add(User(u'username', 'password-hash', u'John Doe',
                                   u'john@example.com', Role.USER))
        self.assertTrue(user.isUser())
        self.assertFalse(user.isAnonymous())
        self.assertFalse(user.isSuperuser())


class UserSchemaTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testUniqueNameConstraint(self):
        """
        An C{IntegrityError} is raised if a L{User} with a duplicate username
        is added to the database.
        """
        self.store.add(User(u'username', 'password-hash', u'User',
                            u'user@example.com', Role.USER))
        self.store.flush()
        self.store.add(User(u'username', 'password-hash', u'User',
                            u'user@example.com', Role.USER))
        self.assertRaises(IntegrityError, self.store.flush)
        self.store.rollback()

    def testUniqueObjectIDConstraint(self):
        """
        An C{IntegrityError} is raised if a L{User} with a duplicate object ID
        is added to the database.
        """
        user1 = User(u'username1', 'password-hash', u'User1',
                     u'user1@example.com', Role.USER)
        self.store.add(user1)
        self.store.flush()
        user2 = User(u'username2', 'password-hash', u'User2',
                     u'user2@example.com', Role.USER)
        user2.objectID = user1.objectID
        self.store.add(user2)
        self.assertRaises(IntegrityError, self.store.flush)
        self.store.rollback()

    def testInvalidEmailAddress(self):
        """
        A C{ValueError} is raised if a L{User} with an invalid email address
        is created.
        """
        self.assertRaises(ValueError, User, u'username', 'password-hash',
                          u'User', u'', Role.USER)
        self.assertRaises(ValueError, User, u'username', 'password-hash',
                          u'User', u'user', Role.USER)
        self.assertRaises(ValueError, User, u'username', 'password-hash',
                          u'User', u'user.', Role.USER)
        self.assertRaises(ValueError, User, u'username', 'password-hash',
                          u'User', u'user@host', Role.USER)
        self.assertRaises(ValueError, User, u'username', 'password-hash',
                          u'User', u'user@host.', Role.USER)
        self.assertRaises(ValueError, User, u'username', 'password-hash',
                          u'User', u'.user@host.', Role.USER)
        self.assertRaises(ValueError, User, u'username', 'password-hash',
                          u'User', u'user;@host.', Role.USER)
        self.assertRaises(ValueError, User, u'username', 'password-hash',
                          u'User', u'user;@host.com', Role.USER)
        self.assertRaises(ValueError, User, u'username', 'password-hash',
                          u'User', u'user:@host.com', Role.USER)
        self.assertRaises(ValueError, User, u'username', 'password-hash',
                          u'User', u'user\n@host.com', Role.USER)
        self.assertRaises(ValueError, User, u'username', 'password-hash',
                          u'User', u'user\r@host.com', Role.USER)


class HashPasswordTest(FluidinfoTestCase):

    def testPredictablePasswordWithSalt(self):
        """
        If the L{hashPassword} function is called with a known salt, the
        hashed string must be always the same.
        """
        password = u'password'
        salt = 'salt'
        hashedPassword = hashPassword(password, salt)
        self.assertEqual('sa3tHJ3/KuYvI', hashedPassword)

    def testRandomSaltMD5(self):
        """
        If the L{hashPassword} function is called without a salt, it must
        generate a random one and return a hashed string using the MD5
        algorithm.
        """
        password = u'password'
        # An MD5-hashed password consists of three fields separated by $:
        # 1) the mechanism (1 for MD5, 2a for Blowfish, 5 for SHA-256 and 6
        #     for SHA-512)
        # 2) the salt
        # 3) the hashed password
        _, mechanism, salt, hashedPassword = hashPassword(password).split('$')
        self.assertEqual('1', mechanism)

    def testCheckSamePassword(self):
        """
        If the L{hashPassword} function is called with a hashed password as
        its salt, it'll return the same hashed password if the given plain
        text password matches.
        """
        password = u'password'
        hashedPassword = hashPassword(password)
        hashedPassword2 = hashPassword(password, hashedPassword)
        self.assertEqual(hashedPassword, hashedPassword2)

    def testCheckDifferentPassword(self):
        """
        If the L{hashPassword} function is called with a hashed password as
        its salt and a plain text password that doesn't match, it'll return
        the hash value for the plain text password.
        """
        password = u'password'
        hashedPassword = hashPassword(password)

        password2 = u'password2'
        hashedPassword2 = hashPassword(password2, hashedPassword)
        self.assertNotEqual(hashedPassword, hashedPassword2)


class IsValidUsernameTest(FluidinfoTestCase):

    def testValidUsername(self):
        """
        L{isValidUsername} returns C{True} if the specified username is not
        empty, its length is less than 128 characters and is made up of
        alphanumeric characters, colon, dash, dot or underscore.
        """
        validCharacters = letters + digits + ':-._'
        for character in validCharacters:
            self.assertTrue(isValidUsername(unicode(character)))

    def testUsernameIsEmpty(self):
        """
        L{isValidUsername} returns C{False} if the specified username is empty.
        """
        self.assertFalse(isValidUsername(u''))

    def testUnnacceptableCharacter(self):
        """
        L{isValidUsername} returns C{False} if the specified username contains
        unnacceptable characters.
        """
        invalidCharacters = u'/!@#$%^&*()+={}[]\;"\'?<>\\, '
        for character in invalidCharacters:
            self.assertFalse(isValidUsername(character))

    def testLongUsername(self):
        """
        L{isValidUsername} returns C{False} if the specified username is longer
        than 128 characters.
        """
        self.assertFalse(isValidUsername('x' * 129))

    def testLongestUsername(self):
        """
        L{isValidUsername} returns C{true} if the specified username has 128
        characters.
        """
        self.assertTrue(isValidUsername('x' * 128))


class ValidateEmailTest(FluidinfoTestCase):

    def testInvalidEmailAddress(self):
        """
        L{validateEmail} raises a C{ValueError} is raised if a invalid email
        address is provided.
        """
        self.assertRaises(ValueError, validateEmail, None, None, u'')
        self.assertRaises(ValueError, validateEmail, None, None, u'user')
        self.assertRaises(ValueError, validateEmail, None, None, u'user.')
        self.assertRaises(ValueError, validateEmail, None, None, u'user@host')
        self.assertRaises(ValueError, validateEmail, None, None, u'user@host.')
        self.assertRaises(ValueError, validateEmail, None, None,
                          u'.user@host.')
        self.assertRaises(ValueError, validateEmail, None, None, u'user;@host')
        self.assertRaises(ValueError, validateEmail, None, None,
                          u'user;@host.com')
        self.assertRaises(ValueError, validateEmail, None, None,
                          u'user:@host')
        self.assertRaises(ValueError, validateEmail, None, None,
                          u'user:@host.com')
        self.assertRaises(ValueError, validateEmail, None, None,
                          u'user\n@host.com')
        self.assertRaises(ValueError, validateEmail, None, None,
                          u'user\r@host.com')

    def testValidEmailAddress(self):
        """L{validateEmail} returns the email address if it's valid."""
        self.assertEqual(
            u"tim.o'reilly@example.com",
            validateEmail(None, None, u"tim.o'reilly@example.com"))
        self.assertEqual(u"user@example.com",
                         validateEmail(None, None, u"user@example.com"))
        self.assertEqual(u"user.name@example.com",
                         validateEmail(None, None, u"user.name@example.com"))


class CreateTwitterUserTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testCreateTwitterUser(self):
        """
        L{createTwitterUser} creates a new L{TwitterUser}, adds them to the
        database, and returns the new instance.
        """
        user = createUser(u'username', u'secret', u'User', u'user@example.com')
        twitterUser = createTwitterUser(user, 91845202)
        self.assertIdentical(user, twitterUser.user)
        self.assertEqual(91845202, twitterUser.uid)

    def testCreateTwitterUserAddsToStore(self):
        """
        L{createTwitterUser} adds the new L{TwitterUser} to the main store.
        """
        user = createUser(u'username', u'secret', u'User', u'user@example.com')
        twitterUser = createTwitterUser(user, 91845202)
        self.assertIdentical(twitterUser, self.store.find(TwitterUser).one())


class GetTwitterUsersTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testGetTwitterUsersWithoutMatches(self):
        """
        L{getTwitterUsers} returns an empty C{ResultSet} if there are no
        matches for the specified Twitter UID.
        """
        self.assertIdentical(None, getTwitterUsers(uids=[193874]).one())

    def testGetTwitterUsers(self):
        """
        L{getTwitterUsers} returns all L{TwitterUser}s in the database when no
        filtering options are provided.
        """
        user1 = createUser(u'user1', u'secret', u'User1', u'user1@example.com')
        twitterUser1 = createTwitterUser(user1, 91845202)
        user2 = createUser(u'user2', u'secret', u'User2', u'user2@example.com')
        twitterUser2 = createTwitterUser(user2, 198383)
        self.assertEqual([(user1, twitterUser1), (user2, twitterUser2)],
                         list(getTwitterUsers().order_by(User.username)))

    def testGetTwitterUsersFilteredByUID(self):
        """
        L{getTwitterUsers} returns the L{User} and L{TwitterUser} instances
        that match the specified UID.
        """
        user1 = createUser(u'user1', u'secret', u'User1', u'user1@example.com')
        twitterUser1 = createTwitterUser(user1, 91845202)
        user2 = createUser(u'user2', u'secret', u'User2', u'user2@example.com')
        createTwitterUser(user2, 198383)
        self.assertEqual((user1, twitterUser1),
                         getTwitterUsers(uids=[91845202]).one())
