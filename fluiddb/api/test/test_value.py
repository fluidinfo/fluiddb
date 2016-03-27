# -*- coding: utf-8 -*-

from json import loads
from uuid import uuid4, UUID

from twisted.internet.defer import inlineCallbacks

from fluiddb.api.facade import Facade
from fluiddb.application import FluidinfoSessionFactory
from fluiddb.common.types_thrift.ttypes import (
    TNonexistentTag, TPathPermissionDenied, TNoInstanceOnObject, TBadRequest,
    TParseError, TInvalidPath)
from fluiddb.api.value import TagPathAndValue
from fluiddb.data.permission import Operation, Policy
from fluiddb.data.system import createSystemData
from fluiddb.data.tag import getTags
from fluiddb.data.value import createTagValue, getTagValues
from fluiddb.cache.permission import CachingPermissionAPI
from fluiddb.model.tag import TagAPI
from fluiddb.model.user import UserAPI, getUser
from fluiddb.model.value import TagValueAPI, FluidinfoTagValue
from fluiddb.security.tag import SecureTagAPI
from fluiddb.security.value import SecureTagValueAPI
from fluiddb.testing.resources import (
    CacheResource, ConfigResource, DatabaseResource, IndexResource,
    LoggingResource, ThreadPoolResource)
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.session import login
from fluiddb.testing.solr import runDataImportHandler
from fluiddb.util.transact import Transact
from fluiddb.web.query import (
    createBinaryThriftValue, createThriftValue, guessValue)
from fluiddb.web.values import ValuesQuerySchema


class FacadeTagValueMixinTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(FacadeTagValueMixinTest, self).setUp()
        createSystemData()
        self.transact = Transact(self.threadPool)
        factory = FluidinfoSessionFactory('API-9000')
        self.facade = Facade(self.transact, factory)
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = CachingPermissionAPI(self.user)

    @inlineCallbacks
    def testGetTagInstanceWithUnknownTag(self):
        """
        L{FacadeTagValueMixin.getTagInstance} raises a L{TNoInstanceOnObject}
        exception if the specified L{Tag.path} doesn't exist.
        """
        objectID = uuid4()
        self.store.commit()
        with login(u'username', objectID, self.transact) as session:
            deferred = self.facade.getTagInstance(session, u'unknown/path',
                                                  str(objectID))
            error = yield self.assertFailure(deferred, TNonexistentTag)
            self.assertEqual(u'unknown/path', error.path)

    @inlineCallbacks
    def testGetTagInstanceWithUnknownObjectID(self):
        """
        L{FacadeTagValueMixin.getTagInstance} raises a L{TNoInstanceOnObject}
        exception if the specified object ID doesn't exist.
        """
        objectID = uuid4()
        TagAPI(self.user).create([(u'username/tag', u'description')])
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.getTagInstance(session, u'username/tag',
                                                  str(objectID))
            error = yield self.assertFailure(deferred, TNoInstanceOnObject)
            self.assertEqual(u'username/tag', error.path)
            self.assertEqual(str(objectID), error.objectId)

    @inlineCallbacks
    def testGetTagInstancePermissionDenied(self):
        result = TagAPI(self.user).create([(u'username/tag', u'description')])
        [(objectID, _)] = result
        TagValueAPI(self.user).set({objectID: {u'username/tag': False}})
        permissions = CachingPermissionAPI(self.user)
        permissions.set([(u'username/tag', Operation.READ_TAG_VALUE,
                          Policy.OPEN, [u'username'])])
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.getTagInstance(session, u'username/tag',
                                                  str(objectID))
            error = yield self.assertFailure(deferred, TNonexistentTag)
            self.assertEqual(u'username/tag', error.path)

    @inlineCallbacks
    def testGetTagInstanceReturnsTagValue(self):
        """
        L{FacadeTagValueMixin.getTagInstance} returns the L{TagValue}
        object in addition to the Thrift value.
        """
        result = TagAPI(self.user).create([(u'username/tag', u'description')])
        [(objectID, path)] = result
        TagValueAPI(self.user).set({objectID: {u'username/tag': None}})
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            value, tagValue = yield self.facade.getTagInstance(
                session, u'username/tag', str(objectID))
            self.assertEqual(None, guessValue(value))
            self.assertEqual(FluidinfoTagValue, type(tagValue))

    @inlineCallbacks
    def testGetTagInstanceWithNoneValue(self):
        """
        L{FacadeTagValueMixin.getTagInstance} returns a Thrift value for the
        specified L{Tag.path} and object ID.
        """
        result = TagAPI(self.user).create([(u'username/tag', u'description')])
        [(objectID, path)] = result
        TagValueAPI(self.user).set({objectID: {u'username/tag': None}})
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            value, tagValue = yield self.facade.getTagInstance(
                session, u'username/tag', str(objectID))
            self.assertEqual(None, guessValue(value))

    @inlineCallbacks
    def testGetTagInstanceWithBoolValue(self):
        """
        L{FacadeTagValueMixin.getTagInstance} returns a Thrift value for the
        specified L{Tag.path} and object ID.
        """
        result = TagAPI(self.user).create([(u'username/tag', u'description')])
        [(objectID, path)] = result
        TagValueAPI(self.user).set({objectID: {u'username/tag': False}})
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            value, tagValue = yield self.facade.getTagInstance(
                session, u'username/tag', str(objectID))
            self.assertEqual(False, guessValue(value))

    @inlineCallbacks
    def testGetTagInstanceWithIntValue(self):
        """
        L{FacadeTagValueMixin.getTagInstance} returns a Thrift value for the
        specified L{Tag.path} and object ID.
        """
        result = TagAPI(self.user).create([(u'username/tag', u'description')])
        [(objectID, path)] = result
        TagValueAPI(self.user).set({objectID: {u'username/tag': 42}})
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            value, tagValue = yield self.facade.getTagInstance(
                session, u'username/tag', str(objectID))
            self.assertEqual(42, guessValue(value))

    @inlineCallbacks
    def testGetTagInstanceWithFloatValue(self):
        """
        L{FacadeTagValueMixin.getTagInstance} returns a Thrift value for the
        specified L{Tag.path} and object ID.
        """
        result = TagAPI(self.user).create([(u'username/tag', u'description')])
        [(objectID, path)] = result
        TagValueAPI(self.user).set({objectID: {u'username/tag': 42.1}})
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            value, tagValue = yield self.facade.getTagInstance(
                session, u'username/tag', str(objectID))
            self.assertEqual(42.1, guessValue(value))

    @inlineCallbacks
    def testGetTagInstanceWithUnicodeValue(self):
        """
        L{FacadeTagValueMixin.getTagInstance} returns a Thrift value for the
        specified L{Tag.path} and object ID.
        """
        result = TagAPI(self.user).create([(u'username/tag', u'description')])
        [(objectID, path)] = result
        TagValueAPI(self.user).set({objectID: {u'username/tag': u'value'}})
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            value, tagValue = yield self.facade.getTagInstance(
                session, u'username/tag', str(objectID))
            self.assertEqual(u'value', guessValue(value))

    @inlineCallbacks
    def testGetTagInstanceWithSetValue(self):
        """
        L{FacadeTagValueMixin.getTagInstance} returns a Thrift value for the
        specified L{Tag.path} and object ID.
        """
        result = TagAPI(self.user).create([(u'username/tag', u'description')])
        [(objectID, path)] = result
        TagValueAPI(self.user).set(
            {objectID: {u'username/tag': [u'foo', u'bar']}})
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            value, tagValue = yield self.facade.getTagInstance(
                session, u'username/tag', str(objectID))
            self.assertEqual([u'foo', u'bar'], guessValue(value))

    @inlineCallbacks
    def testGetTagInstanceWithBinaryValue(self):
        """
        L{FacadeTagValueMixin.getTagInstance} returns a Thrift value for the
        specified L{Tag.path} and object ID.
        """
        TagAPI(self.user).create([(u'username/tag', u'description')])
        objectID = uuid4()
        thriftValue = createBinaryThriftValue('Hello, world!', 'text/plain')
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            yield self.facade.setTagInstance(session, u'username/tag',
                                             str(objectID), thriftValue)
            value, tagValue = yield self.facade.getTagInstance(
                session, u'username/tag', str(objectID))
            self.assertEqual('Hello, world!', value.binaryKey)
            self.assertEqual('text/plain', value.binaryKeyMimeType)

    @inlineCallbacks
    def testGetTagInstanceWithFluidDBID(self):
        """
        L{FacadeTagValueMixin.getTagInstance} correctly returns object IDs
        when the C{fluiddb/id} L{Tag} is requested.
        """
        TagAPI(self.user).create([(u'username/tag', u'description')])
        objectID = uuid4()
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            thriftValue = createBinaryThriftValue('Hello, world!',
                                                  'text/plain')
            yield self.facade.setTagInstance(session, u'username/tag',
                                             str(objectID), thriftValue)
            value, tagValue = yield self.facade.getTagInstance(
                session, u'fluiddb/id', str(objectID))
            self.assertEqual(str(objectID), guessValue(value))

    @inlineCallbacks
    def testSetTagInstanceWithUnknownTag(self):
        """
        L{FacadeTagValueMixin.setTagInstance} raises a
        L{TNonexistentTag} exception if the requested L{Tag.path}
        doesn't exist and the user doesn't have permission to create it.
        """
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            thriftValue = createThriftValue(42)
            deferred = self.facade.setTagInstance(session, u'unknown/path',
                                                  str(uuid4()), thriftValue)
            error = yield self.assertFailure(deferred, TNonexistentTag)
            self.assertEqual(u'unknown/path', error.path)

    @inlineCallbacks
    def testSetTagInstanceWithImplicitTag(self):
        """
        L{FacadeTagValueMixin.setTagInstance} implicitly creates a L{Tag} if
        the L{User} making the request has permission to do so.
        """
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            thriftValue = createThriftValue(42)
            objectID = uuid4()
            yield self.facade.setTagInstance(session, u'username/unknown',
                                             str(objectID), thriftValue)
            value, tagValue = yield self.facade.getTagInstance(
                session, u'username/unknown', str(objectID))
            self.assertEqual(42, guessValue(value))

    @inlineCallbacks
    def testSetTagInstanceWithImplicitTagWithMalformedPath(self):
        """
        L{FacadeTagValueMixin.setTagInstance} raises L{TInvalidPath} if one of
        the paths for a nonexistent L{Tag} is malformed.
        """
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            thriftValue = createThriftValue(42)
            objectID = uuid4()
            deferred = self.facade.setTagInstance(session, u'username/$bad!',
                                                  str(objectID), thriftValue)
            yield self.assertFailure(deferred, TInvalidPath)

    @inlineCallbacks
    def testSetTagInstancePermissionDenied(self):
        """
        L{FacadeTagValueMixin.setTagInstance} raises a
        L{TPathPermissionDenied} exception if the user doesn't have
        C{Operation.WRITE_TAG_VALUE} permission.
        """
        UserAPI().create([(u'fred', u'password', u'Fred',
                           u'fred@example.com')])
        user = getUser(u'username')
        permissions = CachingPermissionAPI(user)
        TagAPI(user).create([(u'fred/bar', u'description')])
        values = [(u'fred/bar', Operation.WRITE_TAG_VALUE,
                   Policy.CLOSED, [u'fred'])]
        permissions.set(values)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            thriftValue = createThriftValue(42)
            deferred = self.facade.setTagInstance(session, u'fred/bar',
                                                  str(uuid4()), thriftValue)
            error = yield self.assertFailure(deferred, TPathPermissionDenied)
            self.assertEqual(u'tag-values', error.category)
            self.assertEqual('write', error.action)
            self.assertEqual(u'fred/bar', error.path)

    @inlineCallbacks
    def testSetTagInstanceWithNoneValue(self):
        """L{FacadeTagValueMixin.setTagInstance} can store a C{None}."""
        TagAPI(self.user).create([(u'username/bar', u'description')])
        tag = getTags(paths=[u'username/bar']).one()
        objectID = uuid4()
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            thriftValue = createThriftValue(None)
            yield self.facade.setTagInstance(session, u'username/bar',
                                             str(objectID), thriftValue)

        self.store.rollback()
        value = getTagValues(values=[(objectID, tag.id)]).one()
        self.assertIdentical(self.user, value.creator)
        self.assertEqual(objectID, value.objectID)
        self.assertEqual(None, value.value)

    @inlineCallbacks
    def testSetTagInstanceWithBoolValue(self):
        """L{FacadeTagValueMixin.setTagInstance} can store a C{bool}."""
        TagAPI(self.user).create([(u'username/bar', u'description')])
        tag = getTags(paths=[u'username/bar']).one()
        objectID = uuid4()
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            thriftValue = createThriftValue(True)
            yield self.facade.setTagInstance(session, u'username/bar',
                                             str(objectID), thriftValue)

        self.store.rollback()
        value = getTagValues(values=[(objectID, tag.id)]).one()
        self.assertIdentical(self.user, value.creator)
        self.assertEqual(objectID, value.objectID)
        self.assertEqual(True, value.value)

    @inlineCallbacks
    def testSetTagInstanceWithIntValue(self):
        """L{FacadeTagValueMixin.setTagInstance} can store an C{int}."""
        TagAPI(self.user).create([(u'username/bar', u'description')])
        tag = getTags(paths=[u'username/bar']).one()
        objectID = uuid4()
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            thriftValue = createThriftValue(42)
            yield self.facade.setTagInstance(session, u'username/bar',
                                             str(objectID), thriftValue)

        self.store.rollback()
        value = getTagValues(values=[(objectID, tag.id)]).one()
        self.assertIdentical(self.user, value.creator)
        self.assertEqual(objectID, value.objectID)
        self.assertEqual(42, value.value)

    @inlineCallbacks
    def testSetTagInstanceWithFloatValue(self):
        """L{FacadeTagValueMixin.setTagInstance} can store a C{float}."""
        TagAPI(self.user).create([(u'username/bar', u'description')])
        tag = getTags(paths=[u'username/bar']).one()
        objectID = uuid4()
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            thriftValue = createThriftValue(42.31)
            yield self.facade.setTagInstance(session, u'username/bar',
                                             str(objectID), thriftValue)

        self.store.rollback()
        value = getTagValues(values=[(objectID, tag.id)]).one()
        self.assertIdentical(self.user, value.creator)
        self.assertEqual(objectID, value.objectID)
        self.assertEqual(42.31, value.value)

    @inlineCallbacks
    def testSetTagInstanceWithUnicodeValue(self):
        """
        L{FacadeTagValueMixin.setTagInstance} can store a C{unicode} string.
        """
        TagAPI(self.user).create([(u'username/bar', u'description')])
        tag = getTags(paths=[u'username/bar']).one()
        objectID = uuid4()
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            thriftValue = createThriftValue(u'foo bar')
            yield self.facade.setTagInstance(session, u'username/bar',
                                             str(objectID), thriftValue)

        self.store.rollback()
        value = getTagValues(values=[(objectID, tag.id)]).one()
        self.assertIdentical(self.user, value.creator)
        self.assertEqual(objectID, value.objectID)
        self.assertEqual(u'foo bar', value.value)

    @inlineCallbacks
    def testSetTagInstanceWithSetValue(self):
        """
        L{FacadeTagValueMixin.setTagInstance} can store a C{set} of C{unicode}
        strings.
        """
        TagAPI(self.user).create([(u'username/bar', u'description')])
        tag = getTags(paths=[u'username/bar']).one()
        objectID = uuid4()
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            thriftValue = createThriftValue([u'foo', u'bar'])
            yield self.facade.setTagInstance(session, u'username/bar',
                                             str(objectID), thriftValue)

        self.store.rollback()
        value = getTagValues(values=[(objectID, tag.id)]).one()
        self.assertIdentical(self.user, value.creator)
        self.assertEqual(objectID, value.objectID)
        self.assertEqual([u'foo', u'bar'], value.value)

    @inlineCallbacks
    def testSetTagInstanceWithBinaryValue(self):
        """
        L{FacadeTagValueMixin.setTagInstance} can store a binary L{TagValue}.
        """
        TagAPI(self.user).create([(u'username/bar', u'description')])
        objectID = uuid4()
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            thriftValue = createBinaryThriftValue('Hello, world!',
                                                  'text/plain')
            yield self.facade.setTagInstance(session, u'username/bar',
                                             str(objectID), thriftValue)
            value, tagValue = yield self.facade.getTagInstance(
                session, u'username/bar', str(objectID))
            self.assertEqual('text/plain', value.binaryKeyMimeType)
            self.assertEqual('Hello, world!', value.binaryKey)

    @inlineCallbacks
    def testHasTagInstanceUnknownTag(self):
        """
        L{FacadeTagValueMixin.hasTagInstance} raises a L{TNonexistentTag}
        exception if the requested L{Tag.path} doesn't exist.
        """
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.hasTagInstance(session, u'username/unknown',
                                                  str(uuid4()))
            error = yield self.assertFailure(deferred, TNonexistentTag)
            self.assertEqual(u'username/unknown', error.path)

    @inlineCallbacks
    def testHasTagInstancePermissionDenied(self):
        """
        L{FacadeTagValueMixin.hasTagInstance} raises a
        L{TNonexistentTag} exception if the user doesn't have
        C{Operation.READ_TAG_VALUE} permission.
        """
        UserAPI().create([(u'fred', u'password', u'User',
                           u'fred@example.com')])
        user = getUser(u'username')
        permissions = CachingPermissionAPI(user)

        TagAPI(user).create([(u'fred/bar', u'description')])
        tag = getTags(paths=[u'fred/bar']).one()
        values = [(u'fred/bar', Operation.READ_TAG_VALUE, Policy.CLOSED,
                   [u'fred'])]
        permissions.set(values)
        objectID = uuid4()
        createTagValue(user.id, tag.id, objectID, 42)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.hasTagInstance(session, u'fred/bar',
                                                  str(objectID))
            error = yield self.assertFailure(deferred, TNonexistentTag)
            self.assertEqual(u'fred/bar', error.path)

    @inlineCallbacks
    def testHasTagInstanceExists(self):
        """
        L{FacadeTagValueMixin.hasTagInstance} returns C{True} if a L{Tag.path}
        on an object exists.
        """
        TagAPI(self.user).create([(u'username/bar', u'description')])
        tag = getTags(paths=[u'username/bar']).one()
        objectID = uuid4()
        createTagValue(self.user.id, tag.id, objectID, 42)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            results = yield self.facade.hasTagInstance(
                session, u'username/bar', str(objectID))
            self.assertTrue(results)

    @inlineCallbacks
    def testHasTagInstanceNotExists(self):
        """
        L{FacadeTagValueMixin.hasTagInstance} returns C{False} if a L{Tag.path}
        on an object doesn't exist.
        """
        TagAPI(self.user).create([(u'username/bar', u'description')])
        objectID = uuid4()
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            results = yield self.facade.hasTagInstance(
                session, u'username/bar', str(objectID))
            results = guessValue(results)
            self.assertFalse(results)

    @inlineCallbacks
    def testDeleteTagInstanceUnknownTag(self):
        """
        L{FacadeTagValueMixin.deleteTagInstance} raises a L{TNonexistentTag}
        exception if the requested L{Tag.path} doesn't exist.
        """
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.deleteTagInstance(
                session, u'username/unknown', str(uuid4()))
            error = yield self.assertFailure(deferred, TNonexistentTag)
            self.assertEqual(u'username/unknown', error.path)

    @inlineCallbacks
    def testDeleteTagInstancePermissionDenied(self):
        """
        L{FacadeTagValueMixin.deleteTagInstance} raises a
        L{TPathPermissionDenied} exception if the user doesn't have
        C{Operation.DELETE_TAG_VALUE} permission.
        """
        UserAPI().create([(u'fred', u'password', u'User',
                           u'fred@example.com')])
        user = getUser(u'username')
        permissions = CachingPermissionAPI(user)

        TagAPI(user).create([(u'fred/bar', u'description')])
        tag = getTags(paths=[u'fred/bar']).one()
        values = [(u'fred/bar', Operation.DELETE_TAG_VALUE, Policy.CLOSED,
                   [u'fred'])]
        permissions.set(values)
        objectID = uuid4()
        createTagValue(user.id, tag.id, objectID, 42)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.deleteTagInstance(session, u'fred/bar',
                                                     str(objectID))
            error = yield self.assertFailure(deferred, TPathPermissionDenied)
            self.assertEqual(u'tag-values', error.category)
            self.assertEqual('delete', error.action)
            self.assertEqual(u'fred/bar', error.path)

    @inlineCallbacks
    def testDeleteTagInstance(self):
        """
        L{FacadeTagValueMixin.deleteTagInstance} deletes a L{TagValue} on a
        given object.
        """
        TagAPI(self.user).create([(u'username/bar', u'description')])
        tag = getTags(paths=[u'username/bar']).one()
        objectID = uuid4()
        createTagValue(self.user.id, tag.id, objectID, 42)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            yield self.facade.deleteTagInstance(session, u'username/bar',
                                                str(objectID))

        self.store.rollback()
        result = getTagValues([(objectID, tag.id)])
        self.assertTrue(result.is_empty())


class FacadeTagValueMixinQueriesTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('client', IndexResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(FacadeTagValueMixinQueriesTest, self).setUp()
        createSystemData()
        self.transact = Transact(self.threadPool)
        factory = FluidinfoSessionFactory('API-9000')
        self.facade = Facade(self.transact, factory)
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = CachingPermissionAPI(self.user)
        self.store.commit()
        self.config.set('service', 'development', 'true')

    @inlineCallbacks
    def testResolveQueryWithWrongEncoding(self):
        """
        L{FacadeTagValueMixin.resolveQuery} raises L{TBadRequest} if the query
        is not properly encoded in UTF-8.
        """
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.resolveQuery(session,
                                                'fluiddb/about == "\xFF"')
            yield self.assertFailure(deferred, TBadRequest)

    @inlineCallbacks
    def testResolveQueryWithParseError(self):
        """
        L{FacadeTagValueMixin.resolveQuery} raises L{TParseError} if the query
        is not well formed.
        """
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.resolveQuery(session, 'wrong query >:)')
            yield self.assertFailure(deferred, TParseError)

    @inlineCallbacks
    def testResolveQueryWithIllegalQuery(self):
        """
        L{FacadeTagValueMixin.resolveQuery} raises L{TBadRequest} if the query
        contains an illegal expression.
        """
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.resolveQuery(session, 'has fluiddb/about')
            yield self.assertFailure(deferred, TBadRequest)

    @inlineCallbacks
    def testResolveQueryWithSearchError(self):
        """
        L{FacadeTagValueMixin.resolveQuery} raises L{TParseError} if the query
        is not well formed.
        """
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.resolveQuery(session, 'has fluiddb/id')
            yield self.assertFailure(deferred, TParseError)

    @inlineCallbacks
    def testResolveQueryWithPermissionDeniedError(self):
        """
        L{FacadeTagValueMixin.resolveQuery} raises L{TNonexistentTag} if
        the user doesn't have READ permissions on tags in the query.
        """
        TagAPI(self.user).create([(u'username/tag', u'description')])
        permissions = CachingPermissionAPI(self.user)
        values = [(u'username/tag', Operation.READ_TAG_VALUE,
                   Policy.CLOSED, [])]
        permissions.set(values)
        self.store.commit()
        runDataImportHandler(self.client.url)

        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.resolveQuery(session,
                                                'username/tag = "value"')
            error = yield self.assertFailure(deferred, TNonexistentTag)
            self.assertEqual(u'username/tag', error.path)

    @inlineCallbacks
    def testResolveQueryWithUnknownPaths(self):
        """
        L{FacadeTagValueMixin.resolveQuery} raises L{TNonexistentTag} if a path
        in the query doesn't exist.
        """
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.resolveQuery(session, 'unknown/tag = 26')
            error = yield self.assertFailure(deferred, TNonexistentTag)
            self.assertEqual('unknown/tag', error.path)

    @inlineCallbacks
    def testResolveQuery(self):
        """
        L{FacadeTagValueMixin.resolveQuery} returns the results of a query.
        """
        TagAPI(self.user).create([(u'username/tag1', u'description'),
                                  (u'username/tag2', u'description')])
        self.store.commit()
        object1 = uuid4()
        object2 = uuid4()
        TagValueAPI(self.user).set({object1: {u'username/tag1': 20,
                                              u'username/tag2': 20},
                                    object2: {u'username/tag1': 20,
                                              u'username/tag2': 20},
                                    uuid4(): {u'username/tag1': 20,
                                              u'username/tag2': 10}})
        runDataImportHandler(self.client.url)
        with login(u'username', uuid4(), self.transact) as session:
            results = yield self.facade.resolveQuery(session,
                                                     'username/tag2 = 20')
            self.assertEqual(sorted([str(object1), str(object2)]),
                             sorted(results))

    @inlineCallbacks
    def testUpdateValuesForQueriesWithInvalidQuery(self):
        """
        L{FacadeTagValueMixin.updateValuesForQueries} raises a
        L{TParseError} exception if the incoming L{Query} can't be parsed.
        """
        queryItems = [(u'username/unknown 42',
                       [TagPathAndValue(u'username/unknown', 2600)])]
        valuesQuerySchema = ValuesQuerySchema(queryItems)
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.updateValuesForQueries(session,
                                                          valuesQuerySchema)
            yield self.assertFailure(deferred, TParseError)

    @inlineCallbacks
    def testUpdateValuesForQueriesWithIllegalQuery(self):
        """
        L{FacadeTagValueMixin.updateValuesForQueries} raises a L{TBadRequest}
        exception if the incoming L{Query} contains an illegal expression.
        """
        queryItems = [(u'has fluiddb/about',
                       [TagPathAndValue(u'username/unknown', 2600)])]
        valuesQuerySchema = ValuesQuerySchema(queryItems)
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.updateValuesForQueries(session,
                                                          valuesQuerySchema)
            yield self.assertFailure(deferred, TBadRequest)

    @inlineCallbacks
    def testUpdateValuesForQueriesWithSearchError(self):
        """
        L{FacadeTagValueMixin.updateValuesForQueries} raises a
        L{TParseError} exception if the incoming L{Query} can't be parsed.
        """
        value = TagPathAndValue(u'username/unknown', 2600)
        items = [(u'has fluiddb/id', [value])]
        schema = ValuesQuerySchema(items)
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.updateValuesForQueries(session, schema)
            yield self.assertFailure(deferred, TParseError)

    @inlineCallbacks
    def testUpdateValuesForQueriesWithUnknownTagInQuery(self):
        """
        L{FacadeTagValueMixin.updateValuesForQueries} raises a
        L{TNonexistentTag} exception if any of the requested L{Tag.path} in the
        L{Query} doesn't exist.
        """
        SecureTagAPI(self.user).create([(u'username/bar', u'description'),
                                        (u'username/foo', u'description')])
        objectID1 = uuid4()
        objectID2 = uuid4()

        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        values = {objectID1: {u'username/foo': 12},
                  objectID2: {u'username/foo': 42}}

        valuesAPI = SecureTagValueAPI(self.user)
        valuesAPI.set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            queryItems = [
                (u'username/unknown-to-read = 42 or username/foo = 12',
                 [TagPathAndValue(u'username/bar', 2600)])]
            valuesQuerySchema = ValuesQuerySchema(queryItems)
            deferred = self.facade.updateValuesForQueries(session,
                                                          valuesQuerySchema)
            yield self.assertFailure(deferred, TNonexistentTag)

    @inlineCallbacks
    def testUpdateValuesForQueriesWithUncreatablePaths(self):
        """
        L{FacadeTagValueMixin.updateValuesForQueries} raises a
        L{TNonexistentTag} exception if any of the L{Tag.path}s to set don't
        exist and the L{User} making the request doesn't have permission to
        create them.
        """
        TagAPI(self.user).create([(u'username/bar', u'description')])
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        values = {uuid4(): {u'username/bar': 42}}
        SecureTagValueAPI(self.user).set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()

        with login(u'username', uuid4(), self.transact) as session:
            queryItems = [
                (u'username/bar = 42',
                 [TagPathAndValue(u'wubble/unknown-to-set', 2600)])]
            valuesQuerySchema = ValuesQuerySchema(queryItems)
            deferred = self.facade.updateValuesForQueries(session,
                                                          valuesQuerySchema)
            error = yield self.assertFailure(deferred, TNonexistentTag)
            self.assertEqual(u'wubble/unknown-to-set', error.path)

    @inlineCallbacks
    def testUpdateValuesForQueriesWithImplicitTags(self):
        """
        L{FacadeTagValueMixin.updateValuesForQueries} implicitly creates
        missing L{Tag}s if the L{User} has permission to create them.
        """
        TagAPI(self.user).create([(u'username/bar', u'description')])
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        objectID = uuid4()
        values = {objectID: {u'username/bar': 42}}
        tagValues = SecureTagValueAPI(self.user)
        tagValues.set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()

        with login(u'username', uuid4(), self.transact) as session:
            queryItems = [(u'username/bar = 42',
                           [TagPathAndValue(u'username/unknown', 2600)])]
            valuesQuerySchema = ValuesQuerySchema(queryItems)
            yield self.facade.updateValuesForQueries(session,
                                                     valuesQuerySchema)
            result = tagValues.get([objectID], [u'username/unknown'])
            tagValue = result[objectID][u'username/unknown'].value
            self.assertEqual(2600, tagValue)

    @inlineCallbacks
    def testUpdateValuesForQueriesWithImplicitTagsWithMalformedPaths(self):
        """
        L{FacadeTagValueMixin.updateValuesForQueries} raises L{TInvalidPath} if
        the given paths for nonexitent L{Tags} are invalid.
        """
        TagAPI(self.user).create([(u'username/bar', u'description')])
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        objectID = uuid4()
        values = {objectID: {u'username/bar': 42}}
        tagValues = SecureTagValueAPI(self.user)
        tagValues.set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()

        with login(u'username', uuid4(), self.transact) as session:
            queryItems = [(u'username/bar = 42',
                           [TagPathAndValue(u'username/$bad!', 2600)])]
            valuesQuerySchema = ValuesQuerySchema(queryItems)
            deferred = self.facade.updateValuesForQueries(session,
                                                          valuesQuerySchema)
            yield self.assertFailure(deferred, TInvalidPath)

    @inlineCallbacks
    def testUpdateValuesForQueriesWithImplicitNamespaces(self):
        """
        L{FacadeTagValueMixin.updateValuesForQueries} implicitly creates
        missing L{Namespace}s and L{Tag}s if the L{User} has permission to
        create them.
        """
        TagAPI(self.user).create([(u'username/bar', u'description')])
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        objectID = uuid4()
        values = {objectID: {u'username/bar': 42}}
        tagValues = SecureTagValueAPI(self.user)
        tagValues.set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()

        with login(u'username', uuid4(), self.transact) as session:
            queryItems = [(u'username/bar = 42',
                           [TagPathAndValue(u'username/bar/foo', 2600)])]
            valuesQuerySchema = ValuesQuerySchema(queryItems)
            yield self.facade.updateValuesForQueries(session,
                                                     valuesQuerySchema)
            result = tagValues.get([objectID], [u'username/bar/foo'])
            tagValue = result[objectID][u'username/bar/foo'].value
            self.assertEqual(2600, tagValue)

    @inlineCallbacks
    def testUpdateValuesForQueriesWithImplicitNestedNamespaces(self):
        """
        L{FacadeTagValueMixin.updateValuesForQueries} implicitly creates
        missing L{Namespace}s and L{Tag}s if the L{User} has permission to
        create them.
        """
        TagAPI(self.user).create([(u'username/bar', u'description')])
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        objectID = uuid4()
        values = {objectID: {u'username/bar': 42}}
        tagValues = SecureTagValueAPI(self.user)
        tagValues.set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()

        with login(u'username', uuid4(), self.transact) as session:
            queryItems = [(u'username/bar = 42',
                           [TagPathAndValue(u'username/bar/foo/baz', 2600)])]
            valuesQuerySchema = ValuesQuerySchema(queryItems)
            yield self.facade.updateValuesForQueries(session,
                                                     valuesQuerySchema)
            result = tagValues.get([objectID], [u'username/bar/foo/baz'])
            tagValue = result[objectID][u'username/bar/foo/baz'].value
            self.assertEqual(2600, tagValue)

    @inlineCallbacks
    def testUpdateValuesForQueriesWithReadPermissionDenied(self):
        """
        L{FacadeTagValueMixin.updateValuesForQueries} raises a
        L{TNonexistentTag} exception if the user doesn't have
        C{Operation.READ_TAG_VALUE} permission on any of the L{Tag}s in the
        L{Query}.
        """
        UserAPI().create([(u'fred', u'password', u'Fred',
                           u'fred@example.com')])
        user = getUser(u'username')
        permissions = CachingPermissionAPI(user)
        TagAPI(user).create([(u'fred/bar', u'description'),
                             (u'fred/unreadable', u'description')])
        values = [(u'fred/unreadable', Operation.READ_TAG_VALUE,
                   Policy.CLOSED, [u'fred'])]
        permissions.set(values)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            queryItems = [(u'fred/unreadable = 42',
                           [TagPathAndValue(u'fred/bar', 2600)])]
            valuesQuerySchema = ValuesQuerySchema(queryItems)
            deferred = self.facade.updateValuesForQueries(session,
                                                          valuesQuerySchema)
            error = yield self.assertFailure(deferred, TNonexistentTag)
            self.assertEqual(u'fred/unreadable', error.path)

    @inlineCallbacks
    def testUpdateValuesForQueriesWithWritePermissionDenied(self):
        """
        L{FacadeTagValueMixin.updateValuesForQueries} raises a
        L{TPathPermissionDenied} exception if the user doesn't have
        C{Operation.WRITE_TAG_VALUE} permission on any of the outgoing L{Tag}s.
        """
        UserAPI().create([(u'fred', u'password', u'Fred',
                           u'fred@example.com')])
        user = getUser(u'fred')
        permissions = CachingPermissionAPI(user)
        TagAPI(user).create([(u'fred/bar', u'description'),
                             (u'fred/unwritable', u'description')])
        values = {uuid4(): {u'fred/bar': 42}}
        SecureTagValueAPI(user).set(values)
        runDataImportHandler(self.client.url)
        values = [(u'fred/unwritable', Operation.WRITE_TAG_VALUE,
                   Policy.CLOSED, [u'fred'])]
        permissions.set(values)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            queryItems = [(u'fred/bar = 42',
                           [TagPathAndValue(u'fred/unwritable', 2600)])]
            valuesQuerySchema = ValuesQuerySchema(queryItems)
            deferred = self.facade.updateValuesForQueries(session,
                                                          valuesQuerySchema)
            error = yield self.assertFailure(deferred, TPathPermissionDenied)
            self.assertEqual(u'tag-values', error.category)
            self.assertEqual('write', error.action)
            self.assertEqual(u'fred/unwritable', error.path)

    @inlineCallbacks
    def testUpdateValuesForQueriesWithEmptyQueryResults(self):
        """
        L{FacadeTagValueMixin.updateValuesForQueries} does not fail if a
        L{Query} results in an empty C{set}.
        """
        SecureTagAPI(self.user).create([(u'username/bar', u'description')])
        objectID = uuid4()
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        values = {objectID: {u'username/bar': 42}}
        valuesAPI = SecureTagValueAPI(self.user)
        valuesAPI.set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            queryItems = [(u'username/bar = 123',
                           [TagPathAndValue(u'username/bar', 2600)])]
            valuesQuerySchema = ValuesQuerySchema(queryItems)
            yield self.facade.updateValuesForQueries(session,
                                                     valuesQuerySchema)
            result = valuesAPI.get([objectID], [u'username/bar'])
            tagValue = result[objectID][u'username/bar'].value
            self.assertEqual(42, tagValue)

    @inlineCallbacks
    def testUpdateValuesForQueriesWithUnicodeAboutValue(self):
        """
        L{FacadeTagValueMixin.updateValuesForQueries} can store a C{unicode}
        string when the query involves a C{unicode} about-value.
        """
        with login(u'username', uuid4(), self.transact) as session:
            SecureTagAPI(self.user).create([(u'username/bar', u'description')])
            objectID = yield self.facade.createObject(
                session, about=u'éric serra'.encode('utf-8'))
            objectID = UUID(objectID)

        self.store.rollback()
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        values = {objectID: {u'username/bar': 42}}
        valuesAPI = SecureTagValueAPI(self.user)
        valuesAPI.set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()

        with login(u'username', uuid4(), self.transact) as session:
            queryItems = [(u'fluiddb/about = "éric serra"',
                           [TagPathAndValue(u'username/bar', 2600)])]
            valuesQuerySchema = ValuesQuerySchema(queryItems)
            yield self.facade.updateValuesForQueries(session,
                                                     valuesQuerySchema)
            result = valuesAPI.get([objectID], [u'fluiddb/about'])
            about = result[objectID][u'fluiddb/about'].value
            self.assertEqual(u'éric serra', about)
            result = valuesAPI.get([objectID], [u'username/bar'])
            tagValue = result[objectID][u'username/bar'].value
            self.assertEqual(2600, tagValue)

    @inlineCallbacks
    def testUpdateValuesForQueriesWithIntValue(self):
        """
        L{FacadeTagValueMixin.updateValuesForQueries} can store an C{int}.
        """
        SecureTagAPI(self.user).create([(u'username/bar', u'description')])
        objectID = uuid4()
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        values = {objectID: {u'username/bar': 42}}
        valuesAPI = SecureTagValueAPI(self.user)
        valuesAPI.set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            queryItems = [(u'username/bar = 42',
                           [TagPathAndValue(u'username/bar', 2600)])]
            valuesQuerySchema = ValuesQuerySchema(queryItems)
            yield self.facade.updateValuesForQueries(session,
                                                     valuesQuerySchema)
            result = valuesAPI.get([objectID], [u'username/bar'])
            tagValue = result[objectID][u'username/bar'].value
            self.assertEqual(2600, tagValue)

    @inlineCallbacks
    def testUpdateValuesForQueriesWithMultipleQueries(self):
        """
        L{FacadeTagValueMixin.updateValuesForQueries} can solve multiple
        L{Query}s and store the appropiate L{TagValue}s.
        """
        SecureTagAPI(self.user).create([(u'username/bar', u'description')])
        objectID1 = uuid4()
        objectID2 = uuid4()
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        values = {objectID1: {u'username/bar': 42},
                  objectID2: {u'username/bar': 1234}}
        valuesAPI = SecureTagValueAPI(self.user)
        valuesAPI.set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            queryItems = [(u'username/bar = 42',
                           [TagPathAndValue(u'username/bar', 2600)]),
                          (u'username/bar = 1234',
                           [TagPathAndValue(u'username/bar', 4321)])]
            valuesQuerySchema = ValuesQuerySchema(queryItems)
            yield self.facade.updateValuesForQueries(session,
                                                     valuesQuerySchema)
            result = valuesAPI.get([objectID1, objectID2], [u'username/bar'])
            tagValue1 = result[objectID1][u'username/bar'].value
            tagValue2 = result[objectID2][u'username/bar'].value
            self.assertEqual(2600, tagValue1)
            self.assertEqual(4321, tagValue2)

    @inlineCallbacks
    def testUpdateValuesForQueriesWithFloatValue(self):
        """
        L{FacadeTagValueMixin.updateValuesForQueries} can store a C{float}.
        """
        SecureTagAPI(self.user).create([(u'username/bar', u'description')])
        objectID = uuid4()
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        values = {objectID: {u'username/bar': 42}}
        valuesAPI = SecureTagValueAPI(self.user)
        valuesAPI.set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            queryItems = [(u'username/bar = 42',
                           [TagPathAndValue(u'username/bar', 12.34)])]
            valuesQuerySchema = ValuesQuerySchema(queryItems)
            yield self.facade.updateValuesForQueries(session,
                                                     valuesQuerySchema)
            result = valuesAPI.get([objectID], [u'username/bar'])
            tagValue = result[objectID][u'username/bar'].value
            self.assertEqual(12.34, tagValue)

    @inlineCallbacks
    def testUpdateValuesForQueriesWithSetValue(self):
        """
        L{FacadeTagValueMixin.updateValuesForQueries} can store a C{set} of
        C{unicode} strings.
        """
        SecureTagAPI(self.user).create([(u'username/bar', u'description')])
        objectID = uuid4()
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        values = {objectID: {u'username/bar': 42}}
        valuesAPI = SecureTagValueAPI(self.user)
        valuesAPI.set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            queryItems = [(u'username/bar = 42',
                           [TagPathAndValue(u'username/bar',
                                            [u'foo', u'bar'])])]
            valuesQuerySchema = ValuesQuerySchema(queryItems)
            yield self.facade.updateValuesForQueries(session,
                                                     valuesQuerySchema)
            result = valuesAPI.get([objectID], [u'username/bar'])
            self.assertEqual([u'foo', u'bar'],
                             result[objectID][u'username/bar'].value)

    @inlineCallbacks
    def testUpdateValuesForQueriesWithNoneValue(self):
        """
        L{FacadeTagValueMixin.updateValuesForQueries} can store a C{None}.
        """
        SecureTagAPI(self.user).create([(u'username/bar', u'description')])
        objectID = uuid4()
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        values = {objectID: {u'username/bar': 42}}
        valuesAPI = SecureTagValueAPI(self.user)
        valuesAPI.set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            queryItems = [(u'username/bar = 42',
                           [TagPathAndValue(u'username/bar', None)])]
            valuesQuerySchema = ValuesQuerySchema(queryItems)
            yield self.facade.updateValuesForQueries(session,
                                                     valuesQuerySchema)
            result = valuesAPI.get([objectID], [u'username/bar'])
            self.assertEqual(None,
                             result[objectID][u'username/bar'].value)

    @inlineCallbacks
    def testUpdateValuesForQueriesWithBoolValue(self):
        """
        L{FacadeTagValueMixin.updateValuesForQueries} can store a C{bool}.
        """
        SecureTagAPI(self.user).create([(u'username/bar', u'description')])
        objectID = uuid4()
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        values = {objectID: {u'username/bar': 42}}
        valuesAPI = SecureTagValueAPI(self.user)
        valuesAPI.set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            queryItems = [(u'username/bar = 42',
                           [TagPathAndValue(u'username/bar', True)])]
            valuesQuerySchema = ValuesQuerySchema(queryItems)
            yield self.facade.updateValuesForQueries(session,
                                                     valuesQuerySchema)
            result = valuesAPI.get([objectID], [u'username/bar'])
            self.assertTrue(result[objectID][u'username/bar'])

    @inlineCallbacks
    def testUpdateValuesForQueriesWithMixedValues(self):
        """
        L{FacadeTagValueMixin.updateValuesForQueries} can store L{TagValue}s
        of different types: C{bool}, C{None}, C{int}, C{float}, C{unicode} and
        C{set} of C{unicode}.
        """
        SecureTagAPI(self.user).create([(u'username/test1', u'description'),
                                        (u'username/test2', u'description'),
                                        (u'username/test3', u'description'),
                                        (u'username/test4', u'description'),
                                        (u'username/test5', u'description'),
                                        (u'username/test6', u'description')])
        paths = [u'username/test1', u'username/test2', u'username/test3',
                 u'username/test4', u'username/test5', u'username/test6']
        tags = list(getTags(paths=paths))
        objectID = uuid4()
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        values = {objectID: {u'username/test1': 42}}
        SecureTagValueAPI(self.user).set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            queryValues = {u'username/test1': True,
                           u'username/test2': None,
                           u'username/test3': 123,
                           u'username/test4': 12.34,
                           u'username/test5': u'test',
                           u'username/test6': [u'a', u'b']}
            valuesQuerySchema = ValuesQuerySchema(
                [(u'username/test1 = 42',
                  [TagPathAndValue(path, value) for path, value
                   in queryValues.iteritems()])])
            yield self.facade.updateValuesForQueries(session,
                                                     valuesQuerySchema)
            expected = {objectID: queryValues}
            result = dict()
            tagPairs = [(objectID, tag.id) for tag in tags]
            values = getTagValues(values=tagPairs)
            for value in values:
                if not result.get(value.objectID):
                    result[value.objectID] = {}
                result[value.objectID][value.tag.path] = value.value
            self.assertEqual(expected, result)

    @inlineCallbacks
    def testDeleteValuesForQueryWithInvalidQuery(self):
        """
        L{FacadeTagValueMixin.deleteValuesForQuery} raises a L{TParseError}
        exception if the incoming L{Query} can't be parsed.
        """
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.deleteValuesForQuery(
                session, u'username/unknown 42', [u'username/unknown'])
            yield self.assertFailure(deferred, TParseError)

    @inlineCallbacks
    def testDeleteValuesForQueryWithIllegalQuery(self):
        """
        L{FacadeTagValueMixin.deleteValuesForQuery} raises a L{TBadRequest}
        exception if the incoming L{Query} contains an illegal expression.
        """
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.deleteValuesForQuery(
                session, u'has fluiddb/about', [u'username/unknown'])
            yield self.assertFailure(deferred, TBadRequest)

    @inlineCallbacks
    def testDeleteValuesForQueryWithSearch(self):
        """
        L{FacadeTagValueMixin.deleteValuesForQuery} raises a L{TParseError}
        exception if the incoming L{Query} can't be parsed.
        """
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.deleteValuesForQuery(
                session, u'has fluiddb/id', [u'username/unknown'])
            yield self.assertFailure(deferred, TParseError)

    @inlineCallbacks
    def testDeleteValuesForQueryWithUnknownTag(self):
        """
        L{FacadeTagValueMixin.deleteValuesForQuery} raises a
        L{TNonexistentTag} exception if any of the requested L{Tag.path} don't
        exist.
        """
        SecureTagAPI(self.user).create([(u'username/bar', u'description'),
                                        (u'username/foo', u'description')])
        objectID1 = uuid4()
        objectID2 = uuid4()
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        values = {objectID1: {u'username/foo': 12,
                              u'username/bar': u'test1'},
                  objectID2: {u'username/foo': 42,
                              u'username/bar': u'test2'}}
        valuesAPI = SecureTagValueAPI(self.user)
        valuesAPI.set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.deleteValuesForQuery(
                session, u'username/unknown = 42 or username/foo = 12',
                [u'username/bar'])
            yield self.assertFailure(deferred, TNonexistentTag)

    @inlineCallbacks
    def testDeleteValuesForQueryWithMissingTag(self):
        """
        L{FacadeTagValueMixin.deleteValuesForQuery} does not raise an exception
        if any of the requested L{Tag.path} are not present on any matching
        objects.
        """
        SecureTagAPI(self.user).create([(u'username/bar', u'description'),
                                        (u'username/foo', u'description')])
        objectID1 = uuid4()
        objectID2 = uuid4()
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        values = {objectID1: {u'username/foo': 12},
                  objectID2: {u'username/foo': 42,
                              u'username/bar': u'test2'}}
        valuesAPI = SecureTagValueAPI(self.user)
        valuesAPI.set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            yield self.facade.deleteValuesForQuery(
                session, u'username/foo = 12',
                [u'username/bar'])

    @inlineCallbacks
    def testDeleteValuesForQueryWithReadPermissionDenied(self):
        """
        L{FacadeTagValueMixin.deleteValuesForQuery} raises a
        L{TNonexistentTag} exception if the user doesn't have
        C{Operation.READ_TAG_VALUE} permission on any of the L{Tag}s in the
        L{Query}.
        """
        UserAPI().create([(u'fred', u'password', u'Fred',
                           u'fred@example.com')])
        user = getUser(u'username')
        permissions = CachingPermissionAPI(user)
        TagAPI(user).create([(u'fred/bar', u'description')])
        values = [(u'fred/bar', Operation.READ_TAG_VALUE,
                   Policy.CLOSED, [u'fred'])]
        permissions.set(values)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.deleteValuesForQuery(
                session, u'fred/bar = 42', [u'fred/bar'])
            error = yield self.assertFailure(deferred, TNonexistentTag)
            self.assertEqual(u'fred/bar', error.path)

    @inlineCallbacks
    def testDeleteValuesForQueryWithDeletePermissionDenied(self):
        """
        L{FacadeTagValueMixin.deleteValuesForQuery} raises a
        L{TPathPermissionDenied} exception if the user doesn't have
        C{Operation.DELETE_TAG_VALUE} permission on any of the outgoing
        L{Tag}s.
        """
        UserAPI().create([(u'fred', u'password', u'Fred',
                           u'fred@example.com')])
        user = getUser(u'fred')
        permissions = CachingPermissionAPI(user)
        TagAPI(user).create([(u'fred/bar', u'description'),
                             (u'fred/foo', u'description')])
        SecureTagValueAPI(user).set({uuid4(): {u'fred/foo': 42}})
        runDataImportHandler(self.client.url)
        permissions.set([(u'fred/foo', Operation.DELETE_TAG_VALUE,
                          Policy.CLOSED, [u'fred'])])
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.deleteValuesForQuery(
                session, u'fred/foo = 42', [u'fred/foo'])
            error = yield self.assertFailure(deferred, TPathPermissionDenied)
            self.assertEqual(u'tag-values', error.category)
            self.assertEqual('delete', error.action)
            self.assertEqual(u'fred/foo', error.path)

    @inlineCallbacks
    def testDeleteValuesForQuery(self):
        """
        L{FacadeTagValueMixin.deleteValuesForQuery} deletes the L{TagValue}
        of an object if the L{Query} matches and the L{User} has permissions.
        """
        SecureTagAPI(self.user).create([(u'username/bar', u'description')])
        objectID1 = uuid4()
        objectID2 = uuid4()
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        values = {objectID1: {u'username/bar': 42},
                  objectID2: {u'username/bar': 123}}
        valuesAPI = SecureTagValueAPI(self.user)
        valuesAPI.set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            yield self.facade.deleteValuesForQuery(
                session, u'username/bar = 42', [u'username/bar'])
            result = valuesAPI.get([objectID1, objectID2],
                                   [u'username/bar'])
            tagValue = result[objectID2][u'username/bar'].value
            self.assertEqual(123, tagValue)

    @inlineCallbacks
    def testDeleteValuesForQueryWithoutReturnTags(self):
        """
        L{FacadeTagValueMixin.deleteValuesForQuery} deletes all available
        L{TagValue}s for the objects the L{Query} matches and that the L{User}
        has L{Operation.DELETE_TAG_VALUE} permission for.
        """
        SecureTagAPI(self.user).create([(u'username/bar', u'description')])
        objectID1 = uuid4()
        objectID2 = uuid4()
        valuesAPI = SecureTagValueAPI(self.user)
        valuesAPI.set({objectID1: {u'username/bar': 42},
                       objectID2: {u'username/bar': 123}})
        runDataImportHandler(self.client.url)
        self.store.commit()

        with login(u'username', uuid4(), self.transact) as session:
            yield self.facade.deleteValuesForQuery(session,
                                                   u'username/bar = 42')
            result = valuesAPI.get([objectID1, objectID2], [u'username/bar'])
            self.assertEqual(1, len(result))
            self.assertEqual(1, len(result[objectID2]))
            self.assertEqual(123, result[objectID2][u'username/bar'].value)

    @inlineCallbacks
    def testDeleteValuesForQueryOnlyConsidersSpecifiedTags(self):
        """
        L{FacadeTagValueMixin.deleteValuesForQuery} deletes L{TagValue}s for
        the objects the L{Query} matches and that match the specified L{Tag}
        paths.
        """
        objectID = uuid4()
        values = SecureTagValueAPI(self.user)
        values.set({objectID: {u'username/bar': 42, u'username/foo': 123}})
        runDataImportHandler(self.client.url)
        self.store.commit()

        with login(u'username', uuid4(), self.transact) as session:
            yield self.facade.deleteValuesForQuery(
                session, u'has username/bar', [u'username/bar'])
            result = values.get([objectID], [u'username/bar', u'username/foo'])
            self.assertEqual(1, len(result))
            self.assertEqual(1, len(result[objectID]))
            self.assertEqual(123, result[objectID][u'username/foo'].value)

    @inlineCallbacks
    def testDeleteValuesForQueryWithEmptyQueryResults(self):
        """
        L{FacadeTagValueMixin.deleteValuesForQuery} does not fail if a
        L{Query} results in an empty C{set}.
        """
        SecureTagAPI(self.user).create([(u'username/bar', u'description')])
        objectID = uuid4()
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        values = {objectID: {u'username/bar': 42}}
        valuesAPI = SecureTagValueAPI(self.user)
        valuesAPI.set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            yield self.facade.deleteValuesForQuery(
                session, u'username/bar = 2600', [u'username/bar'])
            result = valuesAPI.get([objectID], [u'username/bar'])
            tagValue = result[objectID][u'username/bar'].value
            self.assertEqual(42, tagValue)

    def testGetValuesForQueryWithUnknownTagInQuery(self):
        """
        L{FacadeTagValueMixin.getValuesForQuery} raises a L{TNonexistentTag}
        exception if any of the requested L{Tag.path}s in the L{Query} don't
        exist.
        """
        SecureTagValueAPI(self.user).set({uuid4(): {u'username/tag': 12}})
        runDataImportHandler(self.client.url)
        self.store.commit()

        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.getValuesForQuery(
                session, u'username/unknown = 42 or username/tag = 12',
                [u'username/tag'])
            return self.assertFailure(deferred, TNonexistentTag)

    @inlineCallbacks
    def testGetValuesForQueryWithUnknownTagInReturnTags(self):
        """
        L{FacadeTagValueMixin.getValuesForQuery} ignores L{Tag.path}s that
        have been requested, if they don't exist.  If none of the requested
        L{Tag.path}s exist an empty result is returned.
        """
        SecureTagValueAPI(self.user).set({uuid4(): {u'username/tag': 12}})
        runDataImportHandler(self.client.url)
        self.store.commit()

        with login(u'username', uuid4(), self.transact) as session:
            result = yield self.facade.getValuesForQuery(
                session, u'username/tag = 12', [u'username/unknown'])
            self.assertEquals({u'results': {u'id': {}}}, loads(result))

    @inlineCallbacks
    def testGetValuesForQueryWithPartialUnknownTagInReturnTags(self):
        """
        L{FacadeTagValueMixin.getValuesForQuery} ignores L{Tag.path}s that
        have been requested, if they don't exist.  L{Tag.path}s that exist and
        have values matched by the query are returned.
        """
        objectID = uuid4()
        SecureTagValueAPI(self.user).set({objectID: {u'username/tag': 12}})
        runDataImportHandler(self.client.url)
        self.store.commit()

        with login(u'username', uuid4(), self.transact) as session:
            result = yield self.facade.getValuesForQuery(
                session, u'username/tag = 12',
                [u'username/unknown', u'username/tag'])
            result = loads(result)
            updatedAt = (result[u'results'][u'id'][str(objectID)]
                               [u'username/tag']['updated-at'])
            value = {str(objectID): {
                u'username/tag': {'value': 12,
                                  'updated-at': updatedAt,
                                  'username': u'username'}}}
            expected = {u'results': {u'id': value}}
            self.assertEquals(expected, result)

    @inlineCallbacks
    def testGetValuesForQueryWithOnlyFluidDBIDTag(self):
        """
        L{FacadeTagValueMixin.getValuesForQuery} returns matching object IDs
        when the C{fluiddb/id} tag is requested.
        """
        SecureTagAPI(self.user).create([(u'username/tag', u'description')])
        objectID = uuid4()
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        values = {objectID: {u'username/tag': 12}}
        SecureTagValueAPI(self.user).set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            results = yield self.facade.getValuesForQuery(
                session, u'has username/tag', [u'fluiddb/id'])
            results = loads(results)
            updatedAt = (results[u'results'][u'id'][str(objectID)]
                                [u'fluiddb/id']['updated-at'])
            value = {str(objectID): {u'fluiddb/id': {'value': str(objectID),
                                                     'updated-at': updatedAt,
                                                     'username': u'fluiddb'}}}
            expected = {u'results': {u'id': value}}
            self.assertEquals(expected, results)

    @inlineCallbacks
    def testGetValuesForQueryWithFluidDBIDTag(self):
        """
        L{FacadeTagValueMixin.getValuesForQuery} returns matching object IDs
        when the C{fluiddb/id} tag is requested, in addition to other
        L{Tag.path}s.
        """
        SecureTagAPI(self.user).create([(u'username/tag', u'description')])
        objectID = uuid4()
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        values = {objectID: {u'username/tag': 12}}
        SecureTagValueAPI(self.user).set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            results = yield self.facade.getValuesForQuery(
                session, u'has username/tag', [u'fluiddb/id', u'username/tag'])
            results = loads(results)
            updatedAt1 = (results[u'results'][u'id'][str(objectID)]
                                 [u'fluiddb/id']['updated-at'])
            updatedAt2 = (results[u'results'][u'id'][str(objectID)]
                                 [u'username/tag']['updated-at'])
            value = {str(objectID): {
                u'fluiddb/id': {
                    'value': str(objectID),
                    'updated-at': updatedAt1,
                    'username': u'fluiddb'},
                u'username/tag': {
                    'value': 12,
                    'updated-at': updatedAt2,
                    'username': u'username'}}}
            expected = {u'results': {u'id': value}}
            self.assertEquals(expected, results)

    @inlineCallbacks
    def testGetValuesForQueryWithReadQueryPermissionDenied(self):
        """
        L{FacadeTagValueMixin.getValuesForQuery} raises a
        L{TNonexistentTag} exception if the user doesn't have
        C{Operation.READ_TAG_VALUE} permission on any of the L{Tag}s in the
        L{Query}.
        """
        UserAPI().create([(u'fred', u'password', u'Fred',
                           u'fred@example.com')])
        user = getUser(u'username')
        permissions = CachingPermissionAPI(user)
        TagAPI(user).create([(u'fred/bar', u'description')])
        values = [(u'fred/bar', Operation.READ_TAG_VALUE,
                   Policy.CLOSED, [u'fred'])]
        permissions.set(values)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.getValuesForQuery(
                session, u'fred/bar = 42', [u'fred/bar'])
            error = yield self.assertFailure(deferred, TNonexistentTag)
            self.assertEqual(u'fred/bar', error.path)

    @inlineCallbacks
    def testGetValuesForQueryWithReadReturnPermissionDenied(self):
        """
        L{FacadeTagValueMixin.getValuesForQuery} raises a
        L{TNonexistentTag} exception if the user doesn't have
        C{Operation.READ_TAG_VALUE} permission on any of the outgoing
        L{Tag}s.
        """
        UserAPI().create([(u'fred', u'password', u'Fred',
                           u'fred@example.com')])
        user = getUser(u'fred')
        permissions = CachingPermissionAPI(user)
        TagAPI(user).create([(u'fred/bar', u'description'),
                             (u'fred/foo', u'description')])
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        values = {uuid4(): {u'fred/bar': 42}}
        SecureTagValueAPI(user).set(values)
        runDataImportHandler(self.client.url)
        values = [(u'fred/foo', Operation.READ_TAG_VALUE,
                   Policy.CLOSED, [u'fred'])]
        permissions.set(values)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.getValuesForQuery(
                session, u'fred/bar = 42', [u'fred/foo'])
            error = yield self.assertFailure(deferred, TNonexistentTag)
            self.assertEqual(u'fred/foo', error.path)

    @inlineCallbacks
    def testGetValuesForQueryWithInvalidQuery(self):
        """
        L{FacadeTagValueMixin.getValuesForQuery} raises a
        L{TParseError} exception if the incoming L{Query} can't be parsed.
        """
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.getValuesForQuery(
                session, u'username/bar 42', [u'username/bar'])
            yield self.assertFailure(deferred, TParseError)

    @inlineCallbacks
    def testGetValuesForQueryWithIllegalQuery(self):
        """
        L{FacadeTagValueMixin.getValuesForQuery} raises a L{TBadRequest}
        exception if the incoming L{Query} contains an illegal expression.
        """
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.getValuesForQuery(
                session, u'has fluiddb/about', [u'username/bar'])
            yield self.assertFailure(deferred, TBadRequest)

    @inlineCallbacks
    def testGetValuesForQueryWithSearchError(self):
        """
        L{FacadeTagValueMixin.getValuesForQuery} raises L{TParseError} if the
        query is not well formed.
        """
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.getValuesForQuery(session, 'has fluiddb/id',
                                                     [u'username/bar'])
            yield self.assertFailure(deferred, TParseError)

    @inlineCallbacks
    def testGetValuesForQueryWithEmptyQueryResults(self):
        """
        L{FacadeTagValueMixin.getValuesForQuery} does not fail if a
        L{Query} results in an empty C{set}.
        """
        TagAPI(self.user).create([(u'username/bar', u'description')])
        tag = getTags(paths=[u'username/bar']).one()
        objectID = uuid4()
        createTagValue(self.user.id, tag.id, objectID, 42)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            results = yield self.facade.getValuesForQuery(
                session, u'username/bar = 2600', [u'username/bar'])
            expected = {u'results': {u'id': {}}}
            self.assertEquals(expected, loads(results))

    @inlineCallbacks
    def testGetValuesForQuery(self):
        """
        L{FacadeTagValueMixin.getValuesForQuery} returns the L{TagValue}
        of an object if the L{Query} matches and the L{User} has permissions.
        """
        SecureTagAPI(self.user).create([(u'username/bar', u'description')])
        objectID = uuid4()
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        values = {objectID: {u'username/bar': 42}}
        SecureTagValueAPI(self.user).set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            results = yield self.facade.getValuesForQuery(
                session, u'username/bar = 42', [u'username/bar'])
            results = loads(results)
            updatedAt = (results[u'results'][u'id'][str(objectID)]
                                [u'username/bar']['updated-at'])
            expected = {
                u'results': {
                    u'id': {
                        str(objectID): {
                            u'username/bar': {
                                u'value': 42,
                                u'updated-at': updatedAt,
                                u'username': 'username'}}}}}
            self.assertEqual(expected, results)

    @inlineCallbacks
    def testGetValuesForQueryWithoutReturnTags(self):
        """
        L{FacadeTagValueMixin.getValuesForQuery} returns all available
        L{TagValue}s for the objects the L{Query} matches and that the L{User}
        has L{Operation.READ_TAG_VALUE} permission for.
        """
        SecureTagAPI(self.user).create([(u'username/bar', u'description')])
        objectID = uuid4()
        # FIXME replace this with SecureTagValueAPI once the index is
        # integrated
        values = {objectID: {u'username/bar': 42}}
        SecureTagValueAPI(self.user).set(values)
        runDataImportHandler(self.client.url)
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            results = yield self.facade.getValuesForQuery(session,
                                                          u'username/bar = 42')
            results = loads(results)
            updatedAt = (results[u'results'][u'id'][str(objectID)]
                                [u'username/bar']['updated-at'])
            expected = {
                u'results': {
                    u'id': {
                        str(objectID): {
                            u'username/bar': {
                                u'value': 42,
                                u'updated-at': updatedAt,
                                u'username': 'username'}}}}}
            self.assertEqual(expected, results)

    @inlineCallbacks
    def testGetValuesForQueryWithBinaryValue(self):
        """
        L{FacadeTagValueMixin.getValuesForQuery} returns only the MIME type
        and the size of binary L{TagValue}s, but not their contents.
        """
        SecureTagAPI(self.user).create([(u'username/tag1', u'description'),
                                        (u'username/tag2', u'description')])
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            objectID = uuid4()
            thriftValue = createBinaryThriftValue('Hello, world!',
                                                  'text/plain')
            yield self.facade.setTagInstance(session, u'username/tag1',
                                             str(objectID), thriftValue)
            thriftValue = createThriftValue(42)
            yield self.facade.setTagInstance(session, u'username/tag2',
                                             str(objectID), thriftValue)
            runDataImportHandler(self.client.url)

            results = yield self.facade.getValuesForQuery(
                session, u'username/tag2 = 42', [u'username/tag1'])
            results = loads(results)
            updatedAt = (results[u'results'][u'id'][str(objectID)]
                                [u'username/tag1']['updated-at'])
            expected = {
                u'results': {
                    u'id': {
                        str(objectID): {
                            u'username/tag1': {
                                u'value-type': u'text/plain',
                                u'size': 13,
                                u'updated-at': updatedAt,
                                u'username': u'username'}}}}}
            self.assertEquals(expected, results)
