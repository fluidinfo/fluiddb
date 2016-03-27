from storm.locals import Not

from fluiddb.data.exceptions import MalformedPathError
from fluiddb.data.namespace import Namespace, createNamespace, getNamespaces
from fluiddb.data.permission import (
    NamespacePermission, Operation, Policy, getNamespacePermissions)
from fluiddb.data.system import createSystemData
from fluiddb.data.tag import createTag, getTags
from fluiddb.data.value import createTagValue, getTagValues
from fluiddb.model.exceptions import DuplicatePathError, NotEmptyError
from fluiddb.model.namespace import NamespaceAPI
from fluiddb.model.permission import PermissionAPI
from fluiddb.model.user import UserAPI, getUser
from fluiddb.model.value import TagValueAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import ConfigResource, DatabaseResource


class NamespaceAPITestMixin(object):

    def assertDefaultPermissions(self, namespacePath):
        """
        Assert that a L{NamespacePermission} exists for the specified
        L{Namespace.path} and that it uses the default system-wide policy.
        """
        result = self.store.find(
            NamespacePermission,
            NamespacePermission.namespaceID == Namespace.id,
            Namespace.path == namespacePath)
        permission = result.one()
        self.assertEqual(Policy.CLOSED, permission.createPolicy)
        self.assertEqual([self.user.id], permission.createExceptions)
        self.assertEqual(Policy.CLOSED, permission.updatePolicy)
        self.assertEqual([self.user.id], permission.updateExceptions)
        self.assertEqual(Policy.CLOSED, permission.deletePolicy)
        self.assertEqual([self.user.id], permission.deleteExceptions)
        self.assertEqual(Policy.OPEN, permission.listPolicy)
        self.assertEqual([], permission.listExceptions)
        self.assertEqual(Policy.CLOSED, permission.controlPolicy)
        self.assertEqual([self.user.id], permission.controlExceptions)

    def testCreateChildNamespace(self):
        """
        L{NamespaceAPI.create} creates new L{Namespace}s based on the provided
        data.
        """
        values = [(u'username/child-namespace', u'A description')]
        self.namespaces.create(values)
        result = self.store.find(Namespace,
                                 Namespace.path == u'username/child-namespace')
        namespace = result.one()
        self.assertEqual(u'username/child-namespace', namespace.path)
        self.assertEqual(u'child-namespace', namespace.name)
        self.assertIdentical(self.user.namespace, namespace.parent)

    def testCreateChildNamespaceInheritsParentNamespacePermissions(self):
        """
        L{NamespaceAPI.create} creates new L{Namespace}s with
        L{Operation.CREATE_NAMESPACE} permissions inherited from the parent
        L{Namespace}'s permissions.
        """
        UserAPI().create([(u'user', u'secret', u'name', u'user@example.com')])
        user = getUser(u'user')
        PermissionAPI(self.user).set([
            (u'user', Operation.CREATE_NAMESPACE, Policy.OPEN, []),
            (u'user', Operation.UPDATE_NAMESPACE, Policy.OPEN, []),
            (u'user', Operation.DELETE_NAMESPACE, Policy.OPEN, []),
            (u'user', Operation.LIST_NAMESPACE, Policy.CLOSED, [u'user']),
            (u'user', Operation.CONTROL_NAMESPACE, Policy.OPEN, [])])

        self.namespaces.create([(u'user/child', u'A child namespace')])
        result = getNamespacePermissions([u'user/child'])
        namespace, permission = result.one()
        self.assertEqual((Policy.OPEN, []),
                         permission.get(Operation.CREATE_NAMESPACE))
        self.assertEqual((Policy.OPEN, []),
                         permission.get(Operation.UPDATE_NAMESPACE))
        self.assertEqual((Policy.OPEN, []),
                         permission.get(Operation.DELETE_NAMESPACE))
        self.assertEqual((Policy.CLOSED, [user.id]),
                         permission.get(Operation.LIST_NAMESPACE))
        self.assertEqual((Policy.OPEN, []),
                         permission.get(Operation.CONTROL_NAMESPACE))

    def testCreateCreatesPermissions(self):
        """
        L{NamespaceAPI.create} creates permissions for the newly created
        L{Namespace}s.
        """
        values = [(u'username/namespace', u'A description')]
        self.namespaces.create(values)
        self.assertDefaultPermissions(u'username/namespace')

    def testCreateRootNamespace(self):
        """
        L{NamespaceAPI.create} creates new root L{Namespace}s based on the
        provided data.
        """
        superuser = self.system.users[u'fluiddb']
        values = [(u'root-namespace', u'A description.')]
        NamespaceAPI(superuser).create(values)
        result = self.store.find(Namespace,
                                 Namespace.path == u'root-namespace')
        namespace = result.one()
        self.assertEqual(u'root-namespace', namespace.path)
        self.assertEqual(u'root-namespace', namespace.name)
        self.assertIdentical(None, namespace.parent)

    def testCreateWithImplicitNamespace(self):
        """
        L{NamespaceAPI.create} creates missing parent L{Namespace}s
        automatically.
        """
        values = [(u'username/nested/namespace', u'A description')]
        self.namespaces.create(values)
        result = self.store.find(
            Namespace, Namespace.path == u'username/nested/namespace')
        namespace = result.one()
        self.assertEqual(u'username/nested/namespace', namespace.path)
        self.assertEqual(u'namespace', namespace.name)
        parent = namespace.parent
        self.assertEqual(u'username/nested', parent.path)
        self.assertIdentical(self.user.namespace, parent.parent)

    def testCreateExplicitParentNamespace(self):
        """
        L{NamespaceAPI.create} won't create a parent implicitly if the parent
        is already in the path list.
        """
        values = [(u'username/parent', u'Parent Namespace'),
                  (u'username/parent/child', u'Child Namespace')]
        self.namespaces.create(values)
        result = self.store.find(
            Namespace, Namespace.path == u'username/parent/child')
        namespace = result.one()
        self.assertEqual(u'username/parent/child', namespace.path)
        self.assertEqual(u'child', namespace.name)
        parent = namespace.parent
        self.assertEqual(u'username/parent', parent.path)
        self.assertIdentical(self.user.namespace, parent.parent)

    def testCreatePermissionsWithImplicitNamespace(self):
        """
        L{NamespaceAPI.create} creates permissions for the newly created
        L{Namespace}s.
        """
        values = [(u'username/implicit/namespace', u'A description')]
        self.namespaces.create(values)
        self.assertDefaultPermissions(u'username/implicit')
        self.assertDefaultPermissions(u'username/implicit/namespace')

    def testCreateWithImplicitNestedNamespace(self):
        """
        L{NamespaceAPI.create} creates missing parent L{Namespace}s
        automatically, even when many levels are missing.
        """
        values = [(u'username/nested/foo/bar', u'A description')]
        self.namespaces.create(values)
        result = self.store.find(
            Namespace, Namespace.path == u'username/nested/foo/bar')
        namespace = result.one()
        self.assertEqual(u'username/nested/foo/bar', namespace.path)
        self.assertEqual(u'bar', namespace.name)
        self.assertIdentical(self.user.namespace,
                             namespace.parent.parent.parent)

    def testCreateStoresNamespaceDescriptions(self):
        """
        L{NamespaceAPI.create} creates new C{fluiddb/namespaces/description}
        L{TagValue}s to store the specified L{Namespace} descriptions.
        """
        values = [(u'username/namespace', u'A namespace description')]
        [(objectID, path)] = self.namespaces.create(values)
        tag = getTags(paths=[u'fluiddb/namespaces/description']).one()
        value = getTagValues([(objectID, tag.id)]).one()
        self.assertEqual(u'A namespace description', value.value)

    def testCreateStoresNamespacePaths(self):
        """
        L{NamespaceAPI.create} creates new C{fluiddb/namespaces/path}
        L{TagValue}s to store the specified L{Namespace} paths.
        """
        values = [(u'username/namespace', u'A namespace description')]
        [(objectID, path)] = self.namespaces.create(values)
        tag = getTags(paths=[u'fluiddb/namespaces/path']).one()
        value = getTagValues([(objectID, tag.id)]).one()
        self.assertEqual(u'username/namespace', value.value)

    def testCreateCreatesAboutTag(self):
        """
        L{NamespaceAPI.create} creates new C{fluiddb/about} L{TagValue}s when
        creating new L{Namespace}s.
        """
        values = [(u'username/namespace', u'A namespace description')]
        [(objectID, path)] = self.namespaces.create(values)
        tag = getTags(paths=[u'fluiddb/about']).one()
        value = getTagValues([(objectID, tag.id)]).one()
        self.assertEqual(u'Object for the namespace username/namespace',
                         value.value)

    def testCreateReusesPreviousObjectIDs(self):
        """
        If a L{Namespace} is deleted and created again, L{NamespaceAPI.create}
        uses the old object ID.
        """
        values = [(u'username/namespace', u'A namespace description')]
        [(firstObjectID, path)] = self.namespaces.create(values)
        self.namespaces.delete([u'username/namespace'])
        [(secondObjectID, path)] = self.namespaces.create(values)
        self.assertEqual(firstObjectID, secondObjectID)

    def testCreateWithExistingNamespacePath(self):
        """
        L{NamespaceAPI.create} raises a L{DuplicatePathError} exception if an
        attempt to create a L{Namespace} with the same path as an existing
        L{Namespace} is made.
        """
        self.namespaces.create([(u'username/test', u'description')])
        self.assertRaises(
            DuplicatePathError, self.namespaces.create,
            [(u'username/test', u'Already used namespace path.')])

    def testCreateWithExistingTagPath(self):
        """
        L{NamespaceAPI.create} can be used to create L{Namespace}s with the
        same path as an existing L{Namespace}.
        """
        createTag(self.user, self.user.namespace, u'name')
        values = [(u'username/name', u'A description')]
        self.namespaces.create(values)
        result = self.store.find(Namespace, Namespace.path == u'username/name')
        namespace = result.one()
        self.assertEqual(u'username/name', namespace.path)
        self.assertEqual(u'name', namespace.name)
        self.assertIdentical(self.user.namespace, namespace.parent)

    def testGetWithoutData(self):
        """
        L{NamespaceAPI.get} returns an empty C{dict} if no L{Namespace.path}s
        are provided.
        """
        self.assertEqual({}, self.namespaces.get([]))

    def testGet(self):
        """
        L{NamespaceAPI.get} returns L{Namespace}s that match the specified
        paths.
        """
        namespace = createNamespace(self.user, u'namespace')
        self.assertEqual({'namespace': {'id': namespace.objectID}},
                         self.namespaces.get([u'namespace']))

    def testGetWithDescriptions(self):
        """
        L{NamespaceAPI.get} can optionally include L{Namespace.description}s
        in the result.
        """
        descriptionTag = self.system.tags[u'fluiddb/namespaces/description']
        namespace = createNamespace(self.user, u'namespace')
        createTagValue(self.user.id, descriptionTag.id, namespace.objectID,
                       u'A namespace')
        result = self.namespaces.get([u'namespace'], withDescriptions=True)
        self.assertEqual(namespace.objectID, result['namespace']['id'])
        self.assertEqual(u'A namespace', result['namespace']['description'])

    def testGetWithNamespaces(self):
        """
        L{NamespaceAPI.get} can optionally include the names of child
        L{Namespace} in the result.
        """
        createNamespace(self.user, u'username/child', self.user.namespace.id)
        result = self.namespaces.get([u'username'], withNamespaces=True)
        result['username']['namespaceNames'].sort()
        self.assertEqual({'username': {'id': self.user.namespace.objectID,
                                       'namespaceNames': [u'child',
                                                          u'private']}},
                         result)

    def testGetWithNamespacesWithoutChildren(self):
        """
        L{NamespaceAPI.get} returns an empty C{list} when child L{Namespace}s
        are requested for a namespace that doesn't have any.
        """
        self.assertEqual({'username': {'id': self.user.namespace.objectID,
                                       'namespaceNames': [u'private']}},
                         self.namespaces.get([u'username'],
                                             withNamespaces=True))

    def testGetWithTags(self):
        """
        L{NamespaceAPI.get} can optionally include the names of child L{Tag}s
        in the result.
        """
        createTag(self.user, self.user.namespace, u'tag')
        self.assertEqual({'username': {'id': self.user.namespace.objectID,
                                       'tagNames': [u'tag']}},
                         self.namespaces.get([u'username'], withTags=True))

    def testGetWithTagsWithoutChildren(self):
        """
        L{NamespaceAPI.get} returns an empty C{list} when child L{Tag}s are
        requested for a L{Namespace} that doesn't have any.
        """
        self.assertEqual({'username': {'id': self.user.namespace.objectID,
                                       'tagNames': []}},
                         self.namespaces.get([u'username'], withTags=True))

    def testDelete(self):
        """L{NamespaceAPI.delete} removes L{Namespace}s."""
        self.namespaces.create([(u'username/child', u'A description')])
        self.namespaces.delete([u'username/child'])
        result = self.store.find(Namespace,
                                 Namespace.path == u'username/child')
        self.assertIdentical(None, result.one())

    def testDeleteDoesNotDeleteOtherNamespaces(self):
        """
        L{NamespaceAPI.delete} does not delete namespaces other than the
        ones it's asked to delete.
        """
        self.namespaces.create([(u'username/child1', u'A description')])
        self.namespaces.create([(u'username/child2', u'A description')])
        self.namespaces.delete([u'username/child1'])
        result = self.store.find(Namespace,
                                 Namespace.path == u'username/child2')
        namespace = result.one()
        self.assertEqual(u'username/child2', namespace.path)

    def testDeleteDoesNotDeleteOtherNamespacesWhenPassedAGenerator(self):
        """
        L{NamespaceAPI.delete} removes just the L{Namespace}s it is asked
        to delete when passed a generator (as opposed to a C{list}.
        """
        self.namespaces.create([(u'username/child1', u'A description')])
        self.namespaces.create([(u'username/child2', u'A description')])
        self.namespaces.delete(name for name in [u'username/child1'])
        result = self.store.find(Namespace,
                                 Namespace.path == u'username/child2')
        namespace = result.one()
        self.assertEqual(u'username/child2', namespace.path)

    def testDeleteRemovesDescription(self):
        """
        L{NamespaceAPI.delete} removes the C{fluiddb/namespaces/description}
        values stored for deleted L{Namespace}s.
        """
        values = [(u'username/child', u'A description')]
        [(objectID, path)] = self.namespaces.create(values)
        self.namespaces.delete([u'username/child'])
        result = TagValueAPI(self.user).get(
            objectIDs=[objectID], paths=[u'fluiddb/namespaces/description'])
        self.assertEqual({}, result)

    def testDeleteRemovesPath(self):
        """
        L{NamespaceAPI.delete} removes the C{fluiddb/namespaces/path}
        values stored for deleted L{Namespace}s.
        """
        values = [(u'username/child', u'A description')]
        [(objectID, path)] = self.namespaces.create(values)
        self.namespaces.delete([u'username/child'])
        result = TagValueAPI(self.user).get(objectIDs=[objectID],
                                            paths=[u'fluiddb/namespaces/path'])
        self.assertEqual({}, result)

    def testDeleteRemovesPermissions(self):
        """L{TagAPI.delete} removes permissions when L{Tag}s are deleted."""
        values = [(u'username/child', u'A description')]
        [(objectID, path)] = self.namespaces.create(values)

        self.namespaces.delete([u'username/child'])
        result = self.store.find(
            NamespacePermission,
            NamespacePermission.namespaceID == Namespace.id,
            Namespace.path == u'username/child')
        self.assertTrue(result.is_empty())

    def testDeleteKeepsTheAboutTag(self):
        """
        L{NamespaceAPI.delete} keeps the C{fluiddb/about} tag value for the
        deleted namespace.
        """
        values = [(u'username/namespace', u'A namespace description')]
        [(objectID, path)] = self.namespaces.create(values)
        self.namespaces.delete([u'username/namespace'])
        tag = getTags(paths=[u'fluiddb/about']).one()
        value = getTagValues([(objectID, tag.id)]).one()
        self.assertEqual(u'Object for the namespace username/namespace',
                         value.value)

    def testDeleteReturnsDeletedNamespaces(self):
        """L{NamespaceAPI.delete} returns the list of removed L{Namespace}s."""
        result1 = self.namespaces.create([(u'username/child', u'A namespace')])
        result2 = self.namespaces.delete([u'username/child'])
        self.assertEqual(result1, result2)

    def testDeleteWithChildNamespace(self):
        """
        L{NamespaceAPI.delete} raises a L{NotEmptyError} if a child
        L{Namespace} exists.
        """
        self.namespaces.create([(u'username/child', u'A description')])
        self.namespaces.create([(u'username/child/child', u'A description')])
        self.assertRaises(NotEmptyError,
                          self.namespaces.delete, [u'username/child'])

    def testDeleteWithChildTag(self):
        """
        L{NamespaceAPI.delete} raises a L{NotEmptyError} if a child L{Tag}
        exists.
        """
        self.namespaces.create([(u'username/child', u'A description')])
        namespace = getNamespaces(paths=[u'username/child']).one()
        createTag(self.user, namespace, u'tag')
        self.assertRaises(NotEmptyError,
                          self.namespaces.delete, [u'username/child'])

    def testSet(self):
        """
        L{NamespaceAPI.set} updates the description for the specified
        L{Namespace}s.
        """
        descriptionTag = self.system.tags[u'fluiddb/namespaces/description']
        self.namespaces.set({u'username': u'A fancy new description.'})
        result = getTagValues(
            [(self.user.namespace.objectID, descriptionTag.id)])
        description = result.one()
        self.assertEqual(u'A fancy new description.', description.value)

    def testSetReturnsUpdatedNamespaces(self):
        """L{NamespaceAPI.set} returns the list of updated L{Namespace}s."""
        result1 = self.namespaces.create([(u'username/child', u'old')])
        result2 = self.namespaces.set({u'username/child': u'new'})
        self.assertEqual(result1, result2)

    def testDeletePermissions(self):
        """
        L{NamespaceAPI.delete} deletes all the permissions for the given
        L{Namespace}s.
        """
        self.namespaces.create([(u'username/test', u'description')])
        self.namespaces.delete([u'username/test'])
        result = self.store.find(
            NamespacePermission,
            NamespacePermission.namespaceID == Namespace.id,
            Namespace.path == u'username/test')
        self.assertIdentical(None, result.one())

    def testPermissionsAreNotDeletedIfDeleteFails(self):
        """
        If L{NamespaceAPI.delete} fails, no permissions should be deleted.
        """
        self.namespaces.create([(u'username/test', u'description')])
        self.namespaces.create([(u'username/test/child', u'description')])
        self.assertRaises(NotEmptyError, self.namespaces.delete,
                          [u'username/test'])
        self.assertDefaultPermissions(u'username/test')


class NamespaceAPITest(NamespaceAPITestMixin, FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(NamespaceAPITest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.namespaces = NamespaceAPI(self.user)
        self.permissions = PermissionAPI(self.user)

    def testCreateWithoutData(self):
        """
        L{NamespaceAPI.create} returns an empty C{list} if no L{Namespace}
        data is available.
        """
        result = self.namespaces.create([])
        self.assertEqual([], result)
        ignored = (
            self.system.namespaces.keys() + [u'username', u'username/private'])
        result = self.store.find(Namespace, Not(Namespace.path.is_in(ignored)))
        self.assertIdentical(None, result.one())

    def testPermissionsAreNotCreatedIfCreateFails(self):
        """
        If L{NamespaceAPI.create} fails, no permissions should be created.
        """
        self.assertRaises(MalformedPathError, self.namespaces.create,
                          [(u'!!!!/test', u'description')])

        result = getNamespacePermissions([u'username/test'])
        self.assertTrue(result.is_empty())
