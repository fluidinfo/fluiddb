import json
from uuid import UUID

from fluiddb.cache.user import UserCache, cachingGetUser, CachingUserAPI
from fluiddb.data.system import createSystemData
from fluiddb.data.user import Role, User, createUser
from fluiddb.model.test.test_user import GetUserTestMixin, UserAPITestMixin
from fluiddb.model.user import getUser
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    BrokenCacheResource, CacheResource, ConfigResource, DatabaseResource,
    LoggingResource)


class CachingUserAPITestMixin(object):

    def testSetInvalidatesCachedUsers(self):
        """
        L{CachingUserAPI.set} invalidates L{User}s to ensure the cache is
        always fresh.
        """
        cache = UserCache()
        self.users.create([(u'user', u'hash', u'User', u'user@example.com')])
        user = getUser(u'user')
        cache.save(user)
        self.users.set([(u'user', u'hash2', u'User2', u'user@example.com',
                         Role.USER)])

        cached = cache.get(u'user')
        self.assertIdentical(None, cached.results)
        self.assertEqual(u'user', cached.uncachedValues)

    def testDeleteInvalidatesCachedUsers(self):
        """
        L{CachingUserAPI.delete} invalidates L{User}s to ensure the cache is
        always fresh.
        """
        cache = UserCache()
        self.users.create([(u'user', u'hash', u'User', u'user@example.com')])
        user = getUser(u'user')
        cache.save(user)
        self.users.delete([u'user'])

        cached = cache.get(u'user')
        self.assertIdentical(None, cached.results)
        self.assertEqual(u'user', cached.uncachedValues)


class CachingUserAPITest(UserAPITestMixin, CachingUserAPITestMixin,
                         FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(CachingUserAPITest, self).setUp()
        self.system = createSystemData()
        self.users = CachingUserAPI()


class CachingUserAPIWithBrokenCacheTest(UserAPITestMixin, FluidinfoTestCase):

    resources = [('cache', BrokenCacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(CachingUserAPIWithBrokenCacheTest, self).setUp()
        self.system = createSystemData()
        self.users = CachingUserAPI()


class CachingGetUserTest(GetUserTestMixin, FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(CachingGetUserTest, self).setUp()
        self.getUser = cachingGetUser

    def testCachingGetUserUsesTheCache(self):
        """L{getUser} adds missing L{User}s to the cache."""
        createUser(u'user', u'password', u'User', u'user@example.com')
        user = self.getUser(u'user')
        self.assertIsInstance(user, User)

        # Delete the user from the store
        self.store.remove(user)
        user = self.getUser(u'user')
        self.assertIsInstance(user, User)


class UserCacheTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource(format='%(message)s'))]

    def setUp(self):
        super(UserCacheTest, self).setUp()
        self.userCache = UserCache()

    def testGet(self):
        """L{UserCache.get} returns a L{User} object stored in the cache."""
        userdict = {'id': 1,
                    'objectID': u'04585bec-28cf-4a21-bc3e-081f3ed62680',
                    'username': u'testuser',
                    'passwordHash': 'hash',
                    'fullname': u'Test User',
                    'email': u'test@example.com',
                    'role': Role.ANONYMOUS.id}
        self.cache.set('user:testuser', json.dumps(userdict))
        result = self.userCache.get(u'testuser')
        user = result.results
        self.assertEqual(1, user.id)
        self.assertEqual('04585bec-28cf-4a21-bc3e-081f3ed62680',
                         str(user.objectID))
        self.assertEqual(u'testuser', user.username)
        self.assertEqual('hash', user.passwordHash)
        self.assertEqual(u'Test User', user.fullname)
        self.assertEqual(u'test@example.com', user.email)
        self.assertEqual(Role.ANONYMOUS, user.role)

    def testGetWithNoEmail(self):
        """
        L{UserCache.get} returns a L{User} with C{None} as email if the email
        is not in the cache.
        """
        userdict = {'id': 1,
                    'objectID': u'04585bec-28cf-4a21-bc3e-081f3ed62680',
                    'username': u'testuser',
                    'passwordHash': 'hash',
                    'email': None,
                    'fullname': u'Test User',
                    'role': Role.ANONYMOUS.id}
        self.cache.set('user:testuser', json.dumps(userdict))
        result = self.userCache.get(u'testuser')
        user = result.results
        self.assertEqual(1, user.id)
        self.assertEqual('04585bec-28cf-4a21-bc3e-081f3ed62680',
                         str(user.objectID))
        self.assertEqual(u'testuser', user.username)
        self.assertEqual('hash', user.passwordHash)
        self.assertEqual(u'Test User', user.fullname)
        self.assertEqual(None, user.email)
        self.assertEqual(Role.ANONYMOUS, user.role)

    def testGetWithUnicodeCharacters(self):
        """
        L{UserCache.get} returns a L{User} object stored in the cache with
        unicode values in its username or full name.
        """
        userdict = {'id': 1,
                    'objectID': u'04585bec-28cf-4a21-bc3e-081f3ed62680',
                    'username': u'user\N{HIRAGANA LETTER A}',
                    'passwordHash': 'hash',
                    'fullname': u'\N{HIRAGANA LETTER A}',
                    'email': u'test@example.com',
                    'role': Role.ANONYMOUS.id}
        self.cache.set(u'user:user\N{HIRAGANA LETTER A}', json.dumps(userdict))
        result = self.userCache.get(u'user\N{HIRAGANA LETTER A}')
        user = result.results
        self.assertEqual(1, user.id)
        self.assertEqual('04585bec-28cf-4a21-bc3e-081f3ed62680',
                         str(user.objectID))
        self.assertEqual(u'user\N{HIRAGANA LETTER A}', user.username)
        self.assertEqual('hash', user.passwordHash)
        self.assertEqual(u'\N{HIRAGANA LETTER A}', user.fullname)
        self.assertEqual(u'test@example.com', user.email)
        self.assertEqual(Role.ANONYMOUS, user.role)

    def testGetReturnsUncachedUsername(self):
        """
        If L{UserCache.get} can't find a username in the cache, it returns it
        in the C{uncachedFields} of the L{CacheResult}.
        """
        result = self.userCache.get(u'testuser')
        self.assertIdentical(None, result.results)
        self.assertIdentical(u'testuser', result.uncachedValues)

    def testSave(self):
        """L{UserCache.save} stores a L{User} object in the cache."""
        user = User(u'testuser', 'hash', u'fullname',
                    u'email@example.com', Role.USER)
        user.objectID = UUID('04585bec-28cf-4a21-bc3e-081f3ed62680')
        user.id = 1
        self.userCache.save(user)
        expected = {'username': 'testuser',
                    'objectID': '04585bec-28cf-4a21-bc3e-081f3ed62680',
                    'passwordHash': 'hash',
                    'id': 1,
                    'role': Role.USER.id,
                    'fullname': 'fullname',
                    'email': 'email@example.com'}
        self.assertEqual(expected, json.loads(self.cache.get('user:testuser')))

    def testSaveWithNoneEmail(self):
        """L{UserCache.save} doesn't store the email if it's C{None}."""
        user = User(u'testuser', 'hash', u'fullname', None, Role.USER)
        user.objectID = UUID('04585bec-28cf-4a21-bc3e-081f3ed62680')
        user.id = 1
        self.userCache.save(user)
        expected = {'username': 'testuser',
                    'objectID': '04585bec-28cf-4a21-bc3e-081f3ed62680',
                    'passwordHash': 'hash',
                    'id': 1,
                    'role': Role.USER.id,
                    'email': None,
                    'fullname': 'fullname'}
        self.assertEqual(expected, json.loads(self.cache.get('user:testuser')))

    def testClear(self):
        """L{UserCache.clear} removes users objects from the cache."""
        user = User(u'testuser', 'hash', u'fullname',
                    u'email@example.com', Role.USER)
        user.objectID = UUID('04585bec-28cf-4a21-bc3e-081f3ed62680')
        user.id = 1
        self.userCache.save(user)
        self.assertNotEqual({}, json.loads(self.cache.get('user:testuser')))
        self.userCache.clear(u'testuser')
        self.assertEqual(None, self.cache.get('user:testuser'))
