from uuid import uuid4, UUID

from twisted.internet.defer import inlineCallbacks

from fluiddb.api.authentication import AuthenticatedSession
from fluiddb.api.facade import Facade
from fluiddb.application import FluidinfoSessionFactory
from fluiddb.common.types_thrift.ttypes import TUnauthorized
from fluiddb.cache.permission import CachingPermissionAPI
from fluiddb.data.permission import Operation, Policy, createTagPermission
from fluiddb.data.system import createSystemData
from fluiddb.data.tag import createTag
from fluiddb.data.value import (
    createTagValue, createAboutTagValue, getAboutTagValues, getTagValues)
from fluiddb.model.user import UserAPI, getUser
from fluiddb.security.tag import SecureTagAPI
from fluiddb.security.value import SecureTagValueAPI
from fluiddb.testing.resources import (
    CacheResource, ConfigResource, DatabaseResource, LoggingResource,
    ThreadPoolResource)
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.session import login
from fluiddb.util.transact import Transact


class FacadeObjectMixinTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(FacadeObjectMixinTest, self).setUp()
        self.system = createSystemData()
        self.transact = Transact(self.threadPool)
        factory = FluidinfoSessionFactory('API-9000')
        self.facade = Facade(self.transact, factory)
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = CachingPermissionAPI(self.user)

    @inlineCallbacks
    def testCreateObjectPermissionDenied(self):
        """
        L{FacadeObjectMixin.createObject} raises a
        L{TUnauthorized} exception if the user is the anonymous user.
        """
        self.store.commit()

        with login(u'anon', uuid4(), self.transact) as session:
            deferred = self.facade.createObject(session)
            yield self.assertFailure(deferred, TUnauthorized)

    @inlineCallbacks
    def testCreateObjectWithoutAboutValue(self):
        """
        L{FacadeObjectAPI.createObject} always returns a valid C{UUID} in a
        C{str} for a new object ID if an about value is not given.
        """
        self.store.commit()

        with login(u'username', uuid4(), self.transact) as session:
            objectID = yield self.facade.createObject(session)
            self.assertEqual(objectID, str(UUID(objectID)))

    @inlineCallbacks
    def testCreateObjectWithAboutValue(self):
        """
        L{FacadeObjectAPI.createObject} always returns a valid C{UUID} in a
        C{str} for a new object ID if an about value is given and it doesn't
        already exist.
        """
        self.store.commit()

        with login(self.user.username, uuid4(), self.transact) as session:
            objectID = yield self.facade.createObject(session, about='foo')
            objectID = UUID(objectID)

        self.store.rollback()
        value = getAboutTagValues([objectID], [u'foo']).one()
        self.assertEqual(u'foo', value.value)

        tag = self.system.tags[u'fluiddb/about']
        value = getTagValues(values=[(objectID, tag.id)]).one()
        self.assertIdentical(self.system.users[u'fluiddb'], value.creator)

    @inlineCallbacks
    def testCreateObjectWithDuplicateAboutValue(self):
        """
        L{FacadeObjectAPI.createObject} returns a valid C{UUID} in a C{str} for
        an existing object ID if an about value is given and already exists in
        the database.
        """
        objectID = uuid4()
        createAboutTagValue(objectID, u'bar')
        values = {objectID: {u'fluiddb/about': u'bar'}}
        SecureTagValueAPI(self.system.superuser).set(values)
        self.store.commit()

        with login(self.user.username, uuid4(), self.transact) as session:
            resultObjectID = yield self.facade.createObject(session,
                                                            about='bar')
            self.assertEqual(str(objectID), resultObjectID)

    @inlineCallbacks
    def testGetObject(self):
        """
        L{FacadeObjectAPI.getObject} returns a L{TObjectInfo} with the
        L{Tag.path}s for which the L{User} has L{Operation.READ_TAG_VALUE}.
        """
        objectID = uuid4()
        SecureTagAPI(self.user).create([(u'username/foo', u'A description')])
        values = {objectID: {u'username/foo': u'bar'}}
        SecureTagValueAPI(self.user).set(values)
        self.store.commit()

        with login(self.user.username, uuid4(), self.transact) as session:
            objectInfo = yield self.facade.getObject(session, str(objectID))
            self.assertEqual([u'username/foo'], objectInfo.tagPaths)
            self.assertEqual(None, objectInfo.about)

    @inlineCallbacks
    def testGetObjectWithAboutValue(self):
        """
        L{FacadeObjectAPI.getObject} returns a L{TObjectInfo} with the
        L{Tag.path}s for which the L{User} has L{Operation.READ_TAG_VALUE},
        and the L{AboutTagValue.value} if it has one and C{showAbout} is
        C{True}.
        """
        objectID = uuid4()
        SecureTagAPI(self.user).create([(u'username/foo', u'A description')])
        values = {objectID: {u'username/foo': u'bar'}}
        SecureTagValueAPI(self.user).set(values)
        aboutTag = self.system.tags[u'fluiddb/about']
        createAboutTagValue(objectID, u'bar')
        createTagValue(self.user.id, aboutTag.id, objectID, u'about value')
        self.store.commit()

        with login(self.user.username, uuid4(), self.transact) as session:
            objectInfo = yield self.facade.getObject(session, str(objectID),
                                                     showAbout=True)
            self.assertEqual([u'fluiddb/about', u'username/foo'],
                             sorted(objectInfo.tagPaths))
            self.assertEqual('about value', objectInfo.about)

    @inlineCallbacks
    def testGetObjectWithAboutValueDoesNotExist(self):
        """
        L{FacadeObjectAPI.getObject} returns a L{TObjectInfo} with the
        L{Tag.path}s for which the L{User} has L{Operation.READ_TAG_VALUE},
        and the L{AboutTagValue.value} if it has one and C{showAbout} is
        C{True}.
        """
        objectID = uuid4()
        tag = createTag(self.user, self.user.namespace, u'foo')
        createTagPermission(tag)
        createTagValue(self.user.id, tag.id, objectID, u'bar')
        session = AuthenticatedSession(self.user.username, uuid4())
        self.store.commit()
        with login(self.user.username, uuid4(), self.transact) as session:
            objectInfo = yield self.facade.getObject(session, str(objectID),
                                                     showAbout=True)
            self.assertEqual([u'username/foo'], objectInfo.tagPaths)
            self.assertIdentical(None, objectInfo.about)

    @inlineCallbacks
    def testGetObjectDeniedPaths(self):
        """
        L{FacadeObjectAPI.getObject} returns a L{TObjectInfo} with the
        L{Tag.path}s for which the L{User} has L{Operation.READ_TAG_VALUE}.
        """
        SecureTagAPI(self.user).create([(u'username/tag1', u'description'),
                                        (u'username/tag2', u'description')])
        objectID = uuid4()
        values = {objectID: {u'username/tag1': 16},
                  objectID: {u'username/tag2': 16}}
        SecureTagValueAPI(self.user).set(values)
        self.permissions.set([(u'username/tag1', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, []),
                              (u'username/tag2', Operation.READ_TAG_VALUE,
                               Policy.OPEN, [])])
        self.store.commit()

        with login(self.user.username, uuid4(), self.transact) as session:
            objectInfo = yield self.facade.getObject(session, str(objectID))
            self.assertEqual([u'username/tag2'], objectInfo.tagPaths)
            self.assertEqual(None, objectInfo.about)

    @inlineCallbacks
    def testGetObjectAllPathsAreDenied(self):
        """
        L{FacadeObjectAPI.getObject} returns a L{TObjectInfo} with the
        L{Tag.path}s for which the L{User} has L{Operation.READ_TAG_VALUE}, if
        all of them are denied, L{FacadeObjectAPI.getObject} must return an
        empty L{TObjectInfo}.
        """
        SecureTagAPI(self.user).create([(u'username/tag1', u'description'),
                                        (u'username/tag2', u'description')])
        objectID = uuid4()
        values = {objectID: {u'username/tag1': 16},
                  objectID: {u'username/tag2': 16}}
        SecureTagValueAPI(self.user).set(values)
        self.permissions.set([(u'username/tag1', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, []),
                              (u'username/tag2', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, [])])
        self.store.commit()

        with login(self.user.username, uuid4(), self.transact) as session:
            objectInfo = yield self.facade.getObject(session, str(objectID))
            self.assertEqual([], objectInfo.tagPaths)
            self.assertEqual(None, objectInfo.about)
