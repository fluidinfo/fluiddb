from uuid import uuid4

from twisted.internet.defer import inlineCallbacks

from fluiddb.api.facade import Facade
from fluiddb.application import FluidinfoSessionFactory
from fluiddb.cache.permission import CachingPermissionAPI
from fluiddb.common.types_thrift.ttypes import (
    TNonexistentTag, TTagAlreadyExists, TPathPermissionDenied, TInvalidPath)
from fluiddb.data.permission import Operation, Policy
from fluiddb.data.system import createSystemData
from fluiddb.data.tag import getTags
from fluiddb.model.tag import TagAPI
from fluiddb.model.user import UserAPI, getUser
from fluiddb.model.value import TagValueAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    CacheResource, ConfigResource, DatabaseResource, LoggingResource,
    ThreadPoolResource)
from fluiddb.testing.session import login
from fluiddb.util.transact import Transact


class FacadeTagMixinTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(FacadeTagMixinTest, self).setUp()
        createSystemData()
        self.transact = Transact(self.threadPool)
        factory = FluidinfoSessionFactory('API-9000')
        self.facade = Facade(self.transact, factory)
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = CachingPermissionAPI(self.user)

    @inlineCallbacks
    def testGetTagWithoutData(self):
        """
        L{FacadeTagMixin.getTag} raises a L{TNonexistentTag} exception if the
        requested L{Tag.path} doesn't exist.
        """
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.getTag(session, u'username/unknown', False)
            yield self.assertFailure(deferred, TNonexistentTag)

    @inlineCallbacks
    def testGetTag(self):
        """
        L{FacadeTagMixin.getTag} returns a L{TTag} instance with information
        about the requested L{Tag}.
        """
        result = TagAPI(self.user).create([(u'username/tag', u'description')])
        [(objectID, path)] = result
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            result = yield self.facade.getTag(session, u'username/tag', False)
            self.assertEqual(str(objectID), result.objectId)
            self.assertEqual(u'username/tag', result.path)
            self.assertTrue(result.indexed)

    @inlineCallbacks
    def testGetTagWithDescription(self):
        """
        L{FacadeTagMixin.getTag} includes the L{Tag.description}, if it was
        requested.
        """
        TagAPI(self.user).create([(u'username/tag', u'A tag.')])
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            result = yield self.facade.getTag(session, u'username/tag', True)
            self.assertEqual(u'A tag.', result.description)

    @inlineCallbacks
    def testCreateTag(self):
        """L{FacadeTagMixin.createTag} creates a new L{Tag}."""
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            objectID = yield self.facade.createTag(
                session, u'username', u'tag', u'A tag.', 'ignored', 'ignored')
            self.assertNotIdentical(None, objectID)

        self.store.rollback()
        tag = getTags(paths=[u'username/tag']).one()
        self.assertIdentical(self.user, tag.creator)
        self.assertIdentical(self.user.namespace, tag.namespace)
        self.assertEqual(u'username/tag', tag.path)
        self.assertEqual(u'tag', tag.name)
        self.assertEqual(objectID, str(tag.objectID))

    @inlineCallbacks
    def testCreateTagWithExistingPath(self):
        """
        L{FacadeTagMixin.createTag} raises a L{TTagAlreadyExists} exception if
        the new L{Tag} already exists.
        """
        TagAPI(self.user).create([(u'username/name', u'A tag.')])
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.createTag(
                session, u'username', u'name', u'A tag.', 'ignored', 'ignored')
            yield self.assertFailure(deferred, TTagAlreadyExists)

    @inlineCallbacks
    def testCreateTagWithInvalidPath(self):
        """
        L{FacadeTagMixin.createTag} raises a L{TInvalidPath} exception if the
        path of the L{Tag} is not well formed.
        """
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.createTag(session, u'username', u'bad name',
                                             u'A tag.', 'ignored', 'ignored')
            yield self.assertFailure(deferred, TInvalidPath)

    @inlineCallbacks
    def testCreateTagWithUnknownParent(self):
        """
        L{FacadeTagMixin.createTag} raises a L{TNonexistentTag} exception if a
        non-existent parent L{Tag} is specified.
        """
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.createTag(
                session, u'unknown', u'name', u'A tag.', 'ignored', 'ignored')
            yield self.assertFailure(deferred, TNonexistentTag)

    @inlineCallbacks
    def testCreateIsDenied(self):
        """
        L{Facade.createTag} raises a L{TPathPermissionDenied} exception if the
        user doesn't have C{CREATE} permissions on the parent L{Namespace}.
        """
        self.permissions.set([(u'username', Operation.CREATE_NAMESPACE,
                               Policy.CLOSED, [])])
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.createTag(
                session, u'username', u'test', u'A tag.', 'ignored', 'ignored')
            yield self.assertFailure(deferred, TPathPermissionDenied)

    @inlineCallbacks
    def testUpdateTag(self):
        """
        L{FacadeTagMixin.updateTag} updates the description for an existing
        L{Tag}.
        """
        tags = TagAPI(self.user)
        tags.create([(u'username/name', u'A tag.')])
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            yield self.facade.updateTag(session, u'username/name',
                                        u'A new description.')

        self.store.rollback()
        result = tags.get([u'username/name'], withDescriptions=True)
        self.assertEqual(u'A new description.',
                         result[u'username/name']['description'])

    @inlineCallbacks
    def testUpdateTagWithUnknownPath(self):
        """
        L{FacadeTagMixin.updateTag} raises a L{TNonexistentTag} exception if
        the requested L{Tag.path} doesn't exist.
        """
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.updateTag(session, u'username/unknown',
                                             u'A new description.')
            yield self.assertFailure(deferred, TNonexistentTag)

    @inlineCallbacks
    def testUpdateIsDenied(self):
        """
        L{Facade.updateTag} raises a L{TPathPermissionDenied} exception if the
        user doesn't have C{UPDATE} permissions on the specified L{Tag}.
        """
        TagAPI(self.user).create([(u'username/test', u'A tag.')])
        self.permissions.set([(u'username/test', Operation.UPDATE_TAG,
                               Policy.CLOSED, [])])
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.updateTag(session, u'username/test',
                                             u'A new description.')
            yield self.assertFailure(deferred, TPathPermissionDenied)

    @inlineCallbacks
    def testDeleteTag(self):
        """L{FacadeTagMixin.deleteTag} deletes a L{Tag}."""
        tags = TagAPI(self.user)
        tags.create([(u'username/name', u'A tag.')])
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            yield self.facade.deleteTag(session, u'username/name')

        self.store.rollback()
        self.assertEqual({}, tags.get([u'username/name']))

    @inlineCallbacks
    def testDeleteTagWithUnknownPath(self):
        """
        L{FacadeTagMixin.deleteTag} raises a L{TNonexistentTag} exception if
        the requested L{Tag.path} doesn't exist.
        """
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.deleteTag(session, u'username/unknown')
            yield self.assertFailure(deferred, TNonexistentTag)

    @inlineCallbacks
    def testDeleteTagWithData(self):
        """
        L{FacadeTagMixin.deleteTag} removes L{TagValue}s associated with the
        deleted L{Tag}.
        """
        objectID = uuid4()
        TagAPI(self.user).create([(u'username/tag', u'A tag.')])
        tagValues = TagValueAPI(self.user)
        tagValues.set({objectID: {u'username/tag': 42}})
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            yield self.facade.deleteTag(session, u'username/tag')

        self.store.rollback()
        self.assertEqual({}, tagValues.get(objectIDs=[objectID],
                                           paths=[u'username/tag']))

    @inlineCallbacks
    def testDeleteIsDenied(self):
        """
        L{Facade.deleteTag} raises a L{TPathPermissionDenied} exception if the
        user doesn't have C{DELETE} permissions on the specified L{Tag}.
        """
        TagAPI(self.user).create([(u'username/test', u'A tag.')])
        self.permissions.set([(u'username/test', Operation.DELETE_TAG,
                               Policy.OPEN, [u'username'])])
        self.store.commit()
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.deleteTag(session, u'username/test')
            yield self.assertFailure(deferred, TPathPermissionDenied)
