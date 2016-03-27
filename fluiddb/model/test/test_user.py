from storm.locals import Or, Not

from fluiddb.data.exceptions import (
    DuplicateUserError, UnknownUserError, MalformedUsernameError)
from fluiddb.data.namespace import getNamespaces
from fluiddb.data.permission import Operation, Policy
from fluiddb.data.system import createSystemData
from fluiddb.data.tag import getTags
from fluiddb.data.user import (
    User, createUser, createTwitterUser, getTwitterUsers,
    hashPassword, Role)
from fluiddb.data.value import getTagValues
from fluiddb.exceptions import FeatureError
from fluiddb.model.namespace import NamespaceAPI
from fluiddb.model.user import UserAPI, TwitterUserAPI, checkPassword, getUser
from fluiddb.model.value import TagValueAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import ConfigResource, DatabaseResource


class UserAPITestMixin(object):

    def testCreateWithoutData(self):
        """
        L{SecureUserAPI.create} raises a L{FeatureError} when given an empty
        list of L{User}s.
        """
        self.assertRaises(FeatureError, self.users.create, [])

    def testCreate(self):
        """L{User.create} creates new L{User}s based on the provided data."""
        users = [(u'fred', u'fred-secret', u'Fred', u'fred@example.com'),
                 (u'joe', u'joe-secret', u'Joe', u'joe@example.com')]
        self.users.create(users)
        result = self.store.find(User,
                                 Not(Or(User.username == u'fluiddb',
                                        User.username == u'fluidinfo.com',
                                        User.username == u'anon')))
        result.order_by(User.username)
        [user1, user2] = list(result)
        self.assertEqual(u'fred', user1.username)
        self.assertEqual(hashPassword(u'fred-secret', user1.passwordHash),
                         user1.passwordHash)
        self.assertEqual(u'Fred', user1.fullname)
        self.assertEqual(u'fred@example.com', user1.email)

        self.assertEqual(u'joe', user2.username)
        self.assertEqual(hashPassword(u'joe-secret', user2.passwordHash),
                         user2.passwordHash)
        self.assertEqual(u'Joe', user2.fullname)
        self.assertEqual(u'joe@example.com', user2.email)

    def testCreateCreatesNamespace(self):
        """
        L{User.create} creates new L{User}s based on the provided data and
        a L{Namespace} for the new L{User} to create their L{Tags}s.
        """
        users = [(u'user', u'secret', u'User', u'user@example.com')]
        self.users.create(users)
        user = getUser(u'user')
        namespace = getNamespaces(paths=[u'user']).one()
        self.assertEqual(u'user', namespace.path)
        self.assertIdentical(user, namespace.creator)

    def testCreateCreatesPrivateNamespace(self):
        """
        L{User.create} creates a new C{<username>/private} namespace for all
        L{User}s.  The L{Namespace} has permissions set so that only the owner
        can work with data in this namespace.
        """
        users = [(u'user', u'secret', u'User', u'user@example.com')]
        self.users.create(users)
        user = getUser(u'user')
        namespace = getNamespaces(paths=[u'user/private']).one()
        self.assertEqual(u'user/private', namespace.path)
        self.assertIdentical(user, namespace.creator)
        permission = namespace.permission
        self.assertEqual((Policy.CLOSED, [user.id]),
                         permission.get(Operation.CREATE_NAMESPACE))
        self.assertEqual((Policy.CLOSED, [user.id]),
                         permission.get(Operation.UPDATE_NAMESPACE))
        self.assertEqual((Policy.CLOSED, [user.id]),
                         permission.get(Operation.DELETE_NAMESPACE))
        self.assertEqual((Policy.CLOSED, [user.id]),
                         permission.get(Operation.LIST_NAMESPACE))
        self.assertEqual((Policy.CLOSED, [user.id]),
                         permission.get(Operation.CONTROL_NAMESPACE))

    def testCreateWithoutPrivateNamespace(self):
        """
        L{User.create} creates a new C{<username>/private} namespace, by
        default.  This behaviour is suppressed if a flag is passed.
        """
        users = [(u'user', u'secret', u'User', u'user@example.com')]
        self.users.create(users, createPrivateNamespace=False)
        self.assertIdentical(None,
                             getNamespaces(paths=[u'user/private']).one())

    def testCreateCreatesAboutTag(self):
        """
        L{UserAPI.create} creates new C{fluiddb/about} L{TagValue}s when
        creating new L{User}s.
        """
        values = [(u'username', u'secret', u'User', u'user@example.com')]
        [(objectID, username)] = self.users.create(values)
        tag = getTags(paths=[u'fluiddb/about']).one()
        value = getTagValues([(objectID, tag.id)]).one()
        self.assertEqual(u'@username', value.value)

    def testCreateReusesPreviousObjectIDs(self):
        """
        If a L{User} is deleted and created again, L{UserAPI.create}
        uses the old object ID.
        """
        values = [(u'username', u'secret', u'User', u'user@example.com')]
        result1 = self.users.create(values)
        getNamespaces(paths=[u'username/private']).remove()
        self.users.delete([u'username'])
        result2 = self.users.create(values)
        self.assertEqual(result1, result2)

    def testCreateCreatesUsernameTags(self):
        """
        L{UserAPI.create} creates the C{fluiddb/users/username} tag value for
        the created user.
        """
        values = [(u'username', u'secret', u'User', u'user@example.com')]
        [(objectID, username)] = self.users.create(values)
        tagID = self.system.tags[u'fluiddb/users/username'].id
        value = getTagValues([(objectID, tagID)]).one()
        self.assertEqual(u'username', value.value)

    def testCreateCreatesNameTags(self):
        """
        L{UserAPI.create} creates the C{fluiddb/users/name} tag value for
        the created user.
        """
        values = [(u'username', u'secret', u'Full Name', u'user@example.com')]
        [(objectID, username)] = self.users.create(values)
        tagID = self.system.tags[u'fluiddb/users/name'].id
        value = getTagValues([(objectID, tagID)]).one()
        self.assertEqual(u'Full Name', value.value)

    def testCreateCreatesEmailTags(self):
        """
        L{UserAPI.create} creates the C{fluiddb/users/email} tag value for
        the created user.
        """
        values = [(u'username', u'secret', u'Full Name', u'user@example.com')]
        [(objectID, username)] = self.users.create(values)
        tagID = self.system.tags[u'fluiddb/users/email'].id
        value = getTagValues([(objectID, tagID)]).one()
        self.assertEqual(u'user@example.com', value.value)

    def testCreateCreatesRoleTags(self):
        """
        L{UserAPI.create} creates the C{fluiddb/users/role} tag value for
        the created user.
        """
        values = [(u'username', u'secret', u'Full Name', u'user@example.com')]
        [(objectID, username)] = self.users.create(values)
        tagID = self.system.tags[u'fluiddb/users/role'].id
        value = getTagValues([(objectID, tagID)]).one()
        self.assertEqual(u'USER', value.value)

    def testCreateWithExistingUsername(self):
        """
        L{UserAPI.create} raises a L{DuplicateUserError} exception if an
        attempt to create a L{User} with the same username as an existing
        L{User} is made.
        """
        users = [(u'fred', u'fred-secret', u'Fred', u'fred@example.com'),
                 (u'joe', u'joe-secret', u'Joe', u'joe@example.com')]
        self.users.create(users)

        error = self.assertRaises(
            DuplicateUserError, self.users.create,
            [(u'fred', u'fred-secret', u'Fred', u'fred@example.com')])
        self.assertEqual(set([u'fred']), error.usernames)

    def testCreateWithInvalidUsername(self):
        """
        L{UserAPI.create} raises a L{MalformedUsernameError} exception if an
        attempt to create a L{User} with an invalid username is made.
        """
        users = [(u'!wrong & name', u'secret', u'None', u'none@example.com')]

        self.assertRaises(MalformedUsernameError, self.users.create, users)

    def testDeleteWithoutData(self):
        """
        L{UserAPI.delete} raises a L{FeatureError} if no L{User.username}s are
        provided.
        """
        self.assertRaises(FeatureError, self.users.delete, [])

    def testDelete(self):
        """
        L{UserAPI.delete} removes L{User}s, returning the objectIDs and
        usernames of the deleted users.
        """
        self.users.create([(u'username', u'password', u'User',
                            u'user@example.com')])
        getNamespaces(paths=[u'username/private']).remove()
        self.users.delete([u'username'])
        self.assertIdentical(None, getUser(u'username'))

    def testDeleteDoesNotDeleteOtherUsers(self):
        """
        L{UserAPI.delete} removes the L{User}s it is asked to delete
        but not other users.
        """
        self.users.create([(u'username1', u'password', u'User',
                            u'user@example.com')])
        self.users.create([(u'username2', u'password', u'User',
                            u'user@example.com')])
        getNamespaces(paths=[u'username1/private']).remove()
        self.users.delete([u'username1'])
        user = getUser(u'username2')
        self.assertEqual(u'username2', user.username)

    def testDeleteDoesNotDeleteOtherUsersWhenPassedAGenerator(self):
        """
        L{UserAPI.delete} removes the L{User}s it is asked to delete but
        not other users, when it is passed a generator (as opposed to a
        C{list}).
        """
        self.users.create([(u'username1', u'password', u'User',
                            u'user@example.com')])
        self.users.create([(u'username2', u'password', u'User',
                            u'user@example.com')])
        getNamespaces(paths=[u'username1/private']).remove()
        self.users.delete(username for username in [u'username1'])
        user = getUser(u'username2')
        self.assertEqual(u'username2', user.username)

    def testDeleteWithUnknownUser(self):
        """
        An L{UnknownUserError} is raised if L{User.delete} is passed a
        C{username} that doesn't match an existing user.
        """
        error = self.assertRaises(UnknownUserError, self.users.delete,
                                  [u'unknown'])
        self.assertEqual([u'unknown'], error.usernames)

    def testDeleteRemovesSystemTags(self):
        """
        L{UserAPI.delete} removes the C{fluiddb/users/*} tag values stored for
        deleted L{User}s.
        """
        self.users.create([(u'user', u'pass', u'User', u'user@example.com')])
        user = getUser(u'user')
        NamespaceAPI(user).delete([u'user/private'])
        [(objectID, _)] = self.users.delete([u'user'])
        tagValues = TagValueAPI(self.system.users[u'fluiddb'])
        result = tagValues.get(objectIDs=[objectID],
                               paths=[u'fluiddb/users/username',
                                      u'fluiddb/users/name',
                                      u'fluiddb/users/email',
                                      u'fluiddb/users/role'])
        self.assertEqual({}, result)

    def testGetWithoutData(self):
        """
        L{UserAPI.get} raises a L{FeatureError} if no L{User.username}s are
        provided.
        """
        self.assertRaises(FeatureError, self.users.get, [])

    def testGet(self):
        """
        L{UserAPI.get} returns the L{User}s that match the specified
        L{User.username}s.
        """
        createUser(u'user1', u'secret', u'User 1', u'user1@example.com')
        user = createUser(u'user2', u'secret', u'User 2', u'user2@example.com')
        self.assertEqual({u'user2': {'id': user.objectID, 'name': u'User 2',
                                     'role': Role.USER}},
                         self.users.get([u'user2']))

    def testSetWithoutData(self):
        """
        L{UserAPI.set} raises a L{FeatureError} if an empty list of
        C{values} instances is provided.
        """
        self.assertRaises(FeatureError, self.users.set, [])

    def testSet(self):
        """
        L{UserAPI.set} updates information L{User}s based on the specified
        data, returning the object IDs and usernames of the updated users.
        """
        user1 = createUser(u'user1', u'secret', u'User1', u'user1@example.com')
        passwordHash1 = user1.passwordHash
        user2 = createUser(u'user2', u'secret', u'User2', u'user2@example.com')
        passwordHash2 = user2.passwordHash
        self.users.set([(u'user1', u'new password', u'new name',
                         u'new-email@example.com', Role.USER_MANAGER)])

        self.assertEqual(u'user1', user1.username)
        self.assertNotEqual(passwordHash1, user1.passwordHash)
        self.assertEqual(u'new name', user1.fullname)
        self.assertEqual(u'new-email@example.com', user1.email)
        self.assertEqual(Role.USER_MANAGER, user1.role)

        self.assertEqual(u'user2', user2.username)
        self.assertEqual(passwordHash2, user2.passwordHash)
        self.assertEqual(u'User2', user2.fullname)
        self.assertEqual(u'user2@example.com', user2.email)
        self.assertEqual(Role.USER, user2.role)

    def testSetWithoutPassword(self):
        """
        If a L{User.password} is not passed to L{UserAPI.set} the existing
        password will not be changed.
        """
        user = createUser(u'user', u'secret', u'User', u'user@example.com')
        passwordHash = user.passwordHash
        self.users.set([(u'user', None, u'new-name', u'new-user@example.com',
                         Role.USER_MANAGER)])
        self.assertEqual(u'user', user.username)
        self.assertEqual(passwordHash, user.passwordHash)
        self.assertEqual(u'new-name', user.fullname)
        self.assertEqual(u'new-user@example.com', user.email)
        self.assertEqual(Role.USER_MANAGER, user.role)

    def testSetWithoutName(self):
        """
        If a L{User.fullname} is not passed to L{UserAPI.set} the existing
        name will not be changed.
        """
        user = createUser(u'user', u'secret', u'User', u'user@example.com')
        passwordHash = user.passwordHash
        self.users.set([(u'user', u's3cr3t', None, u'new-user@example.com',
                         Role.USER_MANAGER)])
        self.assertEqual(u'user', user.username)
        self.assertNotEqual(passwordHash, user.passwordHash)
        self.assertEqual(u'User', user.fullname)
        self.assertEqual(u'new-user@example.com', user.email)
        self.assertEqual(Role.USER_MANAGER, user.role)

    def testSetWithoutEmail(self):
        """
        If a L{User.email} is not passed to L{UserAPI.set} the existing
        email address will not be changed.
        """
        user = createUser(u'user', u'secret', u'User', u'user@example.com')
        passwordHash = user.passwordHash
        self.users.set([(u'user', u's3cr3t', u'new-name', None,
                         Role.USER_MANAGER)])
        self.assertEqual(u'user', user.username)
        self.assertNotEqual(passwordHash, user.passwordHash)
        self.assertEqual(u'new-name', user.fullname)
        self.assertEqual(u'user@example.com', user.email)

    def testSetWithoutRole(self):
        """
        If a L{User.role} is not passed to L{UserAPI.set} the existing
        role will not be changed.
        """
        user = createUser(u'user', u'secret', u'User', u'user@example.com')
        passwordHash = user.passwordHash
        self.users.set([(u'user', None, None, None, Role.USER_MANAGER)])
        self.users.set([(u'user', u's3cr3t', u'new-name',
                         u'new-user@example.com', None)])
        self.assertEqual(u'user', user.username)
        self.assertNotEqual(passwordHash, user.passwordHash)
        self.assertEqual(u'new-name', user.fullname)
        self.assertEqual(u'new-user@example.com', user.email)
        self.assertEqual(Role.USER_MANAGER, user.role)

    def testSetUpdatesTagValues(self):
        """
        The C{fluiddb/users/name} and C{fluiddb/users/email} L{TagValue}s are
        updated when L{User} details are changed by L{UserAPI.set}.
        """
        user = createUser(u'user', u'secret', u'User', u'user@example.com')
        self.users.set([(u'user', u'pwd', u'name', u'new-user@example.com',
                         Role.USER_MANAGER)])
        result = TagValueAPI(user).get([user.objectID],
                                       [u'fluiddb/users/name',
                                        u'fluiddb/users/email',
                                        u'fluiddb/users/role'])
        email = result[user.objectID][u'fluiddb/users/email'].value
        name = result[user.objectID][u'fluiddb/users/name'].value
        role = result[user.objectID][u'fluiddb/users/role'].value
        self.assertEqual(u'new-user@example.com', email)
        self.assertEqual(u'name', name)
        self.assertEqual(u'USER_MANAGER', role)

    def testSetSkipsUpdatingTagValuesWhenPasswordChanges(self):
        """
        The C{fluiddb/users/name} and C{fluiddb/users/email} L{TagValue}s are
        not updated when only the L{User.password} is changed by
        L{UserAPI.set}.
        """
        user = createUser(u'user', u'secret', u'User', u'user@example.com')
        self.users.set([(u'user', u'pwd', None, None, None)])
        result = TagValueAPI(user).get([user.objectID],
                                       [u'fluiddb/users/name',
                                        u'fluiddb/users/email',
                                        u'fluiddb/users/role'])
        self.assertEqual({}, result)

    def testSetWithUnknownUser(self):
        """
        An L{UnknownUserError} is raised if a non-existent user is passed
        to L{User.set}.
        """
        values = [(u'unknown', u'pwd', u'name', u'u@example.com', None)]
        error = self.assertRaises(UnknownUserError, self.users.set, values)
        self.assertEqual([u'unknown'], error.usernames)


class UserAPITest(UserAPITestMixin, FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(UserAPITest, self).setUp()
        self.system = createSystemData()
        self.users = UserAPI()


class TwitterUserAPITest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testCreateWithoutMatchingUser(self):
        """
        L{TwitterUserAPI.create} raises L{UnknownUserError} if the specified
        L{User.username} doesn't match an existing L{User}.
        """
        error = self.assertRaises(UnknownUserError, TwitterUserAPI().create,
                                  u'unknown', 1239586)
        self.assertEqual([u'unknown'], error.usernames)

    def testCreate(self):
        """
        L{TwitterUserAPI.create} creates a new L{TwitterUser} to map a Twitter
        UID to an existing L{User}.
        """
        user = createUser(u'user', u'secret', u'User', u'user@example.com')
        TwitterUserAPI().create(u'user', 19385982)
        sameUser, twitterUser = getTwitterUsers([19385982]).one()
        self.assertNotIdentical(None, twitterUser)
        self.assertIdentical(user, sameUser)

    def testGet(self):
        """
        L{TwitterUserAPI.get} returns the L{User} matching a specified Twitter
        UID, if one exists.
        """
        user = createUser(u'user', u'secret', u'User', u'user@example.com')
        createTwitterUser(user, 1928745)
        self.assertIdentical(user, TwitterUserAPI().get(1928745))

    def testGetWithoutMatch(self):
        """
        L{TwitterUserAPI.get} returns C{None} if the L{User} matching the
        specified Twitter UID is not available.
        """
        self.assertIdentical(None, TwitterUserAPI().get(1928745))


class CheckPasswordTest(FluidinfoTestCase):

    def testCheckPassword(self):
        """
        C{checkPassword} will return C{True} when the password hash matches
        the plaintext password.
        """
        password = u'super-secret'
        passwordHash = hashPassword(password)
        self.assertTrue(checkPassword(password, passwordHash))

    def testCheckPasswordIncorrect(self):
        """
        C{checkPassword} will return C{False} when the password hash doesn't
        match the plaintext password.
        """
        password = u'super-secret'
        passwordHash = hashPassword(u'different-password')
        self.assertFalse(checkPassword(password, passwordHash))


class GetUserTestMixin():

    def testGetUser(self):
        """L{getUser} returns the requested user."""
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        self.assertIdentical(user, self.getUser(u'username'))

    def testGetUserReturnsNoneIfUserDoesNotExist(self):
        """L{getUser} returns C{None} if the user doesn't exist."""
        self.assertIdentical(None, self.getUser(u'username'))


class GetUserTest(GetUserTestMixin, FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def setUp(self):
        super(GetUserTest, self).setUp()
        self.getUser = getUser
