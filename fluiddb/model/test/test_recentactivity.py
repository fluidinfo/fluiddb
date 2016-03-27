from uuid import uuid4

from fluiddb.data.exceptions import UnknownUserError
from fluiddb.data.system import createSystemData
from fluiddb.model.object import ObjectAPI
from fluiddb.model.recentactivity import RecentActivityAPI
from fluiddb.model.user import getUser, UserAPI
from fluiddb.model.value import TagValueAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import DatabaseResource, ConfigResource


class RecentActivityAPITestMixin(object):

    def testGetForObjects(self):
        """
        L{RecentActivityAPI.getForObjects} returns data about recent tag values
        for the given objects.
        """
        tagValues = self.getTagValueAPI(self.user)
        objectID1 = self.getObjectAPI(self.user).create(u'object1')
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

    def testGetForObjectsWithNoValues(self):
        """
        L{SecureRecentActivityAPI.getForObjects} return an empty list if the
        given list of objects is empty.
        """
        result = self.recentActivity.getForObjects([])
        self.assertEqual([], result)

    def testGetFromObjectsWithBinaryValue(self):
        """
        L{RecentActivityAPI.getForObjects} returns binary values using the
        expected format.
        """
        tagValues = TagValueAPI(self.user)
        objectID = uuid4()

        values = {objectID: {u'user/tag': {u'mime-type': u'text/plain',
                                           u'contents': 'Hello, world!'}}}
        tagValues.set(values)
        self.store.commit()

        value = {u'value-type': u'text/plain',
                 u'size': 13}
        expected = [(u'user/tag', objectID, None, value, u'user')]

        result = self.recentActivity.getForObjects([objectID])

        # Remove the creation times from the result, with the order is enough.
        result = [(path, objectID, about, value, username)
                  for path, objectID, about, value, username, time in result]
        self.assertEqual(expected, result)

    def testGetFromUsers(self):
        """
        L{RecentActivityAPI.getForUsers} returns data about recent tag values
        for the given users.
        """
        tagValues = self.getTagValueAPI(self.user)
        objectID1 = self.getObjectAPI(self.user).create(u'object1')
        objectID2 = uuid4()

        # Use commit() frequently to have different timestamps on each value.
        self.store.commit()
        tagValues.set({objectID1: {u'user/tag1': u'A'}})
        self.store.commit()
        tagValues.set({objectID1: {u'user/tag2': u'B'}})
        self.store.commit()

        UserAPI().create([(u'user2', u'secret', u'User', u'user@example.com')])
        tagValues = self.getTagValueAPI(getUser(u'user2'))

        tagValues.set({objectID1: {u'user2/tag1': u'C'}})
        self.store.commit()
        tagValues.set({objectID2: {u'user2/tag2': u'D'}})
        self.store.commit()

        UserAPI().create([(u'user3', u'secret', u'User', u'user@example.com')])
        tagValues = self.getTagValueAPI(getUser(u'user3'))

        tagValues.set({objectID1: {u'user3/tag1': u'C'}})
        self.store.commit()
        tagValues.set({objectID2: {u'user3/tag2': u'D'}})
        self.store.commit()

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

    def testGetForObjectsWithUnknownObjects(self):
        """
        L{CachingRecentActivityAPI.getForObjects} returns an empty list if no
        matching data is available for the specified object IDs.
        """
        self.assertEqual([], self.recentActivity.getForObjects([uuid4()]))

    def testGetForUsersWithUnknownUsers(self):
        """
        L{RecentActivityAPI.getForUsers} raises a L{UnknownUserError} if any
        of the provided users doesn't exist.
        """
        self.assertRaises(UnknownUserError,
                          self.recentActivity.getForUsers, [u'unknown'])

    def testGetForUsersWithNoValues(self):
        """
        L{SecureRecentActivityAPI.getForUsers} return an empty list if the
        given list of usernames is empty.
        """
        result = self.recentActivity.getForUsers([])
        self.assertEqual([], result)

    def testGetFromUsersWithBinaryValue(self):
        """
        L{RecentActivityAPI.getForUsers} returns binary values using the
        expected format.
        """
        tagValues = TagValueAPI(self.user)
        objectID = uuid4()

        values = {objectID: {u'user/tag': {u'mime-type': u'text/plain',
                                           u'contents': 'Hello, world!'}}}
        tagValues.set(values)
        self.store.commit()

        value = {u'value-type': u'text/plain',
                 u'size': 13}
        expected = [(u'user/tag', objectID, None, value, u'user')]

        result = self.recentActivity.getForUsers([u'user'])

        # Remove the creation times from the result, with the order is enough.
        result = [(path, objectID, about, value, username)
                  for path, objectID, about, value, username, time in result]
        self.assertEqual(expected, result)


class RecentActivityAPITest(RecentActivityAPITestMixin, FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(RecentActivityAPITest, self).setUp()
        createSystemData()
        self.recentActivity = RecentActivityAPI()
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        self.user = getUser(u'user')

    def getObjectAPI(self, user):
        """Get an L{ObjectAPI} instance for the specified user.

        @param user: The L{User} to configure the L{ObjectAPI} instance.
        @return: An L{ObjectAPI} instance.
        """
        return ObjectAPI(user)

    def getTagValueAPI(self, user):
        """Get a L{TagValueAPI} instance for the specified user.

        @param user: The L{User} to configure the L{TagValueAPI} instance.
        @return: A L{TagValueAPI} instance.
        """
        return TagValueAPI(user)
