from datetime import datetime, timedelta
from uuid import uuid4

from fluiddb.data.namespace import createNamespace
from fluiddb.data.recentactivity import getRecentActivity
from fluiddb.data.tag import createTag
from fluiddb.data.user import createUser
from fluiddb.data.value import createTagValue, createAboutTagValue
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import DatabaseResource


class GetRecentActivityTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def setUp(self):
        super(GetRecentActivityTest, self).setUp()
        self.user1 = createUser(u'user1', 'hash', u'User', u'user@example.com')
        self.user2 = createUser(u'user2', 'hash', u'User', u'user@example.com')
        self.user3 = createUser(u'user3', 'hash', u'User', u'user@example.com')
        self.user1.namespaceID = createNamespace(self.user1,
                                                 self.user1.username, None).id
        self.user2.namespaceID = createNamespace(self.user2,
                                                 self.user2.username, None).id
        self.user3.namespaceID = createNamespace(self.user3,
                                                 self.user3.username, None).id
        self.user1tag1 = createTag(self.user1, self.user1.namespace, u'tag1')
        self.user1tag2 = createTag(self.user1, self.user1.namespace, u'tag2')
        self.user2tag1 = createTag(self.user2, self.user2.namespace, u'tag1')
        self.user2tag2 = createTag(self.user2, self.user2.namespace, u'tag2')
        self.user3tag1 = createTag(self.user3, self.user3.namespace, u'tag1')
        self.user3tag2 = createTag(self.user3, self.user3.namespace, u'tag2')

    def makeValue(self, user, tag, objectID, value, delay):
        """
        Helper function used to create a tag value with a given delay in its
        L{TagValue.creationTime}.

        @param user: The L{User} creator of the value.
        @param tag: The L{Tag} for the value.
        @param objectID: The object ID for the value.
        @param value: The value for the tag value.
        @param delay: The delay in seconds for the L{TagValue.creationTime}
            field.
        @return: The {TagValue.creationTime} field of the value.
        """
        value = createTagValue(user.id, tag.id, objectID, value)
        value.creationTime = datetime.now() - timedelta(days=delay)
        return value.creationTime

    def createDirtyObject(self, about=None):
        """Helper function to create an object.

        @param about: Optionally, an about value for the object.
        """
        objectID = uuid4()
        if about:
            createAboutTagValue(objectID, about)
        return objectID

    def testGetRecentActivityWithEmptyArguments(self):
        """
        L{getRecentActivity} returns an empty generator if no values are
        provided.
        """
        result = getRecentActivity(objectIDs=[], usernames=[])
        self.assertEqual([], list(result))

    def testGetRecentActivityByObjectID(self):
        """
        L{getRecentActivity} returns the recent tag values for a given object.
        """
        objectID1 = self.createDirtyObject(u'object1')
        objectID2 = self.createDirtyObject(u'object2')

        time1 = self.makeValue(self.user1, self.user1tag1, objectID1, u'A', 1)
        time2 = self.makeValue(self.user1, self.user1tag2, objectID1, u'B', 2)
        time3 = self.makeValue(self.user2, self.user2tag2, objectID1, u'D', 4)
        self.makeValue(self.user2, self.user2tag1, objectID2, u'C', 3)

        expected = [
            (u'user1/tag1', objectID1, u'object1', u'A', u'user1', time1),
            (u'user1/tag2', objectID1, u'object1', u'B', u'user1', time2),
            (u'user2/tag2', objectID1, u'object1', u'D', u'user2', time3)]
        result = getRecentActivity(objectIDs=[objectID1])
        self.assertEqual(expected, list(result))

    def testGetRecentActivityByMultipleObjectIDs(self):
        """
        L{getRecentActivity} returns the recent tag values for multiple object
        IDs.
        """
        objectID1 = self.createDirtyObject(u'object1')
        objectID2 = self.createDirtyObject(u'object2')
        objectID3 = self.createDirtyObject(u'object3')

        time1 = self.makeValue(self.user1, self.user1tag1, objectID1, u'A', 1)
        time2 = self.makeValue(self.user1, self.user1tag2, objectID2, u'B', 2)
        time3 = self.makeValue(self.user2, self.user2tag1, objectID2, u'C', 3)
        self.makeValue(self.user2, self.user2tag2, objectID3, u'D', 4)

        expected = [
            (u'user1/tag1', objectID1, u'object1', u'A', u'user1', time1),
            (u'user1/tag2', objectID2, u'object2', u'B', u'user1', time2),
            (u'user2/tag1', objectID2, u'object2', u'C', u'user2', time3)]
        result = getRecentActivity(objectIDs=[objectID1, objectID2])
        self.assertEqual(expected, list(result))

    def testGetRecentActivityByObjectIDWithLimit(self):
        """
        L{getRecentActivity} returns only the number of items speficied by the
        C{limit} argument.
        """
        objectID1 = self.createDirtyObject(u'object1')

        time1 = self.makeValue(self.user1, self.user1tag1, objectID1, u'A', 1)
        time2 = self.makeValue(self.user1, self.user1tag2, objectID1, u'B', 2)
        time3 = self.makeValue(self.user2, self.user2tag1, objectID1, u'C', 3)
        self.makeValue(self.user2, self.user2tag2, objectID1, u'D', 4)

        expected = [
            (u'user1/tag1', objectID1, u'object1', u'A', u'user1', time1),
            (u'user1/tag2', objectID1, u'object1', u'B', u'user1', time2),
            (u'user2/tag1', objectID1, u'object1', u'C', u'user2', time3)]
        result = getRecentActivity(objectIDs=[objectID1], limit=3)
        self.assertEqual(expected, list(result))

    def testGetRecentActivityByObjectIDWithoutAboutValues(self):
        """
        If the requested objects don't have C{fluiddb/about} values,
        L{getRecentActivity} returns None as L{AboutTagValue}.
        """
        objectID1 = self.createDirtyObject(None)
        objectID2 = self.createDirtyObject(None)

        time1 = self.makeValue(self.user1, self.user1tag1, objectID1, u'A', 1)
        time2 = self.makeValue(self.user1, self.user1tag2, objectID1, u'B', 2)
        time3 = self.makeValue(self.user2, self.user2tag2, objectID1, u'D', 4)
        self.makeValue(self.user2, self.user2tag1, objectID2, u'C', 3)

        expected = [
            (u'user1/tag1', objectID1, None, u'A', u'user1', time1),
            (u'user1/tag2', objectID1, None, u'B', u'user1', time2),
            (u'user2/tag2', objectID1, None, u'D', u'user2', time3)]
        result = getRecentActivity(objectIDs=[objectID1])
        self.assertEqual(expected, list(result))

    def testGetRecentActivityByUsername(self):
        """
        L{getRecentActivity} returns the recent tag values for a given user.
        """
        objectID1 = self.createDirtyObject(u'object1')
        objectID2 = self.createDirtyObject(u'object2')

        time1 = self.makeValue(self.user1, self.user1tag1, objectID1, u'A', 1)
        time2 = self.makeValue(self.user1, self.user1tag2, objectID1, u'B', 2)
        time3 = self.makeValue(self.user1, self.user1tag1, objectID2, u'D', 4)
        self.makeValue(self.user2, self.user2tag1, objectID1, u'C', 3)

        expected = [
            (u'user1/tag1', objectID1, u'object1', u'A', u'user1', time1),
            (u'user1/tag2', objectID1, u'object1', u'B', u'user1', time2),
            (u'user1/tag1', objectID2, u'object2', u'D', u'user1', time3)]
        result = getRecentActivity(usernames=[u'user1'])
        self.assertEqual(expected, list(result))

    def testGetRecentActivityByMultipleUsernames(self):
        """
        L{getRecentActivity} returns the recent tag values for multiple
        usernames.
        """
        objectID1 = self.createDirtyObject(u'object1')
        objectID2 = self.createDirtyObject(u'object2')

        time1 = self.makeValue(self.user1, self.user1tag1, objectID1, u'A', 1)
        time2 = self.makeValue(self.user1, self.user1tag2, objectID1, u'B', 2)
        time3 = self.makeValue(self.user2, self.user2tag1, objectID2, u'C', 3)
        self.makeValue(self.user3, self.user3tag1, objectID1, u'D', 4)

        expected = [
            (u'user1/tag1', objectID1, u'object1', u'A', u'user1', time1),
            (u'user1/tag2', objectID1, u'object1', u'B', u'user1', time2),
            (u'user2/tag1', objectID2, u'object2', u'C', u'user2', time3)]
        result = getRecentActivity(usernames=[u'user1', u'user2'])
        self.assertEqual(expected, list(result))

    def testGetRecentActivityByUsernameWithLimit(self):
        """
        L{getRecentActivity} returns only the number of items speficied by the
        C{limit} argument.
        """
        objectID1 = self.createDirtyObject(u'object1')
        objectID2 = self.createDirtyObject(u'object2')

        time1 = self.makeValue(self.user1, self.user1tag1, objectID1, u'A', 1)
        time2 = self.makeValue(self.user1, self.user1tag2, objectID1, u'B', 2)
        time3 = self.makeValue(self.user1, self.user1tag1, objectID2, u'C', 3)
        self.makeValue(self.user1, self.user1tag2, objectID2, u'D', 4)

        expected = [
            (u'user1/tag1', objectID1, u'object1', u'A', u'user1', time1),
            (u'user1/tag2', objectID1, u'object1', u'B', u'user1', time2),
            (u'user1/tag1', objectID2, u'object2', u'C', u'user1', time3)]
        result = getRecentActivity(usernames=[u'user1'], limit=3)
        self.assertEqual(expected, list(result))

    def testGetRecentActivityByUsernameWithoutAboutValues(self):
        """
        If the requested objects don't have C{fluiddb/about} values,
        L{getRecentActivity} returns None as L{AboutTagValue}.
        """
        objectID1 = self.createDirtyObject(None)
        objectID2 = self.createDirtyObject(None)

        time1 = self.makeValue(self.user1, self.user1tag1, objectID1, u'A', 1)
        time2 = self.makeValue(self.user1, self.user1tag2, objectID1, u'B', 2)
        time3 = self.makeValue(self.user1, self.user1tag1, objectID2, u'D', 4)
        self.makeValue(self.user2, self.user2tag1, objectID1, u'C', 3)

        expected = [
            (u'user1/tag1', objectID1, None, u'A', u'user1', time1),
            (u'user1/tag2', objectID1, None, u'B', u'user1', time2),
            (u'user1/tag1', objectID2, None, u'D', u'user1', time3)]
        result = getRecentActivity(usernames=[u'user1'])
        self.assertEqual(expected, list(result))

    def testGetRecentActivityByUsernameAndObjectID(self):
        """
        L{getRecentActivity} returns the recent tag values for the given
        objects and usernames.
        """
        objectID1 = self.createDirtyObject(u'object1')
        objectID2 = self.createDirtyObject(u'object2')
        objectID3 = self.createDirtyObject(u'object3')

        time1 = self.makeValue(self.user1, self.user1tag1, objectID1, u'A', 1)
        time2 = self.makeValue(self.user1, self.user1tag2, objectID1, u'B', 2)
        time3 = self.makeValue(self.user2, self.user2tag1, objectID2, u'C', 3)
        time4 = self.makeValue(self.user2, self.user2tag2, objectID2, u'D', 4)
        self.makeValue(self.user3, self.user3tag1, objectID3, u'E', 5)
        self.makeValue(self.user3, self.user3tag2, objectID3, u'F', 6)

        expected = [
            (u'user1/tag1', objectID1, u'object1', u'A', u'user1', time1),
            (u'user1/tag2', objectID1, u'object1', u'B', u'user1', time2),
            (u'user2/tag1', objectID2, u'object2', u'C', u'user2', time3),
            (u'user2/tag2', objectID2, u'object2', u'D', u'user2', time4)]
        result = getRecentActivity(objectIDs=[objectID1, objectID2],
                                   usernames=[u'user1', u'user2'])
        self.assertEqual(expected, list(result))
