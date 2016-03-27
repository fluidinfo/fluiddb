from uuid import uuid4

from twisted.internet.defer import inlineCallbacks

from fluiddb.data.object import (
    DirtyObject, ObjectIndex, SearchError, escapeWithWildcards,
    createDirtyObject, getDirtyObjects, touchObjects)
from fluiddb.query.parser import parseQuery
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    ConfigResource, IndexResource, DatabaseResource)


class ObjectIndexTest(FluidinfoTestCase):

    resources = [('client', IndexResource()),
                 ('config', ConfigResource())]

    def setUp(self):
        super(ObjectIndexTest, self).setUp()
        self.index = ObjectIndex(self.client)

    @inlineCallbacks
    def testUpdateWithoutData(self):
        """
        L{ObjectIndex.update} is effectively a no-op if no values are
        provided.
        """
        yield self.index.update({})
        yield self.index.commit()
        response = yield self.client.search('*:*')
        self.assertEqual([], response.results.docs)

    @inlineCallbacks
    def testUpdateWithNoneValue(self):
        """
        L{ObjectIndex.update} is creates Solr documents for the specified
        objects, L{Tag.path}s and C{None} values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/tag': None}})
        yield self.index.commit()
        response = yield self.client.search('*:*')
        self.assertEqual([{u'fluiddb/id': str(objectID)}],
                         response.results.docs)

    @inlineCallbacks
    def testUpdateWithBoolValue(self):
        """
        L{ObjectIndex.update} is creates Solr documents for the specified
        objects, L{Tag.path}s and C{bool} values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/tag': True}})
        yield self.index.commit()
        response = yield self.client.search('*:*')
        self.assertEqual([{u'fluiddb/id': str(objectID)}],
                         response.results.docs)

    @inlineCallbacks
    def testUpdateWithIntValue(self):
        """
        L{ObjectIndex.update} is creates Solr documents for the specified
        objects, L{Tag.path}s and C{int} values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/tag': 42}})
        yield self.index.commit()
        response = yield self.client.search('*:*')
        self.assertEqual([{u'fluiddb/id': str(objectID)}],
                         response.results.docs)

    @inlineCallbacks
    def testUpdateWithFloatValue(self):
        """
        L{ObjectIndex.update} is creates Solr documents for the specified
        objects, L{Tag.path}s and C{float} values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/tag': 42.3}})
        yield self.index.commit()
        response = yield self.client.search('*:*')
        self.assertEqual([{u'fluiddb/id': str(objectID)}],
                         response.results.docs)

    @inlineCallbacks
    def testUpdateWithUnicodeValue(self):
        """
        L{ObjectIndex.update} is creates Solr documents for the specified
        objects, L{Tag.path}s and C{unicode} values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/tag': u'value'}})
        yield self.index.commit()
        response = yield self.client.search('*:*')
        self.assertEqual([{u'fluiddb/id': str(objectID)}],
                         response.results.docs)

    @inlineCallbacks
    def testUpdateWithSetValue(self):
        """
        L{ObjectIndex.update} is creates Solr documents for the specified
        objects, L{Tag.path}s and C{list} values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/tag': [u'foo', u'bar']}})
        yield self.index.commit()
        response = yield self.client.search('*:*')
        self.assertEqual([{u'fluiddb/id': str(objectID)}],
                         response.results.docs)

    @inlineCallbacks
    def testUpdateWithBinaryValue(self):
        """
        L{ObjectIndex.update} is creates Solr documents for the specified
        objects, L{Tag.path}s and binary values.
        """
        objectID = uuid4()
        yield self.index.update(
            {objectID: {u'test/tag': {'mime-type': 'text/html',
                                      'file-id': 'index.html',
                                      'size': 123}}})
        yield self.index.commit()
        response = yield self.client.search('*:*')
        self.assertEqual([{u'fluiddb/id': str(objectID)}],
                         response.results.docs)

    @inlineCallbacks
    def testUpdateWithManyValues(self):
        """
        L{ObjectIndex.update} can create or update documents about many
        objects, L{Tag.path}s and values at once.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        yield self.index.update({objectID1: {u'test/tag1': u'Hi!'},
                                 objectID2: {u'test/tag2': 42}})
        yield self.index.commit()
        response = yield self.client.search('*:*')
        self.assertEqual(sorted([{u'fluiddb/id': str(objectID1)},
                                 {u'fluiddb/id': str(objectID2)}]),
                         sorted(response.results.docs))

    @inlineCallbacks
    def testSearchWithoutData(self):
        """
        L{ObjectIndex.search} returns an empty result if there are no
        documents in the index.
        """
        query = parseQuery(u'test/tag = 5')
        result = yield self.index.search(query)
        self.assertEqual(set(), result)

    @inlineCallbacks
    def testSearchWithoutMatch(self):
        """
        L{ObjectIndex.search} returns an empty result if no documents in the
        index match the specified L{Query}.
        """
        yield self.index.update({uuid4(): {u'test/tag': 42}})
        yield self.index.commit()
        query = parseQuery(u'unknown/tag = 5')
        result = yield self.index.search(query)
        self.assertEqual(set(), result)

    @inlineCallbacks
    def testSearchWithEqualsUnicodeComparison(self):
        """
        L{ObjectIndex.search} can perform C{=} comparisons with C{unicode}
        values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/unicode': u'value'},
                                 uuid4(): {u'test/unicode': u'another'}})
        yield self.index.commit()
        query = parseQuery('test/unicode = "value"')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithEqualsWithEmptyValue(self):
        """
        L{ObjectIndex.search} can perform C{=} comparisons with empty strings.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/tag': u''},
                                 uuid4(): {u'test/tag': u'devalue'}})
        yield self.index.commit()
        query = parseQuery(u'test/tag = ""')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithEqualsNullComparison(self):
        """
        L{ObjectIndex.search} can perform C{=} comparisons with C{null}
        values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/tag': None},
                                 uuid4(): {u'test/tag': u'another'}})
        yield self.index.commit()
        query = parseQuery('test/tag = null')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithNotEqualsNullComparison(self):
        """
        L{ObjectIndex.search} can perform C{!=} comparisons with C{null}
        values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/tag': u'value'},
                                 uuid4(): {u'test/tag': None}})
        yield self.index.commit()
        query = parseQuery('test/tag != null')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithEqualsBoolComparison(self):
        """
        L{ObjectIndex.search} can perform C{=} comparisons with C{bool}
        values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/int': True},
                                 uuid4(): {u'test/int': False}})
        yield self.index.commit()
        query = parseQuery(u'test/int = true')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithEqualsIntComparison(self):
        """
        L{ObjectIndex.search} can perform C{=} comparisons with C{int} values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/int': 42},
                                 uuid4(): {u'test/int': 65}})
        yield self.index.commit()
        query = parseQuery(u'test/int = 42')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithEqualsIntComparisonWithNegative(self):
        """
        L{ObjectIndex.search} can perform C{=} comparisons with negative
        C{int} values. See bug #827411.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/int': -42},
                                 uuid4(): {u'test/int': -65}})
        yield self.index.commit()
        query = parseQuery(u'test/int = -42')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithEqualsFloatComparison(self):
        """
        L{ObjectIndex.search} can perform C{=} comparisons with C{float}
        values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/float': 42.3},
                                 uuid4(): {u'test/float': 42.31}})
        yield self.index.commit()
        query = parseQuery(u'test/float = 42.3')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithEqualsFloatComparisonWithNegative(self):
        """
        L{ObjectIndex.search} can perform C{=} comparisons with negative
        C{float} values. See bug #827411.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/float': -42.3},
                                 uuid4(): {u'test/float': -42.31}})
        yield self.index.commit()
        query = parseQuery(u'test/float = -42.3')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithEqualsIntAndFloatComparison(self):
        """
        L{ObjectIndex.search} can perform C{=} comparisons with C{float}
        and C{int} values.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        objectID3 = uuid4()
        yield self.index.update({objectID1: {u'test/number': 42.0},
                                 objectID2: {u'test/number': 42},
                                 objectID3: {u'test/number': 48}})
        yield self.index.commit()
        query = parseQuery(u'test/number = 42')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID1, objectID2]), result)

    @inlineCallbacks
    def testSearchWithEqualsIntAndFloatComparisonWithNegative(self):
        """
        L{ObjectIndex.search} can perform C{=} comparisons with negative
        C{float} and C{int} values. See bug #827411.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        objectID3 = uuid4()
        yield self.index.update({objectID1: {u'test/number': -42.0},
                                 objectID2: {u'test/number': -42},
                                 objectID3: {u'test/number': -48}})
        yield self.index.commit()
        query = parseQuery(u'test/number = -42')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID1, objectID2]), result)

    def testSearchWithEqualsAndFluidDBSlashID(self):
        """
        A L{SearchError} is raised if an C{equals} query is used with the
        special C{fluiddb/id} virtual tag.
        """
        objectID = uuid4()
        query = parseQuery(u'fluiddb/id = "%s"' % objectID)
        return self.assertFailure(self.index.search(query), SearchError)

    @inlineCallbacks
    def testSearchWithNotEqualsUnicodeComparison(self):
        """
        L{ObjectIndex.search} can perform C{!=} comparisons with C{unicode}
        values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/unicode': u'novalue'},
                                 uuid4(): {u'test/unicode': u'value'}})
        yield self.index.commit()
        query = parseQuery(u'test/unicode != "value"')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithNotEqualsBoolComparison(self):
        """
        L{ObjectIndex.search} can perform C{!=} comparisons with C{bool}
        values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/bool': True},
                                 uuid4(): {u'test/bool': False}})
        yield self.index.commit()
        query = parseQuery(u'test/bool != False')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithNotEqualsIntComparison(self):
        """
        L{ObjectIndex.search} can perform C{!=} comparisons with C{int}
        values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/int': 42},
                                 uuid4(): {u'test/int': 65}})
        yield self.index.commit()
        query = parseQuery(u'test/int != 65')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithNotEqualsFloatComparison(self):
        """
        L{ObjectIndex.search} can perform C{!=} comparisons with C{float}
        values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/float': 42.1},
                                 uuid4(): {u'test/float': 65.3}})
        yield self.index.commit()
        query = parseQuery(u'test/float != 65.3')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    def testSearchWithNotEqualsFluidDBSlashIDComparison(self):
        """
        A L{SearchError} is raised if a C{!=} comparison is used with the
        special C{fluiddb/id} virtual tag.
        """
        objectID = uuid4()
        query = parseQuery(u'fluiddb/id != "%s"' % objectID)
        return self.assertFailure(self.index.search(query), SearchError)

    @inlineCallbacks
    def testSearchWithLessThanIntComparison(self):
        """
        L{ObjectIndex.search} can perform C{<} comparisons with C{int} values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/int': 42},
                                 uuid4(): {u'test/int': 43}})
        yield self.index.commit()
        query = parseQuery(u'test/int < 43')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithLessThanFloatComparison(self):
        """
        L{ObjectIndex.search} can perform C{<} comparisons with C{float}
        values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/float': 42.1},
                                 uuid4(): {u'test/float': 42.2}})
        yield self.index.commit()
        query = parseQuery(u'test/float < 42.2')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithLessThanIntAndFloatComparison(self):
        """
        L{ObjectIndex.search} can perform C{<} comparisons with C{float}
        and C{int} values.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        objectID3 = uuid4()
        yield self.index.update({objectID1: {u'test/number': 42.1},
                                 objectID2: {u'test/number': 42.2},
                                 objectID3: {u'test/number': 42}})
        yield self.index.commit()
        query = parseQuery(u'test/number < 42.2')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID1, objectID3]), result)

    def testSearchWithLessThanFluidDBSlashIDComparison(self):
        """
        A L{SearchError} is raised if a C{<} comparison is used with the
        special C{fluiddb/id} virtual tag.
        """
        objectID = uuid4()
        query = parseQuery(u'fluiddb/id < "%s"' % objectID)
        return self.assertFailure(self.index.search(query), SearchError)

    @inlineCallbacks
    def testSearchWithLessThanOrEqualIntComparison(self):
        """
        L{ObjectIndex.search} can perform C{<=} comparisons with C{int}
        values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/int': 42},
                                 uuid4(): {u'test/int': 43}})
        yield self.index.commit()
        query = parseQuery(u'test/int <= 42')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithLessThanOrEqualFloatComparison(self):
        """
        L{ObjectIndex.search} can perform C{<=} comparisons with C{float}
        values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/float': 42.1},
                                 uuid4(): {u'test/float': 42.11}})
        yield self.index.commit()
        query = parseQuery(u'test/float <= 42.1')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithLessThanOrEqualIntAndFloatComparison(self):
        """
        L{ObjectIndex.search} can perform C{<=} comparisons with C{float}
        and C{int} values.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        objectID3 = uuid4()
        yield self.index.update({objectID1: {u'test/number': 42.1},
                                 objectID2: {u'test/number': 42.11},
                                 objectID3: {u'test/number': 42}})
        yield self.index.commit()
        query = parseQuery(u'test/number <= 42.1')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID1, objectID3]), result)

    def testSearchWithLessThanOrEqualFluidDBSlashIDComparison(self):
        """
        A L{SearchError} is raised if a C{<=} comparison is used with the
        special C{fluiddb/id} virtual tag.
        """
        objectID = uuid4()
        query = parseQuery(u'fluiddb/id <= "%s"' % objectID)
        return self.assertFailure(self.index.search(query), SearchError)

    @inlineCallbacks
    def testSearchWithGreaterThanIntComparison(self):
        """
        L{ObjectIndex.search} can perform C{>} comparisons with C{int} values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/int': 43},
                                 uuid4(): {u'test/int': 42}})
        yield self.index.commit()
        query = parseQuery(u'test/int > 42')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithGreaterThanFloatComparison(self):
        """
        L{ObjectIndex.search} can perform C{>} comparisons with C{float}
        values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/float': 42.2},
                                 uuid4(): {u'test/float': 42.1}})
        yield self.index.commit()
        query = parseQuery(u'test/float > 42.1')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithGreaterThanIntAndFloatComparison(self):
        """
        L{ObjectIndex.search} can perform C{>} comparisons with C{float}
        and C{int} values.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        objectID3 = uuid4()
        yield self.index.update({objectID1: {u'test/number': 42.2},
                                 objectID2: {u'test/number': 42.1},
                                 objectID3: {u'test/number': 43}})
        yield self.index.commit()
        query = parseQuery(u'test/number > 42.1')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID1, objectID3]), result)

    def testSearchWithGreaterThanFluidDBSlashIDComparison(self):
        """
        A L{SearchError} is raised if a C{>} comparison is used with the
        special C{fluiddb/id} virtual tag.
        """
        objectID = uuid4()
        query = parseQuery(u'fluiddb/id > "%s"' % objectID)
        return self.assertFailure(self.index.search(query), SearchError)

    @inlineCallbacks
    def testSearchWithGreaterThanOrEqualIntComparison(self):
        """
        L{ObjectIndex.search} can perform C{>=} comparisons with C{int} values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/int': 43},
                                 uuid4(): {u'test/int': 42}})
        yield self.index.commit()
        query = parseQuery(u'test/int >= 43')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithGreaterThanOrEqualFloatComparison(self):
        """
        L{ObjectIndex.search} can perform C{>=} comparisons with C{float}
        values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/float': 42.2},
                                 uuid4(): {u'test/float': 42.1}})
        yield self.index.commit()
        query = parseQuery(u'test/float >= 42.2')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithGreaterThanOrEqualIntAndFloatComparison(self):
        """
        L{ObjectIndex.search} can perform C{>=} comparisons with C{float}
        and C{int} values.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        objectID3 = uuid4()
        yield self.index.update({objectID1: {u'test/number': 42.2},
                                 objectID2: {u'test/number': 42.1},
                                 objectID3: {u'test/number': 43}})
        yield self.index.commit()
        query = parseQuery(u'test/number >= 42.2')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID1, objectID3]), result)

    def testSearchWithGreaterThanOrEqualFluidDBSlashIDComparison(self):
        """
        A L{SearchError} is raised if a C{>=} comparison is used with the
        special C{fluiddb/id} virtual tag.
        """
        objectID = uuid4()
        query = parseQuery(u'fluiddb/id > "%s"' % objectID)
        return self.assertFailure(self.index.search(query), SearchError)

    @inlineCallbacks
    def testSearchWithHasNoneValue(self):
        """
        L{ObjectIndex.search} can perform C{has} queries with C{None} values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/tag1': None},
                                 uuid4(): {u'test/tag2': None}})
        yield self.index.commit()
        query = parseQuery(u'has test/tag1')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithHasBoolValue(self):
        """
        L{ObjectIndex.search} can perform C{has} queries with C{bool} values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/tag1': True},
                                 uuid4(): {u'test/tag2': True}})
        yield self.index.commit()
        query = parseQuery(u'has test/tag1')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithHasIntValue(self):
        """
        L{ObjectIndex.search} can perform C{has} queries with C{int} values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/tag1': 42},
                                 uuid4(): {u'test/tag2': 42}})
        yield self.index.commit()
        query = parseQuery(u'has test/tag1')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithHasFloatValue(self):
        """
        L{ObjectIndex.search} can perform C{has} queries with C{float} values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/tag1': 42.1},
                                 uuid4(): {u'test/tag2': 42.2}})
        yield self.index.commit()
        query = parseQuery(u'has test/tag1')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithHasUnicodeValue(self):
        """
        L{ObjectIndex.search} can perform C{has} queries with C{unicode}
        values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/tag1': u'value'},
                                 uuid4(): {u'test/tag2': u'value'}})
        yield self.index.commit()
        query = parseQuery(u'has test/tag1')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithHasSetValue(self):
        """
        L{ObjectIndex.search} can perform C{has} queries with C{list} values.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/tag1': [u'foo', u'bar']},
                                 uuid4(): {u'test/tag2': [u'foo', u'bar']}})
        yield self.index.commit()
        query = parseQuery(u'has test/tag1')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithHasBinaryValue(self):
        """
        L{ObjectIndex.search} can perform C{has} queries with binary values.
        """
        objectID = uuid4()
        value = {'mime-type': 'text/html', 'file-id': 'index.html', 'size': 7}
        yield self.index.update({objectID: {u'test/tag1': value},
                                 uuid4(): {u'test/tag2': value}})
        yield self.index.commit()
        query = parseQuery(u'has test/tag1')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithHasColonInPath(self):
        """
        L{ObjectIndex.search} can perform C{has} queries with paths having a
        colon.
        """
        objectID = uuid4()
        value = {'mime-type': 'text/html', 'file-id': 'index.html', 'size': 7}
        yield self.index.update({objectID: {u'test/one:two': value},
                                 uuid4(): {u'test/tag2': value}})
        yield self.index.commit()
        query = parseQuery(u'has test/one:two')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithMatches(self):
        """L{ObjectIndex.search} can perform C{matches} queries."""
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/tag': u'value'},
                                 uuid4(): {u'test/tag': u'devalue'}})
        yield self.index.commit()
        query = parseQuery(u'test/tag matches "value"')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithMatchesWithEmptyValue(self):
        """
        L{ObjectIndex.search} can perform C{matches} queries with empty
        strings.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/tag': u''},
                                 uuid4(): {u'test/tag': u'devalue'}})
        yield self.index.commit()
        query = parseQuery(u'test/tag matches ""')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithMatchesIsCaseInsensitive(self):
        """
        L{ObjectIndex.search} performs C{matches} queries case-insensitively.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        objectID3 = uuid4()
        yield self.index.update({objectID1: {u'test/tag': u'VALUE'},
                                 objectID2: {u'test/tag': u'value'},
                                 objectID3: {u'test/tag': u'VaLuE'},
                                 uuid4(): {u'test/tag': u'devalue'}})
        yield self.index.commit()
        query = parseQuery(u'test/tag matches "vAlUe"')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID1, objectID2, objectID3]), result)

    @inlineCallbacks
    def testSearchWithMatchesAndManyTerms(self):
        """
        L{ObjectIndex.search} can match terms with spaces when the C{matches}
        query is used.
        """
        objectID = uuid4()
        yield self.index.update(
            {objectID: {u'test/tag': u'apple orange cherry'},
             uuid4(): {u'test/tag': u'value'}})
        yield self.index.commit()
        query = parseQuery(u'test/tag matches "apple orange"')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithMatchesAndManyTermsIsCaseInsensitive(self):
        """
        L{ObjectIndex.search} can match terms with spaces when the C{matches}
        query is used.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        objectID3 = uuid4()
        yield self.index.update(
            {objectID1: {u'test/tag': u'APPLE ORANGE CHERRY'},
             objectID2: {u'test/tag': u'apple orange cherry'},
             objectID3: {u'test/tag': u'apple orange cherry'},
             uuid4(): {u'test/tag': u'devalue'}})
        yield self.index.commit()
        query = parseQuery(u'test/tag matches "aPpLe OrAnGe"')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID1, objectID2, objectID3]), result)

    @inlineCallbacks
    def testSearchWithMatchesAndPunctuation(self):
        """
        L{ObjectIndex.search} can match terms with punctuation when a
        C{matches} query is used.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        yield self.index.update(
            {objectID1: {u'test/tag': u'book: Moby Dick'},
             objectID2: {u'test/tag': u'One, Two, Three.'},
             uuid4(): {u'test/tag': u'One Book'}})
        yield self.index.commit()
        query = parseQuery(
            u'test/tag matches "book:" or test/tag matches "One,"')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID1, objectID2]), result)

    @inlineCallbacks
    def testSearchWithMatchesAndStarWildcard(self):
        """
        L{ObjectIndex.search} can match terms using the '*' wildcard when a
        C{matches} query is used.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        yield self.index.update(
            {objectID1: {u'test/tag': u'book:Moby Dict'},
             objectID2: {u'test/tag': u'book:Alice in Wonderland'},
             uuid4(): {u'test/tag': u'One Book'}})
        yield self.index.commit()
        query = parseQuery(u'test/tag matches "book:*"')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID1, objectID2]), result)

    @inlineCallbacks
    def testSearchWithMatchesAndStarWildcardAtTheBegining(self):
        """
        L{ObjectIndex.search} can match terms using the '*' wildcard at the
        begining of a term when a C{matches} query is used.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        yield self.index.update(
            {objectID1: {u'test/tag': u'book:Moby Dick'},
             objectID2: {u'test/tag': u'movie:Moby Dick'},
             uuid4(): {u'test/tag': u'One Book'}})
        yield self.index.commit()
        query = parseQuery(u'test/tag matches "*moby"')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID1, objectID2]), result)

    @inlineCallbacks
    def testSearchWithMatchesAndQuestionMarkWildcard(self):
        """
        L{ObjectIndex.search} can match terms using the '?' wildcard when a
        C{matches} query is used.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        yield self.index.update(
            {objectID1: {u'test/tag': u'red stone'},
             objectID2: {u'test/tag': u'get rid of the body'},
             uuid4(): {u'test/tag': u'run, forest, run'}})
        yield self.index.commit()
        query = parseQuery(u'test/tag matches "r?d"')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID1, objectID2]), result)

    @inlineCallbacks
    def testSearchWithMatchesAndFuzzySearch(self):
        """
        L{ObjectIndex.search} can match fuzzy terms using the '~' wildcard when
        a C{matches} query is used.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        yield self.index.update(
            {objectID1: {u'test/tag': u'fuzzy search'},
             objectID2: {u'test/tag': u'wuzzy term'},
             uuid4(): {u'test/tag': u'not related term'}})
        yield self.index.commit()
        query = parseQuery(u'test/tag matches "fuzzy~"')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID1, objectID2]), result)

    @inlineCallbacks
    def testSearchWithMatchesAndEscapedWildcars(self):
        """
        L{ObjectIndex.search} can match terms with '*', '?' and '~' using
        character escaping.
        """
        objectID1 = uuid4()
        objectID2 = uuid4()
        yield self.index.update(
            {objectID1: {u'test/tag': u'Is that man blue?'},
             objectID2: {u'test/tag': u'Syntax: *remark*'},
             uuid4(): {u'test/tag': u'Blue and remarkable'}})
        yield self.index.commit()
        query = parseQuery(
            u'test/tag matches "blue\?" or test/tag matches "\*remark\*"')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID1, objectID2]), result)

    def testSearchWithMatchesAndFluidDBSlashID(self):
        """
        A L{SearchError} is raised if a C{matches} query is used with the
        special C{fluiddb/id} virtual tag.
        """
        objectID = uuid4()
        query = parseQuery(u'fluiddb/id matches "%s"' % objectID)
        return self.assertFailure(self.index.search(query), SearchError)

    @inlineCallbacks
    def testSearchWithContains(self):
        """L{ObjectIndex.search} can perform C{contains} queries."""
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/tag': [u'foo', u'bar']},
                                 uuid4(): {u'test/tag': [u'baz']}})
        yield self.index.commit()
        query = parseQuery(u'test/tag contains "foo"')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithContainsAndTermWithWhitespace(self):
        """
        L{ObjectIndex.search} can perform C{contains} queries with terms that
        include whitespace.
        """
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/tag': [u'foo bar', u'baz']},
                                 uuid4(): {u'test/tag': [u'quux']}})
        yield self.index.commit()
        query = parseQuery(u'test/tag contains "foo bar"')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    def testSearchWithContainsAndFluidDBSlashID(self):
        """
        A L{SearchError} is raised if a C{contains} query is used with the
        special C{fluiddb/id} virtual tag.
        """
        objectID = uuid4()
        query = parseQuery(u'fluiddb/id contains "%s"' % objectID)
        return self.assertFailure(self.index.search(query), SearchError)

    @inlineCallbacks
    def testSearchWithOr(self):
        """L{ObjectIndex.search} can perform C{or} queries."""
        objectID1 = uuid4()
        objectID2 = uuid4()
        yield self.index.update({objectID1: {u'test/int': 42},
                                 objectID2: {u'test/int': 67},
                                 uuid4(): {u'test/int': 93}})
        yield self.index.commit()
        query = parseQuery(u'test/int = 42 or test/int = 67')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID1, objectID2]), result)

    @inlineCallbacks
    def testSearchWithOrUnmatched(self):
        """
        L{ObjectIndex.search} only returns objects that match one side of an
        C{or} query.
        """
        yield self.index.update({uuid4(): {u'test/int': 42},
                                 uuid4(): {u'test/int': 67}})
        yield self.index.commit()
        query = parseQuery(u'test/int = 41 or test/int = 66')
        result = yield self.index.search(query)
        self.assertEqual(set([]), result)

    @inlineCallbacks
    def testSearchWithAnd(self):
        """L{ObjectIndex.search} can perform C{and} queries."""
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/int': 42,
                                            u'test/unicode': u'value'},
                                 uuid4(): {u'test/int': 67}})
        yield self.index.commit()
        query = parseQuery(u'test/int = 42 and test/unicode = "value"')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithAndUnmatched(self):
        """
        L{ObjectIndex.search} only returns objects that match both sides of an
        C{and} query.
        """
        yield self.index.update({uuid4(): {u'test/int': 67,
                                           u'test/unicode': u'value'},
                                 uuid4(): {u'test/int': 95}})
        yield self.index.commit()
        query = parseQuery(u'test/int = 42 and test/unicode = "value"')
        result = yield self.index.search(query)
        self.assertEqual(set([]), result)

    @inlineCallbacks
    def testSearchWithExcept(self):
        """L{ObjectIndex.search} can perform C{except} queries."""
        objectID1 = uuid4()
        objectID2 = uuid4()
        yield self.index.update({objectID1: {u'test/int': 42,
                                             u'test/unicode': u'value'},
                                 objectID2: {u'test/int': 42,
                                             u'test/unicode': u'hello'}})
        yield self.index.commit()
        query = parseQuery(u'test/int = 42 except test/unicode = "value"')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID2]), result)

    @inlineCallbacks
    def testSearchWithUnicodePath(self):
        """
        L{ObjectIndex.search} can search for paths with unicode characters in
        them.
        """
        objectID = uuid4()
        path = u'test/\N{HIRAGANA LETTER A}'
        yield self.index.update({objectID: {path: u'value'},
                                 uuid4(): {path: u'another'}})
        yield self.index.commit()
        query = parseQuery(u'test/\N{HIRAGANA LETTER A} = "value"')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)

    @inlineCallbacks
    def testSearchWithComplexQuery(self):
        """L{ObjectIndex.search} can handle complex queries."""
        objectID = uuid4()
        yield self.index.update({objectID: {u'test/unicode': u'value',
                                            u'test/int': 42,
                                            u'test/float': 42.1}})
        yield self.index.commit()
        query = parseQuery(u'test/unicode = "value" and '
                           u'(test/int = 42 or test/float = 42.1) '
                           u'except test/unknown = 10')
        result = yield self.index.search(query)
        self.assertEqual(set([objectID]), result)


class EscapeWithWildcards(FluidinfoTestCase):

    def testEscapeWithWildcards(self):
        """
        L{escapeWithWildcards} escapes all Lucene especial characters except
        the wildcards.
        """
        terms = [(r'Hello*World', r'Hello*World'),
                 (r'Hello\*World', r'Hello\*World'),
                 (r'Hello "World"', r'Hello \"World\"'),
                 (r'Hello |&^"~*?', r'Hello \|\&\^\"~*?'),
                 (r'Hello (World)', r'Hello \(World\)'),
                 (r'Hello:World', r'Hello\:World'),
                 (r'Hello\World', r'Hello\\World'),
                 (r'Hello World', r'Hello World'), ]

        for raw, escaped in terms:
            self.assertEqual(escaped, escapeWithWildcards(raw))


class CreateObjectTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testCreateObject(self):
        """L{createDirtyObject} creates a new L{DirtyObject}."""
        objectID = uuid4()
        object1 = createDirtyObject(objectID)
        self.assertEqual(objectID, object1.objectID)

    def testCreateTagAddsToStore(self):
        """
        L{createDirtyObject} adds the new L{DirtyObject} to the main store.
        """
        objectID = uuid4()
        object1 = createDirtyObject(objectID)
        result = self.store.find(DirtyObject, DirtyObject.objectID == objectID)
        self.assertIdentical(object1, result.one())


class GetObjectsTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testGetObjects(self):
        """
        L{getDirtyObjects} returns all L{DirtyObject}s in the database, by
        default.
        """
        object1 = createDirtyObject(uuid4())
        self.assertEqual(object1, getDirtyObjects().one())

    def testGetObjectsWithObjectIDs(self):
        """
        When L{DirtyObject.objectID}s are provided L{getDirtyObjects} returns
        matching L{DirtyObject}s.
        """
        objectID = uuid4()
        object1 = createDirtyObject(objectID)
        createDirtyObject(uuid4())
        result = getDirtyObjects(objectIDs=[objectID])
        self.assertIdentical(object1, result.one())


class TouchObjectsTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testTouchObjects(self):
        """L{touchObjects} adds the objects to the C{dirty_objects} table."""
        objectID = uuid4()
        touchObjects([objectID])
        self.assertNotIdentical(None, getDirtyObjects([objectID]).one())
