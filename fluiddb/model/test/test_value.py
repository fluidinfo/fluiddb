from uuid import uuid4

from storm.locals import Not

from fluiddb.data.namespace import createNamespace
from fluiddb.data.object import DirtyObject, getDirtyObjects
from fluiddb.data.permission import (
    createNamespacePermission, createTagPermission)
from fluiddb.data.system import createSystemData
from fluiddb.data.tag import Tag, createTag
from fluiddb.data.value import TagValue, createTagValue, getTagValues
from fluiddb.exceptions import FeatureError
from fluiddb.model.permission import PermissionAPI
from fluiddb.model.tag import TagAPI
from fluiddb.model.user import UserAPI, getUser
from fluiddb.model.value import TagValueAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import DatabaseResource


class TagValueAPITestMixin(object):

    def testGetWithoutObjectIDs(self):
        """
        L{TagValueAPI.get} raises L{FeatureError} if no object IDs are given.
        """
        tag = createTag(self.user, self.user.namespace, u'tag')
        createTagPermission(tag)
        self.assertRaises(FeatureError, self.tagValues.get, [],
                          [u'username/tag'])

    def testGetWithoutPaths(self):
        """
        L{TagValueAPI.get} returns values for all available L{Tag.path}s if no
        paths are explicitly specified.
        """
        TagAPI(self.user).create([(u'username/tag1', u'A tag'),
                                  (u'username/tag2', u'Another tag')])
        objectID = uuid4()
        self.tagValues.set({objectID: {u'username/tag1': 13},
                            uuid4(): {u'username/2': 17}})
        result = self.tagValues.get([objectID])
        self.assertEqual(1, len(result))
        self.assertIn(objectID, result)
        self.assertEqual(1, len(result[objectID]))
        self.assertIn(u'username/tag1', result[objectID])

    def testGetFilteredByUnknownObjectIDs(self):
        """
        L{TagValueAPI.get} doesn't return any L{Tag} values if none of the
        requested object IDs exist.
        """
        tag = createTag(self.user, self.user.namespace, u'tag')
        createTagPermission(tag)
        createTagValue(self.user.id, tag.id, uuid4(), 42)
        self.assertEqual({}, self.tagValues.get(objectIDs=[uuid4()],
                                                paths=[u'username/tag']))

    def testGetFilteredByObjectIDsAndPath(self):
        """
        When both object IDs and tag paths are provided, L{TagValueAPI.get}
        returns only those L{Tag} values that meet both criteria.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        namespace = createNamespace(self.user, u'name')
        createNamespacePermission(namespace)
        tag1 = createTag(self.user, namespace, u'tag1')
        tag2 = createTag(self.user, namespace, u'tag2')
        createTagPermission(tag1)
        createTagPermission(tag2)
        createTagValue(self.user.id, tag1.id, objectID1, 42)
        createTagValue(self.user.id, tag1.id, objectID2, 67)
        createTagValue(self.user.id, tag2.id, objectID1, 17)
        createTagValue(self.user.id, tag2.id, objectID2, 13)
        result = self.tagValues.get(objectIDs=[objectID1],
                                    paths=[u'name/tag1'])
        self.assertEqual(42, result[objectID1][u'name/tag1'].value)

    def testGetBinaryValue(self):
        """
        L{TagValueAPI.get} returns the MIME type and file contents for binary
        L{TagValue}s.
        """
        namespace = createNamespace(self.user, u'name')
        createNamespacePermission(namespace)
        tag = createTag(self.user, namespace, u'tag')
        createTagPermission(tag)
        objectID = uuid4()
        # NOTE: we use 'Hello \xA2' as value to test that a non utf-8 string
        # will work properly.
        values = {objectID: {u'name/tag': {'mime-type': 'text/plain',
                                           'contents': 'Hello \xA2'}}}
        self.tagValues.set(values)
        result = self.tagValues.get([objectID], [u'name/tag'])
        self.assertEqual(values[objectID][u'name/tag']['mime-type'],
                         result[objectID][u'name/tag'].value['mime-type'])
        self.assertEqual(values[objectID][u'name/tag']['contents'],
                         result[objectID][u'name/tag'].value['contents'])

    def testGetOnlyFluidDBID(self):
        """
        L{TagValueAPI.get} returns object IDs for the 'fluiddb/id' tag, when
        requested.
        """
        namespace = createNamespace(self.user, u'name')
        createNamespacePermission(namespace)
        tag = createTag(self.user, namespace, u'tag')
        createTagPermission(tag)
        objectID = uuid4()
        values = {objectID: {u'name/tag': {'mime-type': 'text/plain',
                                           'contents': 'Hello, world!'}}}
        self.tagValues.set(values)
        result = self.tagValues.get([objectID], [u'fluiddb/id'])
        self.assertEqual(objectID, result[objectID][u'fluiddb/id'].value)

    def testGetFluidDBID(self):
        """
        L{TagValueAPI.get} returns object IDs for the 'fluiddb/id' tag, in
        addition to other requests L{TagValue}s, when requested.
        """
        namespace = createNamespace(self.user, u'name')
        createNamespacePermission(namespace)
        tag = createTag(self.user, namespace, u'tag')
        createTagPermission(tag)
        objectID = uuid4()
        values = {objectID: {u'name/tag': 12}}
        self.tagValues.set(values)
        result = self.tagValues.get([objectID], [u'fluiddb/id', u'name/tag'])
        self.assertEqual(objectID, result[objectID][u'fluiddb/id'].value)
        self.assertEqual(12, result[objectID][u'name/tag'].value)

    def testSetWithEmptyValues(self):
        """
        Passing an empty C{dict} to L{TagValueAPI.set} raises L{FeatureError}.
        """
        self.assertRaises(FeatureError, self.tagValues.set, {})

    def testSet(self):
        """L{TagValueAPI.set} stores new L{TagValue}s."""
        namespace = createNamespace(self.user, u'name')
        createNamespacePermission(namespace)
        tag = createTag(self.user, namespace, u'tag')
        createTagPermission(tag)
        objectID = uuid4()
        values = {objectID: {u'name/tag': 42}}
        self.tagValues.set(values)
        value = getTagValues([(objectID, tag.id)]).one()
        self.assertEqual(tag.id, value.tagID)
        self.assertEqual(objectID, value.objectID)
        self.assertIn(objectID, getDirtyObjects().values(DirtyObject.objectID))

    def testSetBinaryValue(self):
        """
        L{TagValueAPI.set} can store binary L{TagValue}s.  The contents
        included in the dict representing the value are written to a file and
        added to the L{FileStore}.
        """
        namespace = createNamespace(self.user, u'name')
        createNamespacePermission(namespace)
        tag = createTag(self.user, namespace, u'tag')
        createTagPermission(tag)
        objectID = uuid4()
        self.tagValues.set(
            {objectID: {u'name/tag': {'mime-type': 'text/plain',
                                      'contents': 'Hello, world!'}}})
        value = getTagValues([(objectID, tag.id)]).one()
        self.assertEqual(tag.id, value.tagID)
        self.assertEqual(objectID, value.objectID)
        self.assertEqual({'mime-type': 'text/plain',
                          'size': 13},
                         value.value)
        self.assertIn(objectID, getDirtyObjects().values(DirtyObject.objectID))

    def testSetUpdates(self):
        """L{TagValueAPI.set} updates an existing value with a new one."""
        objectID = uuid4()
        namespace = createNamespace(self.user, u'name')
        createNamespacePermission(namespace)
        tag = createTag(self.user, namespace, u'tag')
        createTagPermission(tag)
        self.tagValues.set({objectID: {u'name/tag': 5}})
        self.tagValues.set({objectID: {u'name/tag': None}})
        value = getTagValues([(objectID, tag.id)]).one()
        self.assertEqual(tag.id, value.tagID)
        self.assertEqual(objectID, value.objectID)
        self.assertIn(objectID, getDirtyObjects().values(DirtyObject.objectID))

    def testDeleteWithoutData(self):
        """
        Calling L{TagValueAPI.delete} raises L{FeatureError} if no data is
        given.
        """
        self.assertRaises(FeatureError, self.tagValues.delete, [])

    def testDeleteWithEmptyGeneratorArgument(self):
        """
        Calling L{TagValueAPI.delete} raises L{FeatureError} if a generator
        that yields no values is passed.
        """
        values = (value for value in [])
        self.assertRaises(FeatureError, self.tagValues.delete, values)

    def testDelete(self):
        """L{TagValueAPI.delete} deletes L{TagValue}s."""
        objectID = uuid4()
        namespace = createNamespace(self.user, u'name')
        createNamespacePermission(namespace)
        tag = createTag(self.user, namespace, u'tag')
        createTagPermission(tag)
        createTagValue(self.user.id, tag.id, objectID, None)
        self.tagValues.delete([(objectID, u'name/tag')])
        values = self.store.find(TagValue, TagValue.tagID == Tag.id,
                                 Not(Tag.path.is_in(self.system.tags)))
        self.assertEqual([], list(values))
        self.assertIn(objectID, getDirtyObjects().values(DirtyObject.objectID))

    def testDeleteReturnsRowCount(self):
        """
        L{TagValueAPI.delete} returns the number of rows that were deleted.
        """
        objectID = uuid4()
        namespace = createNamespace(self.user, u'name')
        createNamespacePermission(namespace)
        tag = createTag(self.user, namespace, u'tag')
        createTagPermission(tag)
        createTagValue(self.user.id, tag.id, objectID, 42)
        result = self.tagValues.delete([(objectID, u'name/tag')])
        self.assertEqual(1, result)
        self.assertIn(objectID, getDirtyObjects().values(DirtyObject.objectID))

    def testDeleteOnlyConsidersSpecifiedObjectIDs(self):
        """
        L{TagValueAPI.delete} only removes the values for the specified object
        IDs.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        namespace = createNamespace(self.user, u'name')
        createNamespacePermission(namespace)
        tag = createTag(self.user, namespace, u'tag')
        createTagPermission(tag)
        createTagValue(self.user.id, tag.id, objectID1, 42)
        value = createTagValue(self.user.id, tag.id, objectID2, 17)
        self.tagValues.delete([(objectID1, u'name/tag')])
        values = self.store.find(TagValue, TagValue.tagID == Tag.id,
                                 Not(Tag.path.is_in(self.system.tags)))
        self.assertEqual([value], list(values))
        self.assertIn(objectID1,
                      getDirtyObjects().values(DirtyObject.objectID))

    def testDeleteOnlyConsidersSpecifiedPaths(self):
        """
        L{TagValueAPI.delete} only removes the values for the specified
        L{Tag.path}s.
        """
        objectID = uuid4()
        namespace = createNamespace(self.user, u'name')
        createNamespacePermission(namespace)
        tag1 = createTag(self.user, namespace, u'tag1')
        tag2 = createTag(self.user, namespace, u'tag2')
        createTagPermission(tag1)
        createTagPermission(tag2)
        createTagValue(self.user.id, tag1.id, objectID, 42)
        value = createTagValue(self.user.id, tag2.id, objectID, 17)
        self.tagValues.delete([(objectID, u'name/tag1')])
        values = self.store.find(TagValue, TagValue.tagID == Tag.id,
                                 Not(Tag.path.is_in(self.system.tags)))
        self.assertEqual([value], list(values))
        self.assertIn(objectID, getDirtyObjects().values(DirtyObject.objectID))

    def testDeleteRemovesTagValues(self):
        """
        L{TagValueAPI.delete} removes L{TagValue}s associated with the deleted
        L{Tag}s.
        """
        objectID = uuid4()
        namespace = createNamespace(self.user, u'name')
        createNamespacePermission(namespace)
        tag1 = createTag(self.user, namespace, u'tag1')
        tag2 = createTag(self.user, namespace, u'tag2')
        createTagPermission(tag1)
        createTagPermission(tag2)
        value = createTagValue(self.user.id, tag1.id, objectID, 42)
        createTagValue(self.user.id, tag2.id, objectID, 17)
        self.tagValues.delete([(objectID, u'name/tag2')])
        values = self.store.find(TagValue, TagValue.tagID == Tag.id,
                                 Not(Tag.path.is_in(self.system.tags)))
        self.assertEqual([value], list(values))
        self.assertIn(objectID, getDirtyObjects().values(DirtyObject.objectID))

    def testDeleteRemovesTagValuesWhenPassedAGenerator(self):
        """
        L{TagValueAPI.delete} removes L{TagValue}s associated with the
        deleted L{Tag}s when it is passed a generator (as opposed to a
        C{list}).
        """
        objectID = uuid4()
        namespace = createNamespace(self.user, u'name')
        createNamespacePermission(namespace)
        tag1 = createTag(self.user, namespace, u'tag1')
        tag2 = createTag(self.user, namespace, u'tag2')
        createTagPermission(tag1)
        createTagPermission(tag2)
        value = createTagValue(self.user.id, tag1.id, objectID, 42)
        createTagValue(self.user.id, tag2.id, objectID, 17)
        values = ((objectID, name) for name in [u'name/tag2'])
        self.tagValues.delete(values)
        values = self.store.find(TagValue, TagValue.tagID == Tag.id,
                                 Not(Tag.path.is_in(self.system.tags)))
        self.assertEqual([value], list(values))
        self.assertIn(objectID, getDirtyObjects().values(DirtyObject.objectID))

    def testDeleteOnlyDirtiesRemovedObjects(self):
        """L{TagValueAPI.delete} only marks affected objects as being dirty."""
        objectID = uuid4()
        namespace = createNamespace(self.user, u'name')
        createNamespacePermission(namespace)
        tag = createTag(self.user, namespace, u'tag')
        createTagPermission(tag)
        result = self.tagValues.delete([(objectID, u'name/tag')])
        self.assertEqual(0, result)
        self.assertNotIn(objectID,
                         getDirtyObjects().values(DirtyObject.objectID))


class TagValueAPITest(TagValueAPITestMixin, FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def setUp(self):
        super(TagValueAPITest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = PermissionAPI(self.user)
        self.tagValues = TagValueAPI(self.user)
