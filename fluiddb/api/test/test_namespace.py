from uuid import UUID

from twisted.internet.defer import inlineCallbacks

from fluiddb.api.facade import Facade
from fluiddb.application import FluidinfoSessionFactory
from fluiddb.common.types_thrift.ttypes import (
    TNonexistentNamespace, TNamespaceAlreadyExists, TNamespaceNotEmpty,
    TPathPermissionDenied, TInvalidPath)
from fluiddb.data.namespace import getNamespaces, createNamespace
from fluiddb.data.permission import Operation, Policy
from fluiddb.data.system import createSystemData
from fluiddb.data.tag import createTag
from fluiddb.model.user import getUser
from fluiddb.model.namespace import NamespaceAPI
from fluiddb.model.permission import PermissionAPI
from fluiddb.model.user import UserAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    CacheResource, ConfigResource, DatabaseResource, LoggingResource,
    ThreadPoolResource)
from fluiddb.testing.session import login
from fluiddb.util.transact import Transact


class FacadeNamespaceTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(FacadeNamespaceTest, self).setUp()
        createSystemData()
        self.transact = Transact(self.threadPool)
        factory = FluidinfoSessionFactory('API-9000')
        self.facade = Facade(self.transact, factory)
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = PermissionAPI(self.user)

    @inlineCallbacks
    def testGetNamespaceWithoutData(self):
        """
        L{Facade.getNamespace} raises a L{TNonexistentNamespace} exception if
        the requested L{Namespace.path} doesn't exist.
        """
        self.store.commit()

        with login(u'username', self.user.objectID, self.transact) as session:
            deferred = self.facade.getNamespace(session, u'username/unknown',
                                                False, False, False)
            yield self.assertFailure(deferred, TNonexistentNamespace)

    @inlineCallbacks
    def testGetNamespace(self):
        """
        L{Facade.getNamespace} returns a L{TNamespace} instance with
        information about the requested L{Namespace}.
        """
        self.store.commit()

        with login(u'username', self.user.objectID, self.transact) as session:
            result = yield self.facade.getNamespace(session, u'username',
                                                    False, False, False)

        self.assertEqual(str(self.user.namespace.objectID), result.objectId)
        self.assertEqual(u'username', result.path)

    @inlineCallbacks
    def testGetNamespaceWithDescription(self):
        """
        L{Facade.getNamespace} includes the L{Namespace.description}, if it
        was requested.
        """
        namespaces = NamespaceAPI(self.user)
        namespaces.create([(u'username/name', u'A namespace.')])
        self.store.commit()

        with login(u'username', self.user.objectID, self.transact) as session:
            result = yield self.facade.getNamespace(session, u'username/name',
                                                    True, False, False)
        self.assertEqual(u'A namespace.', result.description)

    @inlineCallbacks
    def testGetNamespaceWithNamespaces(self):
        """
        L{Facade.getNamespace} includes child L{Namespace.name}s, if they were
        requested.
        """
        namespaces = NamespaceAPI(self.user)
        namespaces.create([(u'username/name', u'A namespace.')])
        self.store.commit()

        with login(u'username', self.user.objectID, self.transact) as session:
            result = yield self.facade.getNamespace(session, u'username',
                                                    False, True, False)
        self.assertEqual([u'name', u'private'], sorted(result.namespaces))

    @inlineCallbacks
    def testGetNamespaceWithTags(self):
        """
        L{Facade.getNamespace} includes child L{Tag.name}s, if they were
        requested.
        """
        createTag(self.user, self.user.namespace, u'tag')
        self.store.commit()

        with login(u'username', self.user.objectID, self.transact) as session:
            result = yield self.facade.getNamespace(session, u'username',
                                                    False, False, True)
        self.assertEqual([u'tag'], result.tags)

    @inlineCallbacks
    def testGetNamespaceWithUnknownPath(self):
        """
        L{Facade.getNamespace} raises a L{TNonexistentNamespace} exception
        if the specified L{Namespace} doesn't exist.
        """
        with login(u'username', self.user.objectID, self.transact) as session:
            deferred = self.facade.getNamespace(session, u'unknown',
                                                returnDescription=False,
                                                returnNamespaces=False,
                                                returnTags=False)
            yield self.assertFailure(deferred, TNonexistentNamespace)

    @inlineCallbacks
    def testGetNamespaceWithPermissionDenied(self):
        """
        L{Facade.getNamespace} raises a L{TPathPermissionDenied} exception
        if the user doesn't have C{LIST} permissions on the specified
        L{Namespace}.
        """
        self.permissions.set([(u'username', Operation.LIST_NAMESPACE,
                               Policy.CLOSED, [])])
        self.store.commit()

        with login(u'username', self.user.objectID, self.transact) as session:
            deferred = self.facade.getNamespace(session, u'username',
                                                returnDescription=True,
                                                returnNamespaces=True,
                                                returnTags=True)
            yield self.assertFailure(deferred, TPathPermissionDenied)

    @inlineCallbacks
    def testCreateNamespace(self):
        """L{Facade.createNamespace} creates a new L{Namespace}."""
        self.store.commit()

        with login(u'username', self.user.objectID, self.transact) as session:
            objectID = yield self.facade.createNamespace(
                session, u'username', u'name', u'A namespace.')

        self.store.rollback()
        self.assertNotIdentical(None, objectID)
        objectID = UUID(objectID)
        namespace = getNamespaces(objectIDs=[objectID]).one()
        self.assertIdentical(self.user, namespace.creator)
        self.assertEqual(u'username/name', namespace.path)
        self.assertEqual(u'name', namespace.name)
        self.assertEqual(objectID, namespace.objectID)

    @inlineCallbacks
    def testCreateNamespaceWithExistingPath(self):
        """
        L{Facade.createNamespace} raises a L{TNamespaceAlreadyExists}
        exception if the new L{Namespace} already exists.
        """
        createNamespace(self.user, u'username/name', self.user.namespace.id)
        self.store.commit()

        with login(u'username', self.user.objectID, self.transact) as session:
            deferred = self.facade.createNamespace(session, u'username',
                                                   u'name', u'A namespace.')
            yield self.assertFailure(deferred, TNamespaceAlreadyExists)

    @inlineCallbacks
    def testCreateNamespaceWithUnknownParent(self):
        """
        L{Facade.createNamespace} raises a L{TNonexistentNamespace} exception
        if a non-existent parent L{Namespace} is specified.
        """
        createNamespace(self.user, u'username/name', self.user.namespace.id)
        self.store.commit()

        with login(u'username', self.user.objectID, self.transact) as session:
            deferred = self.facade.createNamespace(session, u'unknown/parent',
                                                   u'name', u'A  namespace.')
            yield self.assertFailure(deferred, TNonexistentNamespace)

    @inlineCallbacks
    def testCreateNamespaceWithInvalidPath(self):
        """
        L{Facade.createNamespace} raises a L{TInvalidPath} exception
        if the path of the L{Namespace} is not well formed.
        """
        self.store.commit()

        with login(u'username', self.user.objectID, self.transact) as session:
            deferred = self.facade.createNamespace(session, u'username',
                                                   u'bad name', u'description')
            yield self.assertFailure(deferred, TInvalidPath)

    @inlineCallbacks
    def testCreateNamespaceImplicitlyCreatesParent(self):
        """
        L{Facade.createNamespace} implicitly creates parent L{Namespace}s if
        they don't exist.
        """
        self.store.commit()

        with login(u'username', self.user.objectID, self.transact) as session:
            objectID = yield self.facade.createNamespace(
                session, u'username/parent', u'name', u'A namespace.')
            namespace = yield self.facade.getNamespace(
                session, u'username/parent/name', returnDescription=False,
                returnNamespaces=False, returnTags=False)
            self.assertEqual(objectID, namespace.objectId)

    @inlineCallbacks
    def testCreateIsDenied(self):
        """
        L{Facade.createNamespace} raises a L{TPathPermissionDenied} exception
        if the user doesn't have C{CREATE} permissions on the parent
        L{Namespace}.
        """
        self.permissions.set([(u'username', Operation.CREATE_NAMESPACE,
                               Policy.CLOSED, [])])
        self.store.commit()

        with login(u'username', self.user.objectID, self.transact) as session:
            deferred = self.facade.createNamespace(session, u'username',
                                                   u'test', u'description')
            yield self.assertFailure(deferred, TPathPermissionDenied)

    @inlineCallbacks
    def testUpdateNamespace(self):
        """
        L{Facade.updateNamespace} updates the description for an existing
        L{Namespace}.
        """
        namespaces = NamespaceAPI(self.user)
        namespaces.create([(u'username/name', u'A namespace.')])
        self.store.commit()

        with login(u'username', self.user.objectID, self.transact) as session:
            yield self.facade.updateNamespace(session, u'username/name',
                                              u'A new description.')

        self.store.rollback()
        result = namespaces.get([u'username/name'], withDescriptions=True)
        self.assertEqual(u'A new description.',
                         result[u'username/name']['description'])

    @inlineCallbacks
    def testUpdateNamespaceWithUnknownPath(self):
        """
        L{Facade.updateNamespace} raises a L{TNonexistentNamespace} exception
        if the requested L{Namespace.path} doesn't exist.
        """
        self.store.commit()

        with login(u'username', self.user.objectID, self.transact) as session:
            deferred = self.facade.updateNamespace(
                session, u'username/unknown', u'A new description.')
            yield self.assertFailure(deferred, TNonexistentNamespace)

    @inlineCallbacks
    def testUpdateIsDenied(self):
        """
        L{Facade.updateNamespace} raises a L{TPathPermissionDenied} exception
        if the user doesn't have C{UPDATE} permissions on the specified
        L{Namespace}.
        """
        self.permissions.set([(u'username', Operation.UPDATE_NAMESPACE,
                               Policy.CLOSED, [])])
        self.store.commit()

        with login(u'username', self.user.objectID, self.transact) as session:
            deferred = self.facade.updateNamespace(session, u'username',
                                                   u'description')
            yield self.assertFailure(deferred, TPathPermissionDenied)

    @inlineCallbacks
    def testDeleteNamespace(self):
        """L{Facade.deleteNamespace} deletes a L{Namespace}."""
        namespaces = NamespaceAPI(self.user)
        namespaces.create([(u'username/name', u'A namespace.')])
        self.store.commit()

        with login(u'username', self.user.objectID, self.transact) as session:
            yield self.facade.deleteNamespace(session, u'username/name')

        self.store.rollback()
        self.assertEqual({}, namespaces.get([u'username/name']))

    @inlineCallbacks
    def testDeleteNamespaceWithUnknownPath(self):
        """
        L{Facade.deleteNamespace} raises a L{TNonexistentNamespace} exception
        if the requested L{Namespace.path} doesn't exist.
        """
        self.store.commit()

        with login(u'username', self.user.objectID, self.transact) as session:
            deferred = self.facade.deleteNamespace(session,
                                                   u'username/unknown')
            yield self.assertFailure(deferred, TNonexistentNamespace)

    @inlineCallbacks
    def testDeleteNamespaceWithData(self):
        """
        L{Facade.deleteNamespace} raises a L{TNamespaceNotEmpty} exception if
        the requested L{Namespace} has child data such as other L{Namespace}s
        or L{Tag}s.
        """
        namespaces = NamespaceAPI(self.user)
        namespaces.create([(u'username/parent', u'A parent namespace.')])
        namespaces.create([(u'username/parent/child', u'A child namespace.')])
        self.store.commit()

        with login(u'username', self.user.objectID, self.transact) as session:
            deferred = self.facade.deleteNamespace(session, u'username/parent')
            yield self.assertFailure(deferred, TNamespaceNotEmpty)

    @inlineCallbacks
    def testDeleteIsDenied(self):
        """
        L{Facade.deleteNamespace} raises a L{TPathPermissionDenied} exception
        if the user doesn't have C{DELETE} permissions on the specified
        L{Namespace}.
        """
        namespaces = NamespaceAPI(self.user)
        namespaces.create([(u'username/test', u'description')])
        self.permissions.set([(u'username/test', Operation.DELETE_NAMESPACE,
                               Policy.OPEN, [u'username'])])
        self.store.commit()

        with login(u'username', self.user.objectID, self.transact) as session:
            deferred = self.facade.deleteNamespace(session, u'username/test')
            yield self.assertFailure(deferred, TPathPermissionDenied)
