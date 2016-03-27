from storm.exceptions import IntegrityError

from fluiddb.data.exceptions import MalformedPathError
from fluiddb.data.namespace import (
    Namespace, createNamespace, getNamespaces, getChildNamespaces,
    getChildTags)
from fluiddb.data.tag import createTag
from fluiddb.data.user import User, Role, createUser
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import DatabaseResource


class CreateNamespaceTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testCreateNamespace(self):
        """L{createNamespace} creates a new L{Namespace}."""
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        namespace = createNamespace(user, u'name')
        self.assertEqual(u'name', namespace.path)
        self.assertEqual(u'name', namespace.name)
        self.assertIdentical(None, namespace.parentID)
        self.assertNotIdentical(None, namespace.objectID)
        self.assertNotIdentical(None, namespace.creationTime)
        self.assertIdentical(user, namespace.creator)
        self.assertIdentical(None, namespace.parent)
        self.assertIdentical(None, namespace.children.one())

    def testCreateNamespaceWithMalformedPath(self):
        """
        L{createNamespace} raises a L{MalformedPathError} if an invalid path
        is provided.
        """
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        self.assertRaises(MalformedPathError, createNamespace, user, u'')

    def testCreateNamespaceAddsToStore(self):
        """L{createNamespace} adds the new L{Namespace} to the main store."""
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        namespace = createNamespace(user, u'name')
        result = self.store.find(Namespace, Namespace.name == u'name')
        self.assertIdentical(namespace, result.one())


class GetNamespacesTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testGetNamespaces(self):
        """
        L{getNamespaces} returns all L{Namespace}s in the database, by
        default.
        """
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        namespace = createNamespace(user, u'name')
        result = getNamespaces()
        self.assertEqual([namespace, user.namespace],
                         list(result.order_by(Namespace.path)))

    def testGetNamespacesWithPaths(self):
        """
        When L{Namespace.path}s are provided L{getNamespaces} returns matching
        L{Namespace}s.
        """
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        namespace = createNamespace(user, u'name')
        result = getNamespaces(paths=[u'name'])
        self.assertIdentical(namespace, result.one())

    def testGetNamespacesWithObjectIDs(self):
        """
        When L{Namespace.objectIDs}s are provided L{getNamespaces} returns
        matching L{Namespace}s.
        """
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        namespace = createNamespace(user, u'name')
        result = getNamespaces(objectIDs=[namespace.objectID])
        self.assertIdentical(namespace, result.one())


class GetChildNamespacesTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testGetChildNamespaces(self):
        """
        L{getChildNamespace} returns the child L{Namespace}s for the specified
        parent paths.
        """
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        createNamespace(user, u'ignored')
        parent = createNamespace(user, u'parent')
        child = createNamespace(user, u'parent/child', parent.id)
        self.assertEqual(child, getChildNamespaces([u'parent']).one())

    def testGetChildNamespacesOnlyConsidersDirectDescendants(self):
        """
        L{getChildNamespace} only returns L{Namespace}s that are direct
        descendants of the specified parent paths.
        """
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        parent = createNamespace(user, u'parent')
        child = createNamespace(user, u'parent/child', parent.id)
        createNamespace(user, u'parent/child/grandchild', child.id)
        self.assertEqual(child, getChildNamespaces([u'parent']).one())


class GetChildTagsTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testGetChildTags(self):
        """
        L{getChildTag} returns the child L{Namespace}s for the specified
        parent L{Namespace} paths.
        """
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        namespace = createNamespace(user, u'ignored')
        createTag(user, namespace, u'child')
        tag = createTag(user, user.namespace, u'child')
        self.assertEqual(tag, getChildTags([u'username']).one())


class NamespaceSchemaTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testUniquePathConstraint(self):
        """
        An C{IntegrityError} is raised if a L{Namespace} with a duplicate name
        is added to the database.
        """
        user = User(u'name', 'password-hash', u'User', u'user@example.com',
                    Role.USER)
        self.store.add(user)
        self.store.add(Namespace(user, u'name', u'name'))
        self.store.flush()
        self.store.add(Namespace(user, u'name', u'name'))
        self.assertRaises(IntegrityError, self.store.flush)
        self.store.rollback()

    def testUniqueObjectIDConstraint(self):
        """
        An C{IntegrityError} is raised if a L{Namespace} with a duplicate
        object ID is added to the database.
        """
        user = User(u'name', 'password-hash', u'User', u'user@example.com',
                    Role.USER)
        self.store.add(user)
        namespace1 = Namespace(user, u'name1', u'name1')
        self.store.add(namespace1)
        self.store.flush()
        namespace2 = Namespace(user, u'name2', u'name2')
        namespace2.objectID = namespace1.objectID
        self.store.add(namespace2)
        self.assertRaises(IntegrityError, self.store.flush)
        self.store.rollback()
