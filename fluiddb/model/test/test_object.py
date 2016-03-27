from uuid import UUID, uuid4

from twisted.internet.defer import inlineCallbacks

from fluiddb.data.object import SearchError
from fluiddb.data.permission import createTagPermission
from fluiddb.data.system import createSystemData
from fluiddb.data.tag import createTag
from fluiddb.data.value import (
    createAboutTagValue, createTagValue, getTagValues)
from fluiddb.exceptions import FeatureError
from fluiddb.model.object import (
    ObjectAPI, ObjectIndex, getObjectIndex, isEqualsQuery, isHasQuery)
from fluiddb.model.tag import TagAPI
from fluiddb.model.user import UserAPI, getUser
from fluiddb.model.value import TagValueAPI
from fluiddb.query.parser import parseQuery
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    ConfigResource, DatabaseResource, IndexResource)


class GetObjectIndexTest(FluidinfoTestCase):

    resources = [('config', ConfigResource())]

    def testGetObjectIndex(self):
        """
        L{getObjectIndex} returns a configured L{ObjectIndex} that is ready to
        use.
        """
        index = getObjectIndex()
        self.assertIsInstance(index, ObjectIndex)


class ObjectAPITestMixin(object):

    def testCreateWithoutAboutTagValue(self):
        """
        L{ObjectAPI.create} returns an L{UpdateResult} to represent the newly
        created object.
        """
        result = self.objects.create()
        self.assertIsInstance(result, UUID)

    def testCreateWithEmptyAboutTagValue(self):
        """
        L{ObjectAPI.create} ignores empty L{AboutTagValue.value}s, creating a
        new object ID when they're provided.
        """
        result1 = self.objects.create('')
        result2 = self.objects.create('')
        self.assertIsInstance(result1, UUID)
        self.assertIsInstance(result2, UUID)
        self.assertNotEqual(result1, result2)

    def testCreate(self):
        """
        L{ObjectAPI.create} creates new L{AboutTagValue} owned by the super
        user and returns the UUID for the newly created object.
        """
        objectID = self.objects.create(u'A fancy about tag value')
        tag = self.system.tags[u'fluiddb/about']
        about = getTagValues([(objectID, tag.id)]).one()
        self.assertEqual(u'A fancy about tag value', about.value)
        self.assertEqual(self.system.users[u'fluiddb'].id, about.creatorID)

    def testCreateDuplicateAboutTagValue(self):
        """
        L{ObjectAPI.create} returns the C{objectID} for an L{AboutTagValue} if
        it already exists in the database.
        """
        objectID1 = uuid4()
        createAboutTagValue(objectID1, u'A fancy about tag value')
        objectID2 = self.objects.create(u'A fancy about tag value')
        self.assertEqual(objectID1, objectID2)

    def testGetWithoutMatchingAboutTagValue(self):
        """
        L{ObjectAPI.get} returns an empty C{dict} if no L{AboutTagValue}s
        match the specified values.
        """
        self.assertEqual({}, self.objects.get([u'Hello world!']))

    def testGet(self):
        """
        L{ObjectAPI.get} returns a C{dict} that maps L{AboutTagValue.value}s
        to object IDs.
        """
        objectID = uuid4()
        createAboutTagValue(objectID, u'Hello world!')
        self.assertEqual({u'Hello world!': objectID},
                         self.objects.get([u'Hello world!']))

    def testGetTagsByObjects(self):
        """
        L{ObjectAPI.getTagsByObjects} returns a C{dict} of L{Tag.path}s that
        are associated with the given objects.
        """
        tag1 = createTag(self.user, self.user.namespace, u'tag1')
        tag2 = createTag(self.user, self.user.namespace, u'tag2')
        createTagPermission(tag1)
        createTagPermission(tag2)
        objectID = uuid4()
        createTagValue(self.user.id, tag1.id, objectID, u'value1')
        createTagValue(self.user.id, tag2.id, objectID, u'value2')

        tagPaths = self.objects.getTagsByObjects([objectID])
        expected = {objectID: [u'user/tag1', u'user/tag2']}
        tagPaths[objectID] = sorted(tagPaths[objectID])
        self.assertEqual(expected, tagPaths)

    def testGetTagsByObjectsWithoutMatchingValues(self):
        """
        L{ObjectAPI.getTagsByObjects} returns an empty C{dict} if no
        L{Tag.path}s are associated with the given objects.
        """
        self.assertEqual({}, self.objects.getTagsByObjects([uuid4()]))

    def testGetTagsForObjects(self):
        """
        L{ObjectAPI.getTagsForObjects} returns a C{list} of L{Tag.path}s that
        are associated with the given objects.
        """
        tag = createTag(self.user, self.user.namespace, u'tag')
        createTagPermission(tag)
        objectID1 = uuid4()
        objectID2 = uuid4()
        createTagValue(self.user.id, tag.id, objectID1, u'value1')
        createTagValue(self.user.id, tag.id, objectID2, u'value2')
        self.assertEqual(
            [u'user/tag'],
            self.objects.getTagsForObjects([objectID1, objectID2]))

    def testGetTagsForObjectsWithoutMatchingValues(self):
        """
        L{ObjectAPI.getTagsForObjects} returns an empty C{list} if no
        L{Tag.path}s are associated with the given objects.
        """
        self.assertEqual([], self.objects.getTagsForObjects([uuid4()]))

    def testSearchWithQueries(self):
        """
        L{ObjectAPI.search} raises a L{FeatureError} if no L{Query}s are
        provided.
        """
        self.assertRaises(FeatureError, self.objects.search, [])

    @inlineCallbacks
    def testSearchWithQuery(self):
        """
        L{ObjectAPI.search} returns a C{dict} that matches specified L{Query}
        instances to results.
        """
        TagAPI(self.user).create([(u'user/tag', u'description')])
        objectID = uuid4()
        index = ObjectIndex(self.client)
        yield index.update({objectID: {u'user/tag': 42},
                            uuid4(): {u'user/tag': 65}})
        yield index.commit()
        query = parseQuery(u'user/tag = 42')
        result = self.objects.search([query])
        result = yield result.get()
        self.assertEqual({query: set([objectID])}, result)

    @inlineCallbacks
    def testSearchWithManyQueries(self):
        """
        L{ObjectAPI.search} can be used to resolve many L{Query}s at once.
        """
        TagAPI(self.user).create([(u'user/tag', u'description')])
        objectID1 = uuid4()
        objectID2 = uuid4()
        index = ObjectIndex(self.client)
        yield index.update({objectID1: {u'user/tag': 42},
                            objectID2: {u'user/tag': 65}})
        yield index.commit()
        query1 = parseQuery(u'user/tag = 42')
        query2 = parseQuery(u'user/tag = 65')
        result = self.objects.search([query1, query2])
        result = yield result.get()
        self.assertEqual({query1: set([objectID1]),
                          query2: set([objectID2])}, result)

    @inlineCallbacks
    def testSearchWithAboutValueDoesNotHitSolr(self):
        """
        L{ObjectAPI.search} doesn't hit Solr to resolve
        C{fluiddb/about = "..."} queries.
        """
        # Use an invalid Solr URL to test that we're not hitting Solr.
        self.config.set('index', 'url', 'http://none')
        objectID = self.objects.create(u'TestObject')
        query = parseQuery(u'fluiddb/about = "TestObject"')
        result = yield self.objects.search([query]).get()
        self.assertEqual({query: set([objectID])}, result)

    def testSearchWithInvalidAboutValue(self):
        """
        L{ObjectAPI.search} raises L{SearchError} if a non-string value is used
        in a C{fluiddb/about = "..."} query.
        """
        query = parseQuery(u'fluiddb/about = 5')
        deferred = self.objects.search([query]).get()
        return self.assertFailure(deferred, SearchError)

    @inlineCallbacks
    def testSearchWithImplicitObjectCreation(self):
        """
        L{ObjectAPI.search} automatically creates objects for nonexistent
        C{fluiddb/about} values.
        """
        query = parseQuery(u'fluiddb/about = "TestObject"')
        result = yield self.objects.search([query], True).get()
        self.assertEqual(1, len(result[query]))
        self.assertEqual(1, len(self.objects.get([u"TestObject"])))

    @inlineCallbacks
    def testSearchWithoutImplicitObjectCreation(self):
        """
        L{ObjectAPI.search} doesn't automatically create objects for
        nonexistent C{fluiddb/about} values if the C{implicitCreate} flag is
        C{False}.
        """
        query = parseQuery(u'fluiddb/about = "TestObject"')
        result = yield self.objects.search([query], False).get()
        self.assertEqual(0, len(result[query]))

    @inlineCallbacks
    def testSearchWithFluiddbIDValueDoesNotHitSolr(self):
        """
        L{ObjectAPI.search} doesn't hit Solr to resolve
        C{fluiddb/id = "..."} queries.
        """
        # Use an invalid Solr URL to test that we're not hitting Solr.
        self.config.set('index', 'url', 'http://none')
        objectID = uuid4()
        query = parseQuery(u'fluiddb/id = "%s"' % objectID)
        result = yield self.objects.search([query]).get()
        self.assertEqual({query: set([objectID])}, result)

    def testSearchWithInvalidFluiddbIDValue(self):
        """
        L{ObjectAPI.search} raises L{SearchError} if a wrong value is used in a
        C{fluiddb/id = "..."} query.
        """
        query = parseQuery(u'fluiddb/id = "INVALID"')
        deferred = self.objects.search([query]).get()
        return self.assertFailure(deferred, SearchError)

    @inlineCallbacks
    def testSearchWithHasQueryDoesNotHitSolr(self):
        """
        L{ObjectAPI.search} doesn't hit Solr to resolve C{has <path>} queries.
        """
        # Use an invalid Solr URL to test that we're not hitting Solr.
        self.config.set('index', 'url', 'http://none')
        objectID = self.objects.create(u'TestObject')
        TagValueAPI(self.user).set({objectID: {u'username/test': 'value'}})
        query = parseQuery(u'has username/test')
        result = yield self.objects.search([query]).get()
        self.assertEqual({query: set([objectID])}, result)

    def testSearchWithHasFluiddbIDQuery(self):
        """
        L{ObjectAPI.search} raises L{SearchError} if a C{has fluiddb/id} query
        is found.
        """
        query = parseQuery(u'has fluiddb/id')
        deferred = self.objects.search([query]).get()
        return self.assertFailure(deferred, SearchError)


class ObjectAPITest(ObjectAPITestMixin, FluidinfoTestCase):

    resources = [('client', IndexResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(ObjectAPITest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        self.user = getUser(u'user')
        self.objects = ObjectAPI(self.user)


class IsEqualsQueryTest(FluidinfoTestCase):

    resources = [('config', ConfigResource())]

    def testIsEqualsQuery(self):
        """
        L{isEqualsQuery} returns C{True} if the given query uses the C{equals}
        operator and the given path.
        """
        query = parseQuery(u'fluiddb/about = "test"')
        self.assertTrue(isEqualsQuery(query, u'fluiddb/about'))

    def testIsEqualsQueryWithOtherOperator(self):
        """
        L{isEqualsQuery} returns C{False} if the given query doesn't use the
        C{equals} operator operator and the given path.
        """
        query = parseQuery(u'fluiddb/about > "test"')
        self.assertFalse(isEqualsQuery(query, u'fluiddb/about'))

    def testIsEqualsQueryWithDifferentPath(self):
        """
        L{isEqualsQuery} returns C{True} if the given query uses the C{equals}
        operator but not the given path.
        """
        query = parseQuery(u'other/path = "test"')
        self.assertFalse(isEqualsQuery(query, u'different/path'))


class IsHasQueryTest(FluidinfoTestCase):

    resources = [('config', ConfigResource())]

    def testIsHasQuery(self):
        """
        L{isHasQuery} returns C{True} if the given query uses the C{has}
        operator.
        """
        query = parseQuery(u'has test/path')
        self.assertTrue(isHasQuery(query))

    def testIsNotHasQuery(self):
        """
        L{isHasQuery} returns C{False} if the given query doesn't use the
        C{has} operator.
        """
        query = parseQuery(u'has username/tag1 or username/tag2 = 42')
        self.assertFalse(isHasQuery(query))
