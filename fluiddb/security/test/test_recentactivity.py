from uuid import uuid4

from fluiddb.cache.object import CachingObjectAPI
from fluiddb.cache.test.test_recentactivity import (
    CachingRecentActivityAPITestMixin)
from fluiddb.cache.value import CachingTagValueAPI
from fluiddb.data.system import createSystemData
from fluiddb.model.object import ObjectAPI
from fluiddb.model.test.test_recentactivity import RecentActivityAPITestMixin
from fluiddb.model.user import UserAPI, getUser
from fluiddb.model.value import TagValueAPI
from fluiddb.security.recentactivity import SecureRecentActivityAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    BrokenCacheResource, CacheResource, ConfigResource, DatabaseResource,
    IndexResource, LoggingResource)
from fluiddb.cache.permission import CachingPermissionAPI
from fluiddb.data.permission import Operation, Policy


class SecureRecentActivityAPITest(RecentActivityAPITestMixin,
                                  CachingRecentActivityAPITestMixin,
                                  FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('client', IndexResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureRecentActivityAPITest, self).setUp()
        createSystemData()
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        self.user = getUser(u'user')
        self.recentActivity = SecureRecentActivityAPI(self.user)

    def getObjectAPI(self, user):
        """Get an L{CachingObjectAPI} instance for the specified user.

        @param user: The L{User} to configure the L{CachingObjectAPI}
            instance.
        @return: An L{CachingObjectAPI} instance.
        """
        return CachingObjectAPI(user)

    def getTagValueAPI(self, user):
        """Get a L{TagValueAPI} instance for the specified user.

        @param user: The L{User} to configure the L{TagValueAPI} instance.
        @return: A L{TagValueAPI} instance.
        """
        return CachingTagValueAPI(user)


class SecureRecentActivityAPIWithBrokenCacheTest(RecentActivityAPITestMixin,
                                                 FluidinfoTestCase):

    resources = [('cache', BrokenCacheResource()),
                 ('client', IndexResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureRecentActivityAPIWithBrokenCacheTest, self).setUp()
        createSystemData()
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        self.user = getUser(u'user')
        self.recentActivity = SecureRecentActivityAPI(self.user)

    def getObjectAPI(self, user):
        """Get an L{CachingObjectAPI} instance for the specified user.

        @param user: The L{User} to configure the L{CachingObjectAPI}
            instance.
        @return: An L{CachingObjectAPI} instance.
        """
        return CachingObjectAPI(user)

    def getTagValueAPI(self, user):
        """Get a L{TagValueAPI} instance for the specified user.

        @param user: The L{User} to configure the L{TagValueAPI} instance.
        @return: A L{TagValueAPI} instance.
        """
        return CachingTagValueAPI(user)


class SecureRecentActivityAPIWithAnonymousRoleTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('client', IndexResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureRecentActivityAPIWithAnonymousRoleTest, self).setUp()
        system = createSystemData()
        self.anon = system.users[u'anon']
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        self.user = getUser(u'user')
        self.recentActivity = SecureRecentActivityAPI(self.anon)
        self.permissions = CachingPermissionAPI(self.user)

    def testGetForObjectsReturnsOnlyAllowedTags(self):
        """
        L{SecureRecentActivityAPI.getForObjects} will return all the tags for
        which the user has C{Operation.READ_TAG_VALUE} permissions, but not
        those for which the user doesn't have.
        """
        tagValues = TagValueAPI(self.user)
        objectID1 = ObjectAPI(self.user).create(u'object1')
        objectID2 = uuid4()

        # Use commit() frequently to have different timestamps on each value.
        self.store.commit()
        tagValues.set({objectID1: {u'user/tag1': u'A'}})
        self.store.commit()
        tagValues.set({objectID1: {u'user/tag2': u'B'}})
        self.store.commit()
        tagValues.set({objectID2: {u'user/tag1': u'C'}})
        self.store.commit()
        tagValues.set({objectID2: {u'user/tag2': u'D'}})
        self.store.commit()
        tagValues.set({uuid4(): {u'user/tag1': u'E'}})
        self.store.commit()
        tagValues.set({uuid4(): {u'user/tag2': u'F'}})
        self.store.commit()

        self.permissions.set([(u'user/tag2', Operation.READ_TAG_VALUE,
                               Policy.OPEN, [u'anon'])])

        expected = [
            (u'user/tag1', objectID2, None, u'C', u'user'),
            (u'user/tag1', objectID1, u'object1', u'A', u'user'),
            (u'fluiddb/about', objectID1, u'object1', u'object1', u'fluiddb')]

        result = self.recentActivity.getForObjects([objectID1, objectID2])

        # Remove the creation times from the result, with the order is enough.
        result = [(path, objectID, about, value, username)
                  for path, objectID, about, value, username, time in result]
        self.assertEqual(expected, result)

    def testGetForUsersReturnsOnlyAllowedTags(self):
        """
        L{SecureRecentActivityAPI.getForUsers} will return all the tags for
        which the user has C{Operation.READ_TAG_VALUE} permissions, but not
        those for which the user doesn't have.
        """
        tagValues = TagValueAPI(self.user)
        objectID1 = ObjectAPI(self.user).create(u'object1')
        objectID2 = uuid4()

        # Use commit() frequently to have different timestamps on each value.
        self.store.commit()
        tagValues.set({objectID1: {u'user/tag1': u'A'}})
        self.store.commit()
        tagValues.set({objectID1: {u'user/tag2': u'B'}})
        self.store.commit()

        UserAPI().create([(u'user2', u'secret', u'User', u'user@example.com')])
        tagValues = TagValueAPI(getUser(u'user2'))

        tagValues.set({objectID1: {u'user2/tag1': u'C'}})
        self.store.commit()
        tagValues.set({objectID2: {u'user2/tag2': u'D'}})
        self.store.commit()

        UserAPI().create([(u'user3', u'secret', u'User', u'user@example.com')])
        tagValues = TagValueAPI(getUser(u'user3'))

        tagValues.set({objectID1: {u'user3/tag1': u'C'}})
        self.store.commit()
        tagValues.set({objectID2: {u'user3/tag2': u'D'}})
        self.store.commit()

        self.permissions.set([(u'user/tag2', Operation.READ_TAG_VALUE,
                               Policy.OPEN, [u'anon']),
                              (u'user2/tag2', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, [])])

        expected = [
            (u'user2/tag1', objectID1, u'object1', u'C', u'user2'),
            (u'user/tag1', objectID1, u'object1', u'A', u'user')]

        result = self.recentActivity.getForUsers([u'user', u'user2'])
        # Remove the creation times from the result, with the order is enough.
        result = [(path, objectID, about, value, username)
                  for path, objectID, about, value, username, time in result]
        self.assertEqual(expected, result)


class SecureRecentActivityAPIWithUserRoleTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('client', IndexResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureRecentActivityAPIWithUserRoleTest, self).setUp()
        createSystemData()
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        self.user = getUser(u'user')
        self.recentActivity = SecureRecentActivityAPI(self.user)
        self.permissions = CachingPermissionAPI(self.user)

    def testGetForObjectsReturnsOnlyAllowedTags(self):
        """
        L{SecureRecentActivityAPI.getForObjects} will return all the tags for
        which the user has C{Operation.READ_TAG_VALUE} permissions, but not
        those for which the user doesn't have.
        """
        tagValues = TagValueAPI(self.user)
        objectID1 = ObjectAPI(self.user).create(u'object1')
        objectID2 = uuid4()

        # Use commit() frequently to have different timestamps on each value.
        self.store.commit()
        tagValues.set({objectID1: {u'user/tag1': u'A'}})
        self.store.commit()
        tagValues.set({objectID1: {u'user/tag2': u'B'}})
        self.store.commit()
        tagValues.set({objectID2: {u'user/tag1': u'C'}})
        self.store.commit()
        tagValues.set({objectID2: {u'user/tag2': u'D'}})
        self.store.commit()
        tagValues.set({uuid4(): {u'user/tag1': u'E'}})
        self.store.commit()
        tagValues.set({uuid4(): {u'user/tag2': u'F'}})
        self.store.commit()

        self.permissions.set([(u'user/tag2', Operation.READ_TAG_VALUE,
                               Policy.OPEN, [u'user'])])

        expected = [
            (u'user/tag1', objectID2, None, u'C', u'user'),
            (u'user/tag1', objectID1, u'object1', u'A', u'user'),
            (u'fluiddb/about', objectID1, u'object1', u'object1', u'fluiddb')]

        result = self.recentActivity.getForObjects([objectID1, objectID2])

        # Remove the creation times from the result, with the order is enough.
        result = [(path, objectID, about, value, username)
                  for path, objectID, about, value, username, time in result]
        self.assertEqual(expected, result)

    def testGetForUsersReturnsOnlyAllowedTags(self):
        """
        L{SecureRecentActivityAPI.getForUsers} will return all the tags for
        which the user has C{Operation.READ_TAG_VALUE} permissions, but not
        those for which the user doesn't have.
        """
        tagValues = TagValueAPI(self.user)
        objectID1 = ObjectAPI(self.user).create(u'object1')
        objectID2 = uuid4()

        # Use commit() frequently to have different timestamps on each value.
        self.store.commit()
        tagValues.set({objectID1: {u'user/tag1': u'A'}})
        self.store.commit()
        tagValues.set({objectID1: {u'user/tag2': u'B'}})
        self.store.commit()

        UserAPI().create([(u'user2', u'secret', u'User', u'user@example.com')])
        tagValues = TagValueAPI(getUser(u'user2'))

        tagValues.set({objectID1: {u'user2/tag1': u'C'}})
        self.store.commit()
        tagValues.set({objectID2: {u'user2/tag2': u'D'}})
        self.store.commit()

        UserAPI().create([(u'user3', u'secret', u'User', u'user@example.com')])
        tagValues = TagValueAPI(getUser(u'user3'))

        tagValues.set({objectID1: {u'user3/tag1': u'C'}})
        self.store.commit()
        tagValues.set({objectID2: {u'user3/tag2': u'D'}})
        self.store.commit()

        self.permissions.set([(u'user/tag2', Operation.READ_TAG_VALUE,
                               Policy.OPEN, [u'user']),
                              (u'user2/tag2', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, [])])

        expected = [
            (u'user2/tag1', objectID1, u'object1', u'C', u'user2'),
            (u'user/tag1', objectID1, u'object1', u'A', u'user')]

        result = self.recentActivity.getForUsers([u'user', u'user2'])
        # Remove the creation times from the result, with the order is enough.
        result = [(path, objectID, about, value, username)
                  for path, objectID, about, value, username, time in result]
        self.assertEqual(expected, result)


class SecureRecentActivityAPIWithSuperuserRoleTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('client', IndexResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureRecentActivityAPIWithSuperuserRoleTest, self).setUp()
        system = createSystemData()
        superuser = system.users[u'fluiddb']
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        self.user = getUser(u'user')
        self.recentActivity = SecureRecentActivityAPI(superuser)
        self.permissions = CachingPermissionAPI(self.user)

    def testGetForObjectsReturnsAllTags(self):
        """
        L{SecureRecentActivityAPI.getForObjects} returns all the tags for the
        superuser.
        """
        tagValues = TagValueAPI(self.user)
        objectID1 = ObjectAPI(self.user).create(u'object1')
        objectID2 = uuid4()

        # Use commit() frequently to have different timestamps on each value.
        self.store.commit()
        tagValues.set({objectID1: {u'user/tag1': u'A'}})
        self.store.commit()
        tagValues.set({objectID1: {u'user/tag2': u'B'}})
        self.store.commit()
        tagValues.set({objectID2: {u'user/tag1': u'C'}})
        self.store.commit()
        tagValues.set({objectID2: {u'user/tag2': u'D'}})
        self.store.commit()
        tagValues.set({uuid4(): {u'user/tag1': u'E'}})
        self.store.commit()
        tagValues.set({uuid4(): {u'user/tag2': u'F'}})
        self.store.commit()

        self.permissions.set([(u'user/tag2', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, [])])

        expected = [
            (u'user/tag2', objectID2, None, u'D', u'user'),
            (u'user/tag1', objectID2, None, u'C', u'user'),
            (u'user/tag2', objectID1, u'object1', u'B', u'user'),
            (u'user/tag1', objectID1, u'object1', u'A', u'user'),
            (u'fluiddb/about', objectID1, u'object1', u'object1', u'fluiddb')]

        result = self.recentActivity.getForObjects([objectID1, objectID2])

        # Remove the creation times from the result, with the order is enough.
        result = [(path, objectID, about, value, username)
                  for path, objectID, about, value, username, time in result]
        self.assertEqual(expected, result)

    def testGetForUsersReturnsOnlyAllowedTags(self):
        """
        L{SecureRecentActivityAPI.getForUser} returns all the tags for the
        superuser.
        """
        tagValues = TagValueAPI(self.user)
        objectID1 = ObjectAPI(self.user).create(u'object1')
        objectID2 = uuid4()

        # Use commit() frequently to have different timestamps on each value.
        self.store.commit()
        tagValues.set({objectID1: {u'user/tag1': u'A'}})
        self.store.commit()
        tagValues.set({objectID1: {u'user/tag2': u'B'}})
        self.store.commit()

        UserAPI().create([(u'user2', u'secret', u'User', u'user@example.com')])
        tagValues = TagValueAPI(getUser(u'user2'))

        tagValues.set({objectID1: {u'user2/tag1': u'C'}})
        self.store.commit()
        tagValues.set({objectID2: {u'user2/tag2': u'D'}})
        self.store.commit()

        UserAPI().create([(u'user3', u'secret', u'User', u'user@example.com')])
        tagValues = TagValueAPI(getUser(u'user3'))

        tagValues.set({objectID1: {u'user3/tag1': u'C'}})
        self.store.commit()
        tagValues.set({objectID2: {u'user3/tag2': u'D'}})
        self.store.commit()

        self.permissions.set([(u'user/tag2', Operation.READ_TAG_VALUE,
                               Policy.OPEN, [u'user']),
                              (u'user2/tag2', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, [])])

        expected = [
            (u'user2/tag2', objectID2, None, u'D', u'user2'),
            (u'user2/tag1', objectID1, u'object1', u'C', u'user2'),
            (u'user/tag2', objectID1, u'object1', u'B', u'user'),
            (u'user/tag1', objectID1, u'object1', u'A', u'user')]

        result = self.recentActivity.getForUsers([u'user', u'user2'])
        # Remove the creation times from the result, with the order is enough.
        result = [(path, objectID, about, value, username)
                  for path, objectID, about, value, username, time in result]
        self.assertEqual(expected, result)
