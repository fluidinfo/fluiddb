from uuid import uuid4

from twisted.internet.defer import inlineCallbacks

from fluiddb.api.facade import Facade
from fluiddb.application import FluidinfoSessionFactory
from fluiddb.cache.permission import CachingPermissionAPI
from fluiddb.common.types_thrift.ttypes import (
    TBadRequest, TNonexistentNamespace, TNonexistentTag, TPathPermissionDenied,
    TPolicyAndExceptions, TInvalidPolicy, TNoSuchUser, TInvalidUsername)
from fluiddb.data.permission import Operation, Policy
from fluiddb.data.system import createSystemData
from fluiddb.model.user import UserAPI, getUser
from fluiddb.security.tag import SecureTagAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.doubles import FakeThreadPool
from fluiddb.testing.resources import (
    CacheResource, ConfigResource, DatabaseResource, LoggingResource)
from fluiddb.testing.session import login
from fluiddb.util.transact import Transact


class FacadePermissionTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(FacadePermissionTest, self).setUp()
        self.transact = Transact(FakeThreadPool())
        factory = FluidinfoSessionFactory('API-9000')
        self.facade = Facade(self.transact, factory)
        createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        user = getUser(u'username')
        self.permissions = CachingPermissionAPI(user)
        SecureTagAPI(user).create([(u'username/tag', u'description')])

    @inlineCallbacks
    def testGetNamespacePermissions(self):
        """
        L{FacadePermissionMixin.getPermission} returns a
        L{TPolicyAndExceptions} object with the policy and exceptions list for
        a given L{Namespace} path.
        """
        self.permissions.set([(u'username', Operation.CREATE_NAMESPACE,
                               Policy.CLOSED, [])])
        with login(u'username', uuid4(), self.transact) as session:
            policyAndExceptions = yield self.facade.getPermission(
                session, u'namespaces', u'create', u'username')
        self.assertEqual(u'closed', policyAndExceptions.policy)
        self.assertEqual([], policyAndExceptions.exceptions)

    @inlineCallbacks
    def testGetTagPermissions(self):
        """
        L{FacadePermissionMixin.getPermission} returns a
        L{TPolicyAndExceptions} object with the policy and exceptions list for
        a given L{Tag} path.
        """
        self.permissions.set([(u'username/tag', Operation.UPDATE_TAG,
                               Policy.CLOSED, [u'username'])])
        with login(u'username', uuid4(), self.transact) as session:
            policyAndExceptions = yield self.facade.getPermission(
                session, u'tags', u'update', u'username/tag')
        self.assertEqual(u'closed', policyAndExceptions.policy)
        self.assertEqual([u'username'], policyAndExceptions.exceptions)

    @inlineCallbacks
    def testGetTagValuePermissions(self):
        """
        L{FacadePermissionMixin.getPermission} returns a
        L{TPolicyAndExceptions} object with the policy and exceptions list for
        a given L{TagValue} path.
        """
        self.permissions.set([(u'username/tag', Operation.WRITE_TAG_VALUE,
                               Policy.CLOSED, [])])
        with login(u'username', uuid4(), self.transact) as session:
            policyAndExceptions = yield self.facade.getPermission(
                session, u'tag-values', u'write', u'username/tag')
        self.assertEqual(u'closed', policyAndExceptions.policy)
        self.assertEqual([], policyAndExceptions.exceptions)

    @inlineCallbacks
    def testGetWithInvalidAction(self):
        """
        L{FacadePermissionMixin.getPermission} raises a L{TBadRequest} error if
        the given C{action} is invalid.
        """
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.getPermission(session, u'namespaces',
                                                 u'invalid', u'username')
            yield self.assertFailure(deferred, TBadRequest)

    @inlineCallbacks
    def testGetWithInvalidCategory(self):
        """
        L{FacadePermissionMixin.getPermission} raises a L{TBadRequest} error if
        the given C{category} is invalid.
        """
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.getPermission(session, u'invalid',
                                                 u'create', u'username')
            yield self.assertFailure(deferred, TBadRequest)

    @inlineCallbacks
    def testGetWithUnknownNamespace(self):
        """
        L{FacadePermissionMixin.getPermission} raises a
        L{TNonexistentNamespace} error if the given L{Namespace} path does not
        exist.
        """
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.getPermission(session, u'namespaces',
                                                 u'create', u'unknown')
            yield self.assertFailure(deferred, TNonexistentNamespace)

    @inlineCallbacks
    def testGetWithUnknownTag(self):
        """
        L{FacadePermissionMixin.getPermission} raises a L{TNonexistentTag}
        error if the given L{Tag} path does not exist.
        """
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.getPermission(
                session, u'tags', u'update', u'username/unknown')
            yield self.assertFailure(deferred, TNonexistentTag)

    @inlineCallbacks
    def testGetNamespacePermissionsIsDenied(self):
        """
        L{FacadePermissionMixin.getPermission} raises a
        L{TPathPermissionDenied} error if the user doesn't have
        C{Operation.CONTROL_NAMESPACE} permissions on the given L{Namespace}.
        """
        self.permissions.set([(u'username', Operation.CONTROL_NAMESPACE,
                               Policy.CLOSED, [])])
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.getPermission(session, u'namespaces',
                                                 u'update', u'username')
            yield self.assertFailure(deferred, TPathPermissionDenied)

    @inlineCallbacks
    def testGetTagPermissionsIsDenied(self):
        """
        L{FacadePermissionMixin.getPermission} raises a
        L{TPathPermissionDenied} error if the user doesn't have
        C{Operation.CONTROL_TAG} permissions on the given L{Tag}.
        """
        self.permissions.set([(u'username/tag', Operation.CONTROL_TAG,
                               Policy.CLOSED, [])])
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.getPermission(session, u'tags',
                                                 u'delete', u'username/tag')
            yield self.assertFailure(deferred, TPathPermissionDenied)

    @inlineCallbacks
    def testGetTagValuePermissionsIsDenied(self):
        """
        L{FacadePermissionMixin.getPermission} raises a
        L{TPathPermissionDenied} error if the user doesn't have
        C{Operation.CONTROL_TAG_VALUE} permissions on the given L{Tag}.
        """
        self.permissions.set([(u'username/tag', Operation.CONTROL_TAG_VALUE,
                               Policy.CLOSED, [])])
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.getPermission(session, u'tag-values',
                                                 u'read', u'username/tag')
            yield self.assertFailure(deferred, TPathPermissionDenied)

    @inlineCallbacks
    def testSetNamespacePermissions(self):
        """
        L{FacadePermissionMixin.updatePermission} updates the permissions for a
        given L{Namespace} path.
        """
        policyAndExceptions = TPolicyAndExceptions(u'closed', [])
        with login(u'username', uuid4(), self.transact) as session:
            yield self.facade.updatePermission(session, u'namespaces',
                                               u'create', u'username',
                                               policyAndExceptions)
        pathAndAction = (u'username', Operation.CREATE_NAMESPACE)
        result = self.permissions.get([pathAndAction])
        self.assertEqual((Policy.CLOSED, []), result[pathAndAction])

    @inlineCallbacks
    def testSetTagPermissions(self):
        """
        L{FacadePermissionMixin.updatePermission} updates the permissions for a
        given L{Tag} path.
        """
        policyAndExceptions = TPolicyAndExceptions(u'open', [u'username'])
        with login(u'username', uuid4(), self.transact) as session:
            yield self.facade.updatePermission(session, u'tags', u'update',
                                               u'username/tag',
                                               policyAndExceptions)
        pathAndAction = (u'username/tag', Operation.UPDATE_TAG)
        result = self.permissions.get([pathAndAction])
        self.assertEqual((Policy.OPEN, [u'username']), result[pathAndAction])

    @inlineCallbacks
    def testSetTagValuePermissions(self):
        """
        L{FacadePermissionMixin.updatePermission} updates the permissions for a
        given L{TagValue} path.
        """
        policyAndExceptions = TPolicyAndExceptions(u'closed', [u'username'])
        with login(u'username', uuid4(), self.transact) as session:
            yield self.facade.updatePermission(session, u'tag-values',
                                               u'write', u'username/tag',
                                               policyAndExceptions)
        pathAndAction = (u'username/tag', Operation.WRITE_TAG_VALUE)
        result = self.permissions.get([pathAndAction])
        self.assertEqual((Policy.CLOSED, [u'username']), result[pathAndAction])

    @inlineCallbacks
    def testSetWithInvalidAction(self):
        """
        L{FacadePermissionMixin.updatePermission} raises a L{TBadRequest} error
        if the given C{action} is invalid.
        """
        policyAndExceptions = TPolicyAndExceptions(u'closed', [])
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.updatePermission(session, u'namespaces',
                                                    u'invalid', u'username',
                                                    policyAndExceptions)
            yield self.assertFailure(deferred, TBadRequest)

    @inlineCallbacks
    def testSetWithInvalidCategory(self):
        """
        L{FacadePermissionMixin.updatePermission} raises a L{TBadRequest} error
        if the given C{category} is invalid.
        """
        policyAndExceptions = TPolicyAndExceptions(u'closed', [])
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.updatePermission(session, u'invalid',
                                                    u'update', u'username',
                                                    policyAndExceptions)
            yield self.assertFailure(deferred, TBadRequest)

    @inlineCallbacks
    def testSetWithInvalidPolicy(self):
        """
        L{FacadePermissionMixin.updatePermission} raises a L{TInvalidPolicy}
        error if the given C{policy} is invalid.
        """
        policyAndExceptions = TPolicyAndExceptions(u'invalid', [])
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.updatePermission(session, u'namespaces',
                                                    u'create', u'username',
                                                    policyAndExceptions)
            yield self.assertFailure(deferred, TInvalidPolicy)

    @inlineCallbacks
    def testSetWithUnknownNamespace(self):
        """
        L{FacadePermissionMixin.updatePermission} raises a
        L{TNonexistentNamespace} error if the given L{Namespace} path does not
        exist.
        """
        policyAndExceptions = TPolicyAndExceptions(u'closed', [])
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.updatePermission(session, u'namespaces',
                                                    u'create', u'unknown',
                                                    policyAndExceptions)
            yield self.assertFailure(deferred, TNonexistentNamespace)

    @inlineCallbacks
    def testSetWithUnknownTag(self):
        """
        L{FacadePermissionMixin.updatePermission} raises a L{TNonexistentTag}
        error if the given L{Tag} path does not exist.
        """
        policyAndExceptions = TPolicyAndExceptions(u'closed', [])
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.updatePermission(
                session, u'tags', u'update', u'username/unknown',
                policyAndExceptions)
            yield self.assertFailure(deferred, TNonexistentTag)

    @inlineCallbacks
    def testSetWithUnknownUser(self):
        """
        L{FacadePermissionMixin.updatePermission} raises a L{TNoSuchUser}
        error if a L{User} in the exceptions list doesn't exist.
        """
        policyAndExceptions = TPolicyAndExceptions(u'closed', [u'unknown'])
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.updatePermission(
                session, u'tags', u'update', u'username/tag',
                policyAndExceptions)
            error = yield self.assertFailure(deferred, TNoSuchUser)
            self.assertEqual('unknown', error.name)

    @inlineCallbacks
    def testSetWithSuperuser(self):
        """
        L{FacadePermissionMixin.updatePermission} raises a L{TInvalidUsername}
        error if a superuser is specified in the exceptions list.
        """
        policyAndExceptions = TPolicyAndExceptions(u'closed', [u'fluiddb'])
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.updatePermission(
                session, u'tags', u'update', u'username/tag',
                policyAndExceptions)
            yield self.assertFailure(deferred, TInvalidUsername)

    @inlineCallbacks
    def testSetWithAnonymous(self):
        """
        L{FacadePermissionMixin.updatePermission} raises a L{TInvalidUsername}
        error if the anonymous user is specified in the exceptions list for
        non-allowed operations.
        """
        policyAndExceptions = TPolicyAndExceptions(u'closed', [u'anon'])
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.updatePermission(
                session, u'tags', u'update', u'username/tag',
                policyAndExceptions)
            yield self.assertFailure(deferred, TInvalidUsername)

    @inlineCallbacks
    def testSetWithUnknownUserUTF8EncodesUsername(self):
        """
        L{FacadePermissionMixin.updatePermission} raises a L{TNoSuchUser}
        error if a L{User} in the exceptions list doesn't exist.  The username
        passed to L{TNoSuchUser} is UTF-8 encoded.
        """
        policyAndExceptions = TPolicyAndExceptions(u'closed',
                                                   [u'\N{HIRAGANA LETTER A}'])
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.updatePermission(
                session, u'tags', u'update', u'username/tag',
                policyAndExceptions)
            error = yield self.assertFailure(deferred, TNoSuchUser)
            self.assertEqual(u'\N{HIRAGANA LETTER A}'.encode('utf-8'),
                             error.name)

    @inlineCallbacks
    def testSetNamespacePermissionsIsDenied(self):
        """
        L{FacadePermissionMixin.updatePermission} raises a
        L{TPathPermissionDenied} error if the user doesn't have
        C{Operation.CONTROL_NAMESPACE} permissions on the given L{Namespace}.
        """
        self.permissions.set([(u'username', Operation.CONTROL_NAMESPACE,
                               Policy.CLOSED, [])])
        policyAndExceptions = TPolicyAndExceptions(u'open', [])
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.updatePermission(session, u'namespaces',
                                                    u'control', u'username',
                                                    policyAndExceptions)
            yield self.assertFailure(deferred, TPathPermissionDenied)

    @inlineCallbacks
    def testSetTagPermissionsIsDenied(self):
        """
        L{FacadePermissionMixin.updatePermission} raises a
        L{TPathPermissionDenied} error if the user doesn't have
        C{Operation.CONTROL_TAG} permissions on the given L{Tag}.
        """
        self.permissions.set([(u'username/tag', Operation.CONTROL_TAG,
                               Policy.CLOSED, [])])
        policyAndExceptions = TPolicyAndExceptions(u'open', [])
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.updatePermission(
                session, u'tags', u'control', u'username/tag',
                policyAndExceptions)
            yield self.assertFailure(deferred, TPathPermissionDenied)

    @inlineCallbacks
    def testSetTagValuePermissionsIsDenied(self):
        """
        L{FacadePermissionMixin.updatePermission} raises a
        L{TPathPermissionDenied} error if the user doesn't have
        C{Operation.CONTROL_TAG_VALUE} permissions on the given L{Tag}.
        """
        self.permissions.set([(u'username/tag', Operation.CONTROL_TAG_VALUE,
                               Policy.CLOSED, [])])
        policyAndExceptions = TPolicyAndExceptions(u'open', [])
        with login(u'username', uuid4(), self.transact) as session:
            deferred = self.facade.updatePermission(
                session, u'tag-values', u'control', u'username/tag',
                policyAndExceptions)
            yield self.assertFailure(deferred, TPathPermissionDenied)
