from datetime import datetime, timedelta
import os
from uuid import uuid4

from twisted.internet.defer import inlineCallbacks

from fluiddb.data.object import getDirtyObjects, DirtyObject
from fluiddb.data.namespace import createNamespace
from fluiddb.data.tag import createTag
from fluiddb.data.user import createUser
from fluiddb.data.value import createTagValue, getTagValues, TagValue
from fluiddb.model.object import ObjectIndex
from fluiddb.scripts.index import (
    buildIndex, deleteIndex, updateIndex, batchIndex)
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    ConfigResource, DatabaseResource, IndexResource, LoggingResource)


class DeleteIndexTest(FluidinfoTestCase):

    resources = [('client', IndexResource()),
                 ('config', ConfigResource())]

    @inlineCallbacks
    def testDeleteIndex(self):
        """L{deleteIndex} removes all documents from a Solr index."""
        objectID = uuid4()
        index = ObjectIndex(self.client)
        yield index.update({objectID: {u'test/tag': 42}})
        yield self.client.commit()
        response = yield self.client.search('*:*')
        self.assertEqual([{u'fluiddb/id': str(objectID)}],
                         response.results.docs)

        yield deleteIndex(self.client.url)
        response = yield self.client.search('*:*')
        self.assertEqual([], response.results.docs)


class UpdateIndexTest(FluidinfoTestCase):

    resources = [('client', IndexResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    @inlineCallbacks
    def testUpdateIndexWithoutData(self):
        """
        L{updateIndex} is a no-op if there are no changes to the
        main store.
        """
        with open(os.devnull, 'w') as stream:
            yield updateIndex(self.client.url, stream=stream)
        response = yield self.client.search('*:*')
        self.assertEqual([], response.results.docs)

    @inlineCallbacks
    def testUpdateIndex(self):
        """
        L{updateIndex} creates documents for all tag-values in the main store
        that have been modified since the given C{datetime}.
        """
        user = createUser(u'username', u'secret', u'User', u'user@example.com')
        namespace = createNamespace(user, u'username', None)
        tag = createTag(user, namespace, u'tag')
        objectID = uuid4()
        value = createTagValue(user.id, tag.id, uuid4(), 42)
        value.creationTime = datetime.utcnow() - timedelta(days=2)
        createTagValue(user.id, tag.id, objectID, 65)
        createdAfterTime = datetime.utcnow() - timedelta(days=1)
        with open(os.devnull, 'w') as stream:
            yield updateIndex(self.client.url, createdAfterTime, stream=stream)
        response = yield self.client.search('*:*')
        self.assertEqual([{u'fluiddb/id': str(objectID)}],
                         response.results.docs)


class BuildIndexTest(FluidinfoTestCase):

    resources = [('client', IndexResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    @inlineCallbacks
    def testBuildIndexWithoutData(self):
        """L{buildIndex} is effectively a no-op if the main store is empty."""
        with open(os.devnull, 'w') as stream:
            yield buildIndex(self.client.url, stream=stream)
        response = yield self.client.search('*:*')
        self.assertEqual([], response.results.docs)

    @inlineCallbacks
    def testBuildIndexWithDirtyIndex(self):
        """
        L{buildIndex} raises a C{RuntimeError} if the Solr index already
        contains documents.
        """
        objectID = uuid4()
        index = ObjectIndex(self.client)
        yield index.update({objectID: {u'test/tag': 42}})
        yield self.client.commit()
        yield self.assertFailure(buildIndex(self.client.url), RuntimeError)

    @inlineCallbacks
    def testBuildIndex(self):
        """
        L{buildIndex} creates documents for all tags values in the main store.
        """
        user = createUser(u'username', u'secret', u'User', u'user@example.com')
        namespace = createNamespace(user, u'username', None)
        tag = createTag(user, namespace, u'tag')
        objectID1 = uuid4()
        objectID2 = uuid4()
        createTagValue(user.id, tag.id, objectID1, 42)
        createTagValue(user.id, tag.id, objectID2, 65)
        with open(os.devnull, 'w') as stream:
            yield buildIndex(self.client.url, stream=stream)
        response = yield self.client.search('*:*')
        self.assertEqual(sorted([{u'fluiddb/id': str(objectID1)},
                                 {u'fluiddb/id': str(objectID2)}]),
                         sorted(response.results.docs))


class BatchIndexTest(FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('log', LoggingResource(format='%(message)s')),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(BatchIndexTest, self).setUp()

        # We use low-level functions here instead of model API methods because
        # we want to avoid an automatic update of the objects table.
        user = createUser(u'username', u'secret', u'User', u'user@example.com')
        namespace = createNamespace(user, u'username', None)
        tag = createTag(user, namespace, u'tag')

        self.userID = user.id
        self.tagID = tag.id
        tempPath = self.config.get('service', 'temp-path')
        self.objectsFilename = os.path.join(tempPath, 'objects.txt')

    def tearDown(self):
        super(BatchIndexTest, self).tearDown()
        if os.path.exists(self.objectsFilename):
            os.remove(self.objectsFilename)

    def createObjectsFile(self):
        """Helper function to create a file with a list of all object IDs."""
        allObjects = set(getTagValues().values(TagValue.objectID))
        with open(self.objectsFilename, 'w') as objectsFile:
            for objectID in allObjects:
                objectsFile.write(str(objectID) + '\n')

    def testBatchIndexTouchesAllObjects(self):
        """C{batchIndex} touches all objects in the given file."""
        createTagValue(self.userID, self.tagID, uuid4(), 10)
        createTagValue(self.userID, self.tagID, uuid4(), 20)

        allObjects = set(getTagValues().values(TagValue.objectID))
        self.createObjectsFile()
        batchIndex(self.objectsFilename, 0, 10)
        touchedObjects = set(getDirtyObjects().values(DirtyObject.objectID))
        self.assertEqual(allObjects, touchedObjects)

    def testBatchIndexTouchesTheGivenNumberOfObjectsPerInterval(self):
        """
        C{batchIndex} touches only the max number of objects permited on each
        interval acording to the interval parameter.
        """
        createTagValue(self.userID, self.tagID, uuid4(), 10)
        createTagValue(self.userID, self.tagID, uuid4(), 20)
        createTagValue(self.userID, self.tagID, uuid4(), 30)
        createTagValue(self.userID, self.tagID, uuid4(), 40)
        createTagValue(self.userID, self.tagID, uuid4(), 50)
        self.createObjectsFile()

        self.expectedTouchedObjects = 1

        def fakeSleep(seconds):
            self.assertEqual(10 * 60, seconds)
            self.assertEqual(self.expectedTouchedObjects,
                             getDirtyObjects().count())
            self.expectedTouchedObjects += 1

        # index objects one every ten seconds
        batchIndex(self.objectsFilename, 10, 1, sleepFunction=fakeSleep)

    def testBatchIndexLogsErrorIfObjectIDIsNotWellFormed(self):
        """
        If C{batchIndex} encounters a malformed objectID in the file it will
        continue the process after printing an error in the logs.
        """
        createTagValue(self.userID, self.tagID, uuid4(), 10)
        createTagValue(self.userID, self.tagID, uuid4(), 20)
        allObjects = set(getTagValues().values(TagValue.objectID))
        self.createObjectsFile()
        with open(self.objectsFilename, 'a') as objectsFilename:
            objectsFilename.write('wrong-id')
        batchIndex(self.objectsFilename, 0, 10)
        touchedObjects = set(getDirtyObjects().values(DirtyObject.objectID))
        self.assertEqual(allObjects, touchedObjects)
        self.assertIn("Invalid objectID: 'wrong-id'", self.log.getvalue())
