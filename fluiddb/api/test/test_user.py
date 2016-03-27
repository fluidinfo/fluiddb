from uuid import uuid4

from twisted.internet.defer import inlineCallbacks

from fluiddb.api.facade import Facade
from fluiddb.application import FluidinfoSessionFactory
from fluiddb.common.types_thrift.ttypes import (
    TUserUpdate, TNoSuchUser, TPathPermissionDenied, TBadRequest)
from fluiddb.data.system import createSystemData
from fluiddb.data.user import Role
from fluiddb.model.user import UserAPI, getUser
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    CacheResource, ConfigResource, DatabaseResource, LoggingResource,
    ThreadPoolResource)
from fluiddb.testing.session import login
from fluiddb.util.transact import Transact


class FacadeUserMixinTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(FacadeUserMixinTest, self).setUp()
        self.transact = Transact(self.threadPool)
        factory = FluidinfoSessionFactory('API-9000')
        self.facade = Facade(self.transact, factory)
        system = createSystemData()
        self.admin = system.users[u'fluiddb']

    @inlineCallbacks
    def testGetUserWithoutData(self):
        """
        L{FacadeUserMixin.getUser} raises a L{TNoSuchUser} exception if the
        requested L{User.username} doesn't exist.
        """
        self.store.commit()
        with login(u'fluiddb', self.admin.objectID, self.transact) as session:
            deferred = self.facade.getUser(session, u'unknown')
            error = yield self.assertFailure(deferred, TNoSuchUser)
            self.assertEqual(u'unknown', error.name)

    @inlineCallbacks
    def testGetUser(self):
        """
        L{FacadeUserMixin.getUser} returns a L{TUser} instance with
        information about the requested L{User}.
        """
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        user = getUser(u'user')
        self.store.commit()
        with login(u'fluiddb', self.admin.objectID, self.transact) as session:
            result = yield self.facade.getUser(session, u'user')
            self.assertEqual(u'user', result.username)
            self.assertEqual(str(user.objectID), result.objectId)
            self.assertEqual(u'User', result.name)
            self.assertEqual(u'USER', result.role)

    @inlineCallbacks
    def testGetUserIgnoresCase(self):
        """L{FacadeUserMixin.getUser} ignores case for the username."""
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        self.store.commit()
        with login(u'fluiddb', self.admin.objectID, self.transact) as session:
            result = yield self.facade.getUser(session, u'uSeR')
            self.assertEqual(u'user', result.username)

    @inlineCallbacks
    def testUpdateUser(self):
        """
        L{FacadeUserMixin.updateUser} updates the description for an existing
        L{User}.
        """
        UserAPI().create([(u'test', u'secret', u'name', u'name@example.com')])
        user = getUser(u'test')
        passwordHash = user.passwordHash
        self.store.commit()
        info = TUserUpdate(u'test', u'password', u'new-name',
                           u'new-name@example.com')
        with login(u'fluiddb', self.admin.objectID, self.transact) as session:
            yield self.facade.updateUser(session, info)

        self.store.rollback()
        self.assertEqual(u'test', user.username)
        self.assertNotEqual(passwordHash, user.passwordHash)
        self.assertEqual(u'new-name', user.fullname)
        self.assertEqual(u'new-name@example.com', user.email)

    @inlineCallbacks
    def testUpdateUserWithoutPassword(self):
        """
        If a L{User.password} is not passed to L{FacadeUserMixin.updateUser}
        the existing password will not be changed.
        """
        UserAPI().create([(u'user', u'secret', u'name', u'name@example.com')])
        user = getUser(u'user')
        passwordHash = user.passwordHash
        info = TUserUpdate(u'user', None, u'new-name', u'new-name@example.com',
                           'USER_MANAGER')
        self.store.commit()
        with login(u'fluiddb', self.admin.objectID, self.transact) as session:
            yield self.facade.updateUser(session, info)

        self.store.rollback()
        self.assertEqual(u'user', user.username)
        self.assertEqual(passwordHash, user.passwordHash)
        self.assertEqual(u'new-name', user.fullname)
        self.assertEqual(u'new-name@example.com', user.email)
        self.assertEqual(Role.USER_MANAGER, user.role)

    @inlineCallbacks
    def testUpdateUserWithoutName(self):
        """
        If a L{User.fullname} is not passed to L{FacadeUserMixin.updateUser}
        the existing name will not be changed.
        """
        UserAPI().create([(u'user', u'secret', u'name', u'name@example.com')])
        user = getUser(u'user')
        passwordHash = user.passwordHash
        info = TUserUpdate(u'user', u's3cr3t', None, u'new-name@example.com',
                           'USER_MANAGER')
        self.store.commit()
        with login(u'fluiddb', self.admin.objectID, self.transact) as session:
            yield self.facade.updateUser(session, info)

        self.store.rollback()
        self.assertEqual(u'user', user.username)
        self.assertNotEqual(passwordHash, user.passwordHash)
        self.assertEqual(u'name', user.fullname)
        self.assertEqual(u'new-name@example.com', user.email)
        self.assertEqual(Role.USER_MANAGER, user.role)

    @inlineCallbacks
    def testUpdateUserWithoutEmail(self):
        """
        If a L{User.email} is not passed to L{FacadeUserMixin.updateUser}
        the existing email address will not be changed.
        """
        UserAPI().create([(u'user', u'secret', u'name', u'name@example.com')])
        user = getUser(u'user')
        passwordHash = user.passwordHash
        info = TUserUpdate(u'user', u's3cr3t', u'new-name', None,
                           'USER_MANAGER')
        self.store.commit()
        with login(u'fluiddb', self.admin.objectID, self.transact) as session:
            yield self.facade.updateUser(session, info)

        self.store.rollback()
        self.assertEqual(u'user', user.username)
        self.assertNotEqual(passwordHash, user.passwordHash)
        self.assertEqual(u'new-name', user.fullname)
        self.assertEqual(u'name@example.com', user.email)
        self.assertEqual(Role.USER_MANAGER, user.role)

    @inlineCallbacks
    def testUpdateUserWithoutRole(self):
        """
        If a L{User.role} is not passed to L{FacadeUserMixin.updateUser}
        the existing user role will not be changed.
        """
        UserAPI().create([(u'user', u'secret', u'name', u'name@example.com')])
        user = getUser(u'user')
        passwordHash = user.passwordHash
        info = TUserUpdate(u'user', u's3cr3t', u'new-name', 'new@example.com',
                           None)
        self.store.commit()
        with login(u'fluiddb', self.admin.objectID, self.transact) as session:
            yield self.facade.updateUser(session, info)

        self.store.rollback()
        self.assertEqual(u'user', user.username)
        self.assertNotEqual(passwordHash, user.passwordHash)
        self.assertEqual(u'new-name', user.fullname)
        self.assertEqual(u'new@example.com', user.email)
        self.assertEqual(Role.USER, user.role)

    @inlineCallbacks
    def testUpdateUserWithBadRole(self):
        """
        If an invalid L{User.role} is passed to L{FacadeUserMixin.updateUser}
        a L{TBadRequest} exception is raised.
        """
        info = TUserUpdate(u'user', u's3cr3t', u'new-name', 'new@example.com',
                           'BAD_ROLE')
        with login(u'fluiddb', self.admin.objectID, self.transact) as session:
            deferred = self.facade.updateUser(session, info)
            yield self.assertFailure(deferred, TBadRequest)

    @inlineCallbacks
    def testUpdateUserIgnoresCase(self):
        """
        L{FacadeUserMixin.updateUser} ignores case when updating a new user.
        """
        UserAPI().create([(u'test', u'secret', u'name', u'name@example.com')])
        user = getUser(u'test')
        passwordHash = user.passwordHash
        info = TUserUpdate(u'TesT', u'password', u'new-name',
                           u'new-name@example.com')
        self.store.commit()
        with login(u'fluiddb', self.admin.objectID, self.transact) as session:
            yield self.facade.updateUser(session, info)

        self.store.rollback()
        self.assertEqual(u'test', user.username)
        self.assertNotEqual(passwordHash, user.passwordHash)
        self.assertEqual(u'new-name', user.fullname)
        self.assertEqual(u'new-name@example.com', user.email)

    @inlineCallbacks
    def testUpdateUserWithUnknownUsername(self):
        """
        L{FacadeUserMixin.updateUser} raises a L{TNoSuchUser} exception
        if the requested L{User.username} doesn't exist.
        """
        info = TUserUpdate(u'unknown', u'password', u'name',
                           u'email@example.com')
        self.store.commit()
        with login(u'fluiddb', self.admin.objectID, self.transact) as session:
            deferred = self.facade.updateUser(session, info)
            error = yield self.assertFailure(deferred, TNoSuchUser)
            self.assertEqual(u'unknown', error.name)

    @inlineCallbacks
    def testUpdateUserIsDenied(self):
        """
        L{FacadeUserMixin.updateUser} raises a L{TPathPermissionDenied}
        exception if the user making the request is not a superuser.
        """
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        info = TUserUpdate(u'username', u'secret', u'Username',
                           u'username@example.com')
        self.store.commit()
        with login(u'user', uuid4(), self.transact) as session:
            deferred = self.facade.updateUser(session, info)
            error = yield self.assertFailure(deferred, TPathPermissionDenied)
            self.assertEqual(u'username', error.path)

    @inlineCallbacks
    def testDeleteUser(self):
        """L{FacadeUserMixin.deleteUser} deletes a L{User}."""
        UserAPI().create([(u'test', u'secret', u'name', u'name@example.com')],
                         createPrivateNamespace=False)
        self.store.commit()
        with login(u'fluiddb', self.admin.objectID, self.transact) as session:
            yield self.facade.deleteUser(session, u'test')

        self.store.rollback()
        self.assertIdentical(None, getUser(u'test'))

    @inlineCallbacks
    def testDeleteUserIgnoresCase(self):
        """
        L{FacadeUserMixin.deleteUser} ignores case for the username when
        deleting a user.
        """
        UserAPI().create([(u'test', u'secret', u'name', u'name@example.com')],
                         createPrivateNamespace=False)
        self.store.commit()
        with login(u'fluiddb', self.admin.objectID, self.transact) as session:
            yield self.facade.deleteUser(session, u'tESt')

        self.store.rollback()
        self.assertIdentical(None, getUser(u'test'))

    @inlineCallbacks
    def testDeleteUserWithUnknownUsername(self):
        """
        L{FacadeUserMixin.deleteUser} raises a L{TNoSuchUser} exception if the
        specified L{User.username} doesn't exist.
        """
        self.store.commit()
        with login(u'fluiddb', self.admin.objectID, self.transact) as session:
            deferred = self.facade.deleteUser(session, u'unknown')
            error = yield self.assertFailure(deferred, TNoSuchUser)
            self.assertEqual(u'unknown', error.name)

    @inlineCallbacks
    def testDeleteUserIsDenied(self):
        """
        L{FacadeUserMixin.deleteUser} raises a L{TPathPermissionDenied}
        exception if the user making the request is not a superuser.
        """
        [(objectID, username)] = UserAPI().create(
            [(u'user', u'secret', u'User', u'user@example.com')])
        self.store.commit()
        with login(u'user', objectID, self.transact) as session:
            deferred = self.facade.deleteUser(session, u'doomed')
            error = yield self.assertFailure(deferred, TPathPermissionDenied)
            self.assertEqual(u'doomed', error.path)
