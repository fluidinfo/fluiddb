import time

from twisted.internet.defer import inlineCallbacks

from fluiddb.data.object import ObjectIndex, getDirtyObjects
from fluiddb.data.system import createSystemData
from fluiddb.model.object import ObjectAPI
from fluiddb.model.tag import TagAPI
from fluiddb.model.user import UserAPI, getUser
from fluiddb.model.value import TagValueAPI
from fluiddb.query.parser import parseQuery
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    IndexResource, ConfigResource, DatabaseResource)
from fluiddb.testing.solr import runDataImportHandler


class DataImportHandlerTest(FluidinfoTestCase):

    resources = [('client', IndexResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(DataImportHandlerTest, self).setUp()
        createSystemData()
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        self.user = getUser(u'user')
        self.objects = ObjectAPI(self.user)
        self.values = TagValueAPI(self.user)
        self.index = ObjectIndex(self.client)

    @inlineCallbacks
    def assertQuery(self, objectIDs, query):
        """Asserts if a query to fluidinfo returns the expected results.

        @param objectIDs: A sequence with the expected object IDs for the
            query.
        @param query: The fluidinfo query to check.
        """
        query = parseQuery(query)
        results = yield self.index.search(query)
        self.assertEqual(set(objectIDs), results)

    @inlineCallbacks
    def testImportObjectWithStringValue(self):
        """The Data Import Handler correctly imports C{string} values."""
        objectID = self.objects.create()
        self.values.set({objectID: {u'user/tag': u'string'}})
        runDataImportHandler(self.client.url)
        yield self.assertQuery([objectID], u'user/tag = "string"')
        yield self.assertQuery([objectID], u'has user/tag')

    @inlineCallbacks
    def testImportObjectWithStringValueInvalidXML(self):
        """
        The Data Import Handler correctly imports C{string} values, including
        those that contain invalid XML characters.
        """
        objectID = self.objects.create()
        self.values.set({objectID: {u'user/tag': u'foo \uFFFE'}})
        runDataImportHandler(self.client.url)
        yield self.assertQuery([objectID], u'user/tag = "foo \uFFFE"')
        yield self.assertQuery([objectID], u'has user/tag')

    @inlineCallbacks
    def testImportObjectWithEmptyStringValue(self):
        """The Data Import Handler correctly imports empty C{string} values."""
        objectID = self.objects.create()
        self.values.set({objectID: {u'user/tag': u''}})
        runDataImportHandler(self.client.url)
        yield self.assertQuery([objectID], u'user/tag = ""')
        yield self.assertQuery([objectID], u'has user/tag')

    @inlineCallbacks
    def testImportObjectWithQuotesValue(self):
        """
        The Data Import Handler correctly imports C{string} values with single
        quotes.
        """
        objectID = self.objects.create()
        self.values.set({objectID: {u'user/tag': u'hello\'world'}})
        runDataImportHandler(self.client.url)
        yield self.assertQuery([objectID], u'user/tag = "hello\'world"')
        yield self.assertQuery([objectID], u'has user/tag')

    @inlineCallbacks
    def testImportObjectWithDoubleQuotesValue(self):
        """
        The Data Import Handler correctly imports C{string} values with double
        quotes.
        """
        objectID = self.objects.create()
        self.values.set({objectID: {u'user/tag': u'hello\"world'}})
        runDataImportHandler(self.client.url)
        yield self.assertQuery([objectID], u'user/tag = "hello\\\"world"')
        yield self.assertQuery([objectID], u'has user/tag')

    @inlineCallbacks
    def testImportObjectWithCommaAndParens(self):
        """
        The Data Import Handler correctly imports C{string} values with comma
        and parens.
        """
        objectID = self.objects.create()
        self.values.set({objectID: {u'user/tag': u'),'}})
        runDataImportHandler(self.client.url)

        yield self.assertQuery([objectID], u'user/tag = "),"')
        yield self.assertQuery([objectID], u'has user/tag')

    @inlineCallbacks
    def testImportObjectWithStringValueWithSpecialCharacters(self):
        """
        The Data Import Handler correctly imports C{string} values with special
        unicode characters.
        """
        objectID = self.objects.create()
        self.values.set({objectID: {u'user/tag': u'\xe1\xe9\xed\xf3'}})
        runDataImportHandler(self.client.url)
        yield self.assertQuery([objectID], u'user/tag = "\xe1\xe9\xed\xf3"')
        yield self.assertQuery([objectID], u'has user/tag')

    @inlineCallbacks
    def testImportObjectWithListValue(self):
        """The Data Import Handler correctly imports C{list} values."""
        objectID = self.objects.create()
        self.values.set({objectID: {u'user/tag': [u'one', u'two', u'three']}})
        runDataImportHandler(self.client.url)
        yield self.assertQuery([objectID], u'user/tag contains "one" '
                                           u'and user/tag contains "two" '
                                           u'and user/tag contains "three"')
        yield self.assertQuery([objectID], u'has user/tag')

    @inlineCallbacks
    def testImportObjectWithListValueWithSpecialCharacters(self):
        """
        The Data Import Handler correctly imports C{list} values with special
        unicode characters.
        """
        objectID = self.objects.create()
        self.values.set({objectID: {u'user/tag': [u'one', u'\xe1\xe9']}})
        runDataImportHandler(self.client.url)
        yield self.assertQuery([objectID], u'user/tag contains "\xe1\xe9"')
        yield self.assertQuery([objectID], u'has user/tag')

    @inlineCallbacks
    def testImportObjectWithListValueWithEmptyString(self):
        """
        The Data Import Handler correctly imports C{list} values with an empty
        string in them.
        """
        objectID = self.objects.create()
        self.values.set({objectID: {u'user/tag': [u'']}})
        runDataImportHandler(self.client.url)
        yield self.assertQuery([objectID], u'user/tag contains ""')
        yield self.assertQuery([objectID], u'has user/tag')

    @inlineCallbacks
    def testImportObjectWithIntValue(self):
        """The Data Import Handler correctly imports C{int} values."""
        objectID = self.objects.create()
        self.values.set({objectID: {u'user/tag': 5}})
        runDataImportHandler(self.client.url)
        yield self.assertQuery([objectID], u'user/tag = 5')
        yield self.assertQuery([objectID], u'has user/tag')

    @inlineCallbacks
    def testImportObjectWithIntSixDigitValue(self):
        """The Data Import Handler correctly imports C{int} values."""
        objectID = self.objects.create()
        self.values.set({objectID: {u'user/tag': 123456}})
        runDataImportHandler(self.client.url)
        yield self.assertQuery([objectID], u'user/tag = 123456')
        yield self.assertQuery([objectID], u'has user/tag')

    @inlineCallbacks
    def testImportObjectWithFloatValue(self):
        """The Data Import Handler correctly imports C{float} values."""
        objectID = self.objects.create()
        self.values.set({objectID: {u'user/tag': 5.5}})
        runDataImportHandler(self.client.url)
        yield self.assertQuery([objectID], u'user/tag = 5.5')
        yield self.assertQuery([objectID], u'has user/tag')

    @inlineCallbacks
    def testImportObjectWithBoolValue(self):
        """The Data Import Handler correctly imports C{boolean} values."""
        objectID = self.objects.create()
        self.values.set({objectID: {u'user/tag': False}})
        runDataImportHandler(self.client.url)
        yield self.assertQuery([objectID], u'user/tag = false')
        yield self.assertQuery([objectID], u'has user/tag')

    @inlineCallbacks
    def testImportObjectWithNoneValue(self):
        """The Data Import Handler correctly imports C{null} values."""
        objectID = self.objects.create()
        self.values.set({objectID: {u'user/tag': None}})
        runDataImportHandler(self.client.url)
        yield self.assertQuery([objectID], u'has user/tag')

    @inlineCallbacks
    def testImportObjectWithBinaryValue(self):
        """The Data Import Handler correctly imports C{binary} values."""
        objectID = self.objects.create()
        self.values.set({objectID: {
            u'user/tag': {
                'mime-type': 'text/plain',
                'contents': 'file contents'}}})
        runDataImportHandler(self.client.url)
        yield self.assertQuery([objectID], u'has user/tag')

    @inlineCallbacks
    def testImportObjectWithBinaryValueDoesNotCreateOtherValues(self):
        """
        The Data Import Handler does not import binary tag values as other Solr
        fields. This is a test for issue #1447.
        """
        objectID = self.objects.create()
        self.values.set({objectID: {
            u'user/tag': {
                'mime-type': 'text/plain',
                'contents': 'file contents'}}})
        runDataImportHandler(self.client.url)
        yield self.assertQuery([objectID], u'has user/tag')
        yield self.assertQuery([], u'user/tag = 13')
        yield self.assertQuery([], u'user/tag = "size"')

    @inlineCallbacks
    def testImportObjectWithMultipleValues(self):
        """The Data Import Handler import documents with multiple values."""
        objectID = self.objects.create()
        self.values.set({objectID: {
            u'user/tag1': u'string',
            u'user/tag2': 5,
            u'user/tag3': 5.5,
            u'user/tag4': True,
            u'user/tag5': None,
            u'user/tag6': {
                'mime-type': 'text/plain',
                'contents': 'file contents'}}})
        runDataImportHandler(self.client.url)
        yield self.assertQuery([objectID],
                               'user/tag1 = "string" and user/tag2 = 5 '
                               'and user/tag3 = 5.5 and user/tag4 = true')

        yield self.assertQuery([objectID],
                               'has user/tag1 and has user/tag2 '
                               'and has user/tag3 and has user/tag4 '
                               'and has user/tag5 and has user/tag6')

    @inlineCallbacks
    def testImportMultipleObjects(self):
        """The Data Import Handler imports multiple objects."""
        objectID1 = self.objects.create()
        objectID2 = self.objects.create()
        objectID3 = self.objects.create()
        objectID4 = self.objects.create()
        self.values.set({objectID1: {u'user/tag1': u'string'},
                         objectID2: {u'user/tag1': u'string'},
                         objectID3: {u'user/tag1': 5},
                         objectID4: {u'user/tag2': True}})
        runDataImportHandler(self.client.url)

        yield self.assertQuery([objectID1, objectID2], 'user/tag1 = "string"')
        yield self.assertQuery([objectID1, objectID2, objectID3],
                               'has user/tag1')

    @inlineCallbacks
    def testImportDeletedObject(self):
        """The Data Import Handler removes all fields from deleted objects"""
        objectID1 = self.objects.create()
        objectID2 = self.objects.create()
        self.values.set({objectID1: {u'user/tag1': u'string'},
                         objectID2: {u'user/tag1': u'string'}})
        self.values.delete([(objectID1, u'user/tag1')])
        runDataImportHandler(self.client.url)
        yield self.assertQuery([objectID2], 'has user/tag1')
        yield self.assertQuery([objectID2], 'user/tag1 = "string"')

    @inlineCallbacks
    def testImportDeletedAndCreatedAgainObject(self):
        """
        The Data Import Handler correctly imports values deleted and created
        again.
        """
        objectID1 = self.objects.create()
        objectID2 = self.objects.create()
        self.values.set({objectID1: {u'user/tag1': u'string'},
                         objectID2: {u'user/tag1': u'string'}})
        self.values.delete([(objectID1, u'user/tag1')])
        self.values.set({objectID1: {u'user/tag1': u'string'}})
        runDataImportHandler(self.client.url)
        yield self.assertQuery([objectID1, objectID2], 'has user/tag1')
        yield self.assertQuery([objectID1, objectID2], 'user/tag1 = "string"')

    @inlineCallbacks
    def testDeltaImport(self):
        """
        When using a C{clean=false} option, the Data Import Handler only
        imports values modified since the last run.
        """
        objectID1 = self.objects.create()
        objectID2 = self.objects.create()

        self.values.set({objectID1: {
            u'user/tag1': u'string',
            u'user/tag2': 5,
            u'user/tag3': 5.5}})

        getDirtyObjects().remove()

        self.values.set({objectID2: {
            u'user/tag1': u'string',
            u'user/tag2': 5,
            u'user/tag3': 5.5}})

        runDataImportHandler(self.client.url, clean=False)

        yield self.assertQuery(
            [objectID2], 'has user/tag1 and has user/tag2 and has user/tag3 '
                         'and user/tag1="string" and user/tag2=5 and '
                         'user/tag3=5.5')

    @inlineCallbacks
    def testDeltaImportWithDeletedTag(self):
        """
        L{TagValue}s deleted via delete cascade triggered by a L{Tag} deletion
        should be deleted in the index too.
        """
        objectID = self.objects.create()
        self.values.set({objectID: {u'user/tag1': u'string',
                                    u'user/tag2': u'text'}})
        time.sleep(1)
        runDataImportHandler(self.client.url)
        tags = TagAPI(self.user)
        tags.delete([u'user/tag1'])
        self.store.commit()
        values = self.values.get([objectID], [u'user/tag1'])
        self.assertNotIn(u'user/tag1', values[objectID])
        runDataImportHandler(self.client.url, clean=False)
        yield self.assertQuery([], 'has user/tag1')
        yield self.assertQuery([], 'user/tag1 = "string"')
