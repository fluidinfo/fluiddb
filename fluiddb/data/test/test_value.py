from datetime import datetime, timedelta
from hashlib import sha256
import sys
from uuid import uuid4

from storm.exceptions import IntegrityError
from storm.store import ResultSet

from fluiddb.data.namespace import createNamespace
from fluiddb.data.tag import createTag
from fluiddb.data.user import createUser
from fluiddb.data.value import (
    TagValue, TagValueCollection, AboutTagValue, createAboutTagValue,
    createTagValue, getAboutTagValues, getTagPathsAndObjectIDs,
    getTagPathsForObjectIDs, getTagValues, getObjectIDs, OpaqueValue,
    OpaqueValueLink, createOpaqueValue, getOpaqueValues)
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import DatabaseResource


class GetTagPathsForObjectIDsTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testGetTagPathsForObjectIDsWithoutData(self):
        """
        L{getTagPathsForObjectIDs} doesn't return any results if no object IDs
        are provided.
        """
        self.assertEqual([], list(getTagPathsForObjectIDs([])))

    def testGetTagPathsForObjectIDsWithUnknownObjectID(self):
        """
        L{getTagPathsForObjectIDs} doesn't return any results if unknown
        object IDs are provided.
        """
        user = createUser(u'user', u'secret', u'User', u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag = createTag(user, user.namespace, u'name1')
        createTag(user, user.namespace, u'name2')
        createTagValue(user.id, tag.id, uuid4(), 42)
        self.assertEqual([], list(getTagPathsForObjectIDs([uuid4()])))

    def testGetTagPathsForObjectIDs(self):
        """
        L{getTagPathsForObjectIDs} returns the unique set of L{Tag.path}s that
        match the specified object IDs.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        user = createUser(u'user', u'secret', u'User', u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag = createTag(user, user.namespace, u'name1')
        createTag(user, user.namespace, u'name2')
        createTagValue(user.id, tag.id, objectID1, 42)
        createTagValue(user.id, tag.id, objectID2, 17)
        result = getTagPathsForObjectIDs([objectID1, objectID2])
        self.assertEqual(u'user/name1', result.one())


class GetTagPathsAndObjectIDsTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testGetTagPathsAndObjectIDsWithoutData(self):
        """
        L{getTagPathsAndObjectIDs} doesn't return any results if no object IDs
        are provided.
        """
        self.assertEqual([], list(getTagPathsAndObjectIDs([])))

    def testGetTagPathsAndObjectIDsWithUnknownObjectID(self):
        """
        L{getTagPathsAndObjectIDs} doesn't return any results if unknown
        object IDs are provided.
        """
        user = createUser(u'user', u'secret', u'User', u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag = createTag(user, user.namespace, u'name1')
        createTag(user, user.namespace, u'name2')
        createTagValue(user.id, tag.id, uuid4(), 42)
        self.assertEqual([], list(getTagPathsAndObjectIDs([uuid4()])))

    def testGetTagPathsAndObjectIDs(self):
        """
        L{getTagPathsAndObjectIDs} returns a C{(Tag.path, objectID)} 2-tuples
        that match the specified object IDs.
        """
        objectID = uuid4()
        user = createUser(u'user', u'secret', u'User', u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag = createTag(user, user.namespace, u'name1')
        createTag(user, user.namespace, u'name2')
        createTagValue(user.id, tag.id, objectID, 42)
        createTagValue(user.id, tag.id, uuid4(), 17)
        self.assertEqual((tag.path, objectID),
                         getTagPathsAndObjectIDs([objectID]).one())


class GetObjectsIDsTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testGetObjectIDsWithoutData(self):
        """
        L{getObjectIDs} doesn't return any results if no paths are provided.
        """
        self.assertEqual([], list(getObjectIDs([])))

    def testGetObjectIDsWithUnknownObjectID(self):
        """
        L{getObjectIDs} doesn't return any results if unknown tag paths are
        provided.
        """
        user = createUser(u'user', u'secret', u'User', u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag = createTag(user, user.namespace, u'name1')
        createTagValue(user.id, tag.id, uuid4(), 42)
        self.assertEqual([], list(getObjectIDs([u'user/name2'])))

    def testGetObjectIDs(self):
        """
        L{getObjectIDs} returns a sequence of object IDs that match the
        specified paths.
        """
        objectID1 = uuid4()
        user = createUser(u'user', u'secret', u'User', u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag1 = createTag(user, user.namespace, u'name1')
        tag2 = createTag(user, user.namespace, u'name2')
        createTagValue(user.id, tag1.id, objectID1, 42)
        createTagValue(user.id, tag2.id, uuid4(), 17)
        self.assertEqual(objectID1, getObjectIDs([u'user/name1']).one())


class CreateTagValueTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testCreateTagValue(self):
        """L{createTagValue} creates a new L{TagValue}."""
        objectID = uuid4()
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag = createTag(user, user.namespace, u'name')
        value = createTagValue(user.id, tag.id, objectID, 42)
        self.assertIdentical(user, value.creator)
        self.assertEqual(tag, value.tag)
        self.assertEqual(objectID, value.objectID)
        self.assertEqual(42, value.value)

    def testCreateTagValueAddsToDatabase(self):
        """
        L{createTagValue} automatically adds the new L{TagValue} to the
        database.
        """
        objectID = uuid4()
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag = createTag(user, user.namespace, u'name')
        value = createTagValue(user.id, tag.id, objectID, 42)
        self.assertIdentical(value, self.store.find(TagValue).one())


class GetTagValuesTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testGetTagValues(self):
        """
        L{getTagValues} returns all L{TagValue}s in the database, by default.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag = createTag(user, user.namespace, u'name')
        value1 = self.store.add(TagValue(user.id, tag.id, objectID1, None))
        value2 = self.store.add(TagValue(user.id, tag.id, objectID2, 42))
        self.assertEqual(sorted([value1, value2]), sorted(getTagValues()))

    def testGetTagValuesWithTagIDsAndObjectIDs(self):
        """
        When C{(Tag.id, object ID)} 2-tuples are provided L{getTagValues}
        returns matching L{TagValue}s.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag = createTag(user, user.namespace, u'name')
        value = self.store.add(TagValue(user.id, tag.id, objectID1, None))
        self.store.add(TagValue(user.id, tag.id, objectID2, 42))
        self.assertEqual(value, getTagValues([(objectID1, tag.id)]).one())


class TagValueCollectionTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testValuesWithoutData(self):
        """
        L{TagValueCollection.values} returns a L{ResultSet} that doesn't
        contain any values if no data is available.
        """
        collection = TagValueCollection()
        result = collection.values()
        self.assertIdentical(ResultSet, type(result))
        self.assertEqual([], list(result))

    def testValues(self):
        """
        L{TagValueCollection.values} returns a L{ResultSet} that yields all
        available L{Tag} values, when no filtering has been applied.
        """
        objectID = uuid4()
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        namespace = createNamespace(user, u'name')
        tag1 = createTag(user, namespace, u'tag1')
        tag2 = createTag(user, namespace, u'tag2')
        tagValue1 = TagValue(user.id, tag1.id, objectID, 42)
        tagValue2 = TagValue(user.id, tag2.id, objectID, u'foo')
        self.store.add(tagValue1)
        self.store.add(tagValue2)
        collection = TagValueCollection()
        self.assertEqual(sorted([(tag1, tagValue1),
                                 (tag2, tagValue2)]),
                         sorted(collection.values()))

    def testValuesWithObjectIDs(self):
        """
        A L{TagValueCollection} filtered by object ID only contains values for
        L{Tag}s with a matching object ID.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        tagValue1 = TagValue(user.id, tag.id, objectID1, None)
        tagValue2 = TagValue(user.id, tag.id, objectID2, 42)
        self.store.add(tagValue1)
        self.store.add(tagValue2)
        collection = TagValueCollection(objectIDs=[objectID1])
        self.assertEqual([(tag, tagValue1)],
                         list(collection.values()))

    def testValuesWithPaths(self):
        """
        A L{TagValueCollection} filtered by path only contains values for
        L{Tag}s with a matching path.
        """
        objectID = uuid4()
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        namespace = createNamespace(user, u'name')
        tag1 = createTag(user, namespace, u'tag1')
        tag2 = createTag(user, namespace, u'tag2')
        self.store.add(TagValue(user.id, tag1.id, objectID, None))
        self.store.add(TagValue(user.id, tag2.id, objectID, 42))
        collection = TagValueCollection(paths=[u'name/tag1'])
        (tag, tagValue) = collection.values().one()
        self.assertEqual(objectID, tagValue.objectID)
        self.assertEqual(u'name/tag1', tag.path)
        self.assertEqual(None, tagValue.value)

    def testValuesWithCreatedBeforeTime(self):
        """
        A L{TagValueCollection} filtered by creation time only contains values
        for L{TagValue}s created before the specified time.
        """
        objectID = uuid4()
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        namespace = createNamespace(user, u'name')
        tag1 = createTag(user, namespace, u'tag1')
        tag2 = createTag(user, namespace, u'tag2')
        self.store.add(TagValue(user.id, tag1.id, objectID, None))
        value = self.store.add(TagValue(user.id, tag2.id, objectID, 42))
        value.creationTime = datetime.utcnow() - timedelta(hours=24)
        collection = TagValueCollection(
            createdBeforeTime=datetime.utcnow() - timedelta(hours=12))
        (tag, tagValue) = collection.values().one()
        self.assertEqual(objectID, tagValue.objectID)
        self.assertEqual(u'name/tag2', tag.path)
        self.assertEqual(42, tagValue.value)


class TagValueSchemaTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testUniqueTagAndObjectID(self):
        """
        An C{IntegrityError} is raised if a L{TagValue} with duplicate
        L{Tag.id} and object ID values is added to the database.
        """
        user = createUser(u'name', u'password', u'User', u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag = createTag(user, user.namespace, u'tag')
        objectID = uuid4()
        self.store.add(TagValue(user.id, tag.id, objectID, None))
        self.store.flush()
        self.store.add(TagValue(user.id, tag.id, objectID, None))
        self.assertRaises(IntegrityError, self.store.flush)
        self.store.rollback()

    def testNoneValue(self):
        """A L{TagValue} can store a C{None} value."""
        objectID = uuid4()
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        self.store.add(TagValue(user.id, tag.id, objectID, None))

    def testBoolValue(self):
        """A L{TagValue} can store a C{bool} value."""
        objectID = uuid4()
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        self.store.add(TagValue(user.id, tag.id, objectID, True))

    def testIntValue(self):
        """A L{TagValue} can store an C{int} value."""
        objectID = uuid4()
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        self.store.add(TagValue(user.id, tag.id, objectID, 42))

    def testLongValue(self):
        """A L{TagValue} can store a C{long} value."""
        objectID = uuid4()
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        self.store.add(TagValue(user.id, tag.id, objectID, sys.maxint + 1))

    def testFloatValue(self):
        """A L{TagValue} can store a C{float} value."""
        objectID = uuid4()
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        self.store.add(TagValue(user.id, tag.id, objectID, 42.1))

    def testUnicodeValue(self):
        """A L{TagValue} can store a C{unicode} value."""
        objectID = uuid4()
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        self.store.add(TagValue(user.id, tag.id, objectID, u'foo'))

    def testUnicodeValueWithIllegalXMLCharacter(self):
        """
        A L{TagValue} can store a C{unicode} value even if it contains illegal
        XML characters.
        """
        objectID = uuid4()
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        self.store.add(TagValue(user.id, tag.id, objectID, u'foo \uFFFE'))

    def testUnicodeSetValue(self):
        """A L{TagValue} can store a C{list} of C{unicode} values."""
        objectID = uuid4()
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        self.store.add(TagValue(user.id, tag.id, objectID, [u'foo', u'bar']))

    def testBinaryValue(self):
        """A L{TagValue} can store a binary value."""
        objectID = uuid4()
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        self.store.add(TagValue(user.id, tag.id, objectID,
                                {'mime-type': 'text/html',
                                 'size': 123}))

    def testBinaryValueWithMissingField(self):
        """
        A C{ValueError} is raised if any of the required fields in a C{dict}
        representing a binary L{TagValue}.
        """
        objectID = uuid4()
        user = createUser(u'username', u'password', u'User', u'user@foo.org')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        self.assertRaises(ValueError, TagValue, user.id, tag.id, objectID,
                          {'size': 123})
        self.assertRaises(ValueError, TagValue, user.id, tag.id, objectID,
                          {'mime-type': 'text/html'})

    def testBinaryValueWithUnexpectedField(self):
        """
        A C{ValueError} is raised if an unexpected field is present in a
        C{dict} representing a binary L{TagValue}.
        """
        objectID = uuid4()
        user = createUser(u'username', u'password', u'User', u'user@foo.org')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        self.assertRaises(ValueError, TagValue, user.id, tag.id, objectID,
                          {'mime-type': 'text/html',
                           'file-id': 'foo.html',
                           'size': 123,
                           'unexpected': 'unexpected'})


class OpaqueValueSchemaTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testUniqueFileIDs(self):
        """
        An C{IntegrityError} is raised if an L{OpaqueValue} with the same
        fileID is added to the database.
        """
        fileID = 'f' * 64
        self.store.add(OpaqueValue(fileID, 'content'))
        self.store.flush()
        self.store.add(OpaqueValue(fileID, 'content'))
        self.assertRaises(IntegrityError, self.store.flush)
        self.store.rollback()


class OpaqueValueLinkSchemaTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testUniqueFileIDAndValueID(self):
        """
        An C{IntegrityError} is raised if an L{OpaqueValueLink} with the same
        fileID and valueID is added to the database. Duplicated C{tag_id} or
        C{file_id} can be added as long as the pair is unique.
        """
        user = createUser(u'name', u'password', u'User', u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag = createTag(user, user.namespace, u'tag')
        value1 = TagValue(user.id, tag.id, uuid4(), None)
        value2 = TagValue(user.id, tag.id, uuid4(), None)
        self.store.add(value1)
        self.store.add(value2)
        self.store.flush()

        fileID1 = 'f' * 64
        fileID2 = '0' * 64

        self.store.add(OpaqueValue(fileID1, 'content1'))
        self.store.add(OpaqueValue(fileID2, 'content2'))

        # Add an initial link
        self.store.add(OpaqueValueLink(value1.id, fileID1))

        # Add link with the same fileID but different valueID. It should work.
        self.store.add(OpaqueValueLink(value2.id, fileID1))
        # Add link with the same valueID but different fileID. It should work.
        self.store.add(OpaqueValueLink(value1.id, fileID2))
        self.store.flush()

        # Add link with same fileID and valueID. It should fail.
        self.store.add(OpaqueValueLink(value1.id, fileID1))
        self.assertRaises(IntegrityError, self.store.flush)
        self.store.rollback()

    def testRemoveTagValueRemovesLink(self):
        """
        If a L{TagValue} referenced by a L{OpaqueValueLink} is deleted, the
        referenced link is removed too.
        """
        user = createUser(u'name', u'password', u'User', u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag = createTag(user, user.namespace, u'tag')
        value = TagValue(user.id, tag.id, uuid4(), None)
        self.store.add(value)
        self.store.flush()
        fileID = 'f' * 64
        self.store.add(OpaqueValue(fileID, 'content'))
        self.store.add(OpaqueValueLink(value.id, fileID))
        self.store.remove(value)
        self.store.flush()
        result = self.store.find(OpaqueValueLink,
                                 OpaqueValueLink.fileID == fileID).one()
        self.assertIdentical(None, result)

    def testRemoveOpaqueValueRaisesError(self):
        """
        If an L{OpaqueValue} is removed while there is an existent
        L{OpaqueValueLink} entry in the database, an L{IntegrityError} is
        raised.
        """
        user = createUser(u'name', u'password', u'User', u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag = createTag(user, user.namespace, u'tag')
        value = TagValue(user.id, tag.id, uuid4(), None)
        self.store.add(value)
        self.store.flush()
        fileID = 'f' * 64
        opaque = self.store.add(OpaqueValue(fileID, 'content'))
        self.store.add(OpaqueValueLink(value.id, fileID))
        self.store.remove(opaque)
        self.assertRaises(IntegrityError, self.store.flush)
        self.store.rollback()


class CreateOpaqueValueTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testCreateOpaqueValue(self):
        """
        L{createOpaqueValue} creates an L{OpaqueValue} and the corresponding
        L{OpaqueValueLink} referencing the given L{TagValue}.
        """
        user = createUser(u'name', u'password', u'User', u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag = createTag(user, user.namespace, u'tag')
        value = createTagValue(user.id, tag.id, uuid4(), None)
        self.store.commit()
        createOpaqueValue(value.id, 'content')
        fileID = sha256('content').hexdigest()
        result = self.store.find(OpaqueValue,
                                 OpaqueValue.fileID == fileID).one()
        self.assertNotIdentical(None, result)
        self.assertEqual(fileID, result.fileID)
        self.assertEqual('content', result.content)
        result = self.store.find(OpaqueValueLink,
                                 OpaqueValueLink.fileID == fileID,
                                 OpaqueValueLink.valueID == value.id)
        self.assertNotIdentical(None, result.one())

    def testCreateOpaqueValueWithSameContent(self):
        """
        L{createOpaqueValue} doesn't create duplicate L{OpaqueValue}s if the
        content is the same.
        """
        user = createUser(u'name', u'password', u'User', u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag = createTag(user, user.namespace, u'tag')
        value1 = createTagValue(user.id, tag.id, uuid4(), None)
        value2 = createTagValue(user.id, tag.id, uuid4(), None)
        self.store.commit()
        createOpaqueValue(value1.id, 'content')
        createOpaqueValue(value2.id, 'content')
        fileID = sha256('content').hexdigest()
        result = self.store.find(OpaqueValue, OpaqueValue.fileID == fileID)
        self.assertNotIdentical(None, result.one())
        result = self.store.find(OpaqueValueLink,
                                 OpaqueValueLink.fileID == fileID)
        self.assertEqual(2, result.count())


class GetOpaqueValuesTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testGetOpaqueValues(self):
        """
        L{getOpaqueValues} returns L{OpaqueValue}s for the given L{TagValue}s.
        """
        user = createUser(u'name', u'password', u'User', u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag = createTag(user, user.namespace, u'tag')
        value1 = createTagValue(user.id, tag.id, uuid4(), None)
        value2 = createTagValue(user.id, tag.id, uuid4(), None)
        self.store.commit()
        opaque1 = createOpaqueValue(value1.id, 'content1')
        opaque2 = createOpaqueValue(value2.id, 'content2')
        self.assertEqual(sorted([opaque1, opaque2]),
                         sorted(getOpaqueValues([value1.id, value2.id])))


class AboutTagValueSchemaTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testUniqueAboutTagValue(self):
        """
        An C{IntegrityError} is raised if an L{AboutTagValue} with a duplicate
        about tag value is added to the database.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        self.store.add(AboutTagValue(objectID1, u'foo'))
        self.store.flush()
        self.store.add(AboutTagValue(objectID2, u'foo'))
        self.assertRaises(IntegrityError, self.store.flush)
        self.store.rollback()

    def testUniqueObjectID(self):
        """
        An C{IntegrityError} is raised if an L{AboutTagValue} with a duplicate
        object ID is added to the database.
        """
        objectID = uuid4()
        self.store.add(AboutTagValue(objectID, u'foo'))
        self.store.flush()
        self.store.add(AboutTagValue(objectID, u'bar'))
        self.assertRaises(IntegrityError, self.store.flush)
        self.store.rollback()


class CreateAboutTagValueTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testCreateAboutTagValue(self):
        """L{createAboutTagValue} creates a new L{AboutTagValue}."""
        objectID = uuid4()
        aboutTagValue = createAboutTagValue(objectID, u'An about tag Value')
        self.assertEqual(objectID, aboutTagValue.objectID)
        self.assertEqual(u'An about tag Value', aboutTagValue.value)

    def testCreateTagValueAddsToDatabase(self):
        """
        L{createAboutTagValue} automatically adds the new L{AboutTagValue} to
        the database.
        """
        objectID = uuid4()
        value = createAboutTagValue(objectID, u'An about tag value')
        self.assertIdentical(value, self.store.find(AboutTagValue).one())


class GetAboutTagValuesTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testGetAboutTagValues(self):
        """
        L{getAboutTagValues} returns all L{AboutTagValue}s in the database, by
        default.
        """
        value1 = self.store.add(AboutTagValue(uuid4(), u'foo'))
        value2 = self.store.add(AboutTagValue(uuid4(), u'bar'))
        self.assertEqual(sorted([value1, value2]), sorted(getAboutTagValues()))

    def testGetAboutTagValuesWithTagValues(self):
        """
        When C{AboutTagValue.value}s are provided L{getAboutTagValues} returns
        matching C{AboutTagValue}s.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        value = self.store.add(AboutTagValue(objectID1, u'foo'))
        self.store.add(AboutTagValue(objectID2, u'bar'))
        self.assertEqual(value, getAboutTagValues(values=[u'foo']).one())

    def testGetAboutTagValuesWithObjectIDs(self):
        """
        When C{objectID}s are provided L{getAboutTagValues} returns
        matching C{AboutTagValue}s.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        value = self.store.add(AboutTagValue(objectID1, u'foo'))
        self.store.add(AboutTagValue(objectID2, u'bar'))
        self.assertEqual(value, getAboutTagValues(objectIDs=[objectID1]).one())

    def testGetAboutTagValuesWithValuesAndObjectIDs(self):
        """
        When C{AboutValue.value}s and C{objectID}s are provided
        L{getAboutTagValues} returns matching C{AboutTagValue}s.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        value1 = self.store.add(AboutTagValue(objectID1, u'foo'))
        value2 = self.store.add(AboutTagValue(objectID2, u'bar'))
        results = list(getAboutTagValues(values=[u'bar'],
                                         objectIDs=[objectID1]))
        self.assertEqual([value1, value2], results)
