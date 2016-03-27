from fluiddb.data.namespace import createNamespace
from fluiddb.data.permission import (
    NamespacePermission, Operation, Policy, TagPermission,
    createNamespacePermission, getNamespacePermissions, createTagPermission,
    getTagPermissions)
from fluiddb.data.tag import createTag
from fluiddb.data.user import createUser
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import DatabaseResource


class NamespacePermissionTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testOperations(self):
        """
        L{NamespacePermission.allow} can check all valid L{Namespace}
        L{Operation}s.
        """
        self.assertEqual(sorted(NamespacePermission.operations.iterkeys()),
                         sorted(Operation.NAMESPACE_OPERATIONS))

    def testAllowWithInvalidOperation(self):
        """
        L{NamespacePermission.allow} raises a C{RuntimeError} if the request
        L{Operation} is not a namespace operation.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        permission = createNamespacePermission(namespace)
        self.assertRaises(RuntimeError, permission.allow, user.id,
                          Operation.WRITE_TAG_VALUE)

    def testAllowWithClosedPolicyAndUserInExceptions(self):
        """
        L{NamespacePermission.allow} grants access if the policy is
        L{Policy.CLOSED} and the L{User} is in the exceptions list.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        permission = createNamespacePermission(namespace)
        permission.createPolicy = Policy.CLOSED
        permission.createExceptions = [user.id]
        self.assertTrue(permission.allow(Operation.CREATE_NAMESPACE, user.id))

    def testAllowWithClosedPolicyAndUserNotInExceptions(self):
        """
        L{NamespacePermission.allow} denies access if the policy is
        L{Policy.CLOSED} and the L{User} is not in the exceptions list.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        permission = createNamespacePermission(namespace)
        permission.createPolicy = Policy.CLOSED
        permission.createExceptions = []
        self.assertFalse(permission.allow(Operation.CREATE_NAMESPACE, user.id))

    def testAllowWithOpenPolicyAndUserNotInExceptions(self):
        """
        L{NamespacePermission.allow} grants access if the policy is
        L{Policy.OPEN} and the L{User} is not in the exceptions list.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        permission = createNamespacePermission(namespace)
        permission.createPolicy = Policy.OPEN
        permission.createExceptions = []
        self.assertTrue(permission.allow(Operation.CREATE_NAMESPACE, user.id))

    def testAllowWithOpenPolicyAndUserInExceptions(self):
        """
        L{NamespacePermission.allow} denies access if the policy is
        L{Policy.OPEN} and the L{User} is in the exceptions list.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        permission = createNamespacePermission(namespace)
        permission.createPolicy = Policy.OPEN
        permission.createExceptions = [user.id]
        self.assertFalse(permission.allow(Operation.CREATE_NAMESPACE, user.id))

    def testGetWithInvalidOperation(self):
        """
        L{NamespacePermission.get} raises a C{RuntimeError} if an invalid
        L{Operation} is provided.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        permission = createNamespacePermission(namespace)
        self.assertRaises(RuntimeError, permission.get,
                          Operation.WRITE_TAG_VALUE)

    def testGet(self):
        """
        L{NamespacePermission.get} returns a C{(Policy, exceptions)} 2-tuple
        for the specified L{Operation}.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        permission = createNamespacePermission(namespace)
        permission.set(Operation.CREATE_NAMESPACE, Policy.OPEN, [user.id])
        self.assertEqual((Policy.OPEN, [user.id]),
                         permission.get(Operation.CREATE_NAMESPACE))

    def testSetWithInvalidOperation(self):
        """
        L{NamespacePermission.set} raises a C{RuntimeError} if an invalid
        L{Operation} is provided.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        permission = createNamespacePermission(namespace)
        self.assertRaises(RuntimeError, permission.set,
                          Operation.WRITE_TAG_VALUE, Policy.OPEN, [])

    def testSet(self):
        """
        L{NamespacePermission.set} updates the L{Policy} and exceptions list
        for an L{Operation}.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        permission = createNamespacePermission(namespace)
        self.assertEqual(Policy.CLOSED, permission.createPolicy)
        self.assertEqual([user.id], permission.createExceptions)
        permission.set(Operation.CREATE_NAMESPACE, Policy.OPEN, [])
        self.assertEqual(Policy.OPEN, permission.createPolicy)
        self.assertEqual([], permission.createExceptions)


class CreateNamespacePermissionTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testCreateNamespacePermission(self):
        """
        L{createNamespacePermission} creates a new L{NamespacePermission}
        using the system-wide default permission settings.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        permission = createNamespacePermission(namespace)
        self.assertNotIdentical(None, permission.namespaceID)
        self.assertEqual(namespace.id, permission.namespaceID)
        self.assertEqual(Policy.CLOSED, permission.createPolicy)
        self.assertEqual([user.id], permission.createExceptions)
        self.assertEqual(Policy.CLOSED, permission.updatePolicy)
        self.assertEqual([user.id], permission.updateExceptions)
        self.assertEqual(Policy.CLOSED, permission.deletePolicy)
        self.assertEqual([user.id], permission.deleteExceptions)
        self.assertEqual(Policy.OPEN, permission.listPolicy)
        self.assertEqual([], permission.listExceptions)
        self.assertEqual(Policy.CLOSED, permission.controlPolicy)
        self.assertEqual([user.id], permission.controlExceptions)

    def testCreateNamespacePermissionWithTemplate(self):
        """
        L{createNamespacePermission} can optionally use an existing
        L{NamespacePermission} as a template for the new one.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace1 = createNamespace(user, u'name1')
        permission1 = createNamespacePermission(namespace1)
        permission1.set(Operation.CREATE_NAMESPACE, Policy.OPEN, [])
        permission1.set(Operation.UPDATE_NAMESPACE, Policy.OPEN, [])
        permission1.set(Operation.DELETE_NAMESPACE, Policy.OPEN, [])
        permission1.set(Operation.LIST_NAMESPACE, Policy.CLOSED, [user.id])
        permission1.set(Operation.CONTROL_NAMESPACE, Policy.OPEN, [])

        namespace2 = createNamespace(user, u'name2')
        permission2 = createNamespacePermission(namespace2, permission1)
        self.assertEqual((Policy.OPEN, []),
                         permission2.get(Operation.CREATE_NAMESPACE))
        self.assertEqual((Policy.OPEN, []),
                         permission2.get(Operation.UPDATE_NAMESPACE))
        self.assertEqual((Policy.OPEN, []),
                         permission2.get(Operation.DELETE_NAMESPACE))
        self.assertEqual((Policy.CLOSED, [user.id]),
                         permission2.get(Operation.LIST_NAMESPACE))
        self.assertEqual((Policy.OPEN, []),
                         permission2.get(Operation.CONTROL_NAMESPACE))

    def testCreateNamespacePermissionAddsToStore(self):
        """
        L{createNamespacePermission} automatically adds the new
        L{NamespacePermission} to the database.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        permission = createNamespacePermission(namespace)
        result = self.store.find(
            NamespacePermission,
            NamespacePermission.namespaceID == namespace.id)
        self.assertIdentical(permission, result.one())


class GetNamespacePermissionsTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testGetNamespacePermissionsWithUnknownPaths(self):
        """
        L{getNamespacePermissions} returns an empty C{ResultSet} if
        L{Namespace}s and L{NamespacePermission}s matching the specified
        L{Namespace.path}s are not available.
        """
        self.assertEqual([], list(getNamespacePermissions([u'unknown'])))

    def testGetNamespacePermissions(self):
        """
        L{getNamespacePermissions} returns the L{Namespace}s and
        L{NamespacePermission}s that match the specified L{Namespace.path}s.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        parentNamespace = createNamespace(user, u'name')
        parentPermission = createNamespacePermission(parentNamespace)
        childNamespace = createNamespace(user, u'name/child',
                                         parentID=parentNamespace.id)
        createNamespacePermission(childNamespace)
        self.assertEqual((parentNamespace, parentPermission),
                         getNamespacePermissions([u'name']).one())


class TagPermissionTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testOperations(self):
        """
        L{TagPermission.allow} can check all valid L{Namespace} L{Operation}s.
        """
        self.assertEqual(sorted(TagPermission.operations.iterkeys()),
                         sorted(Operation.TAG_OPERATIONS))

    def testAllowWithInvalidOperation(self):
        """
        L{TagPermission.allow} raises a C{RuntimeError} if the request
        L{Operation} is not a namespace operation.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        permission = createTagPermission(tag)
        self.assertRaises(RuntimeError, permission.allow, user.id,
                          Operation.CREATE_NAMESPACE)

    def testAllowWithClosedPolicyAndUserInExceptions(self):
        """
        L{TagPermission.allow} grants access if the policy is L{Policy.CLOSED}
        and the L{User} is in the exceptions list.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        permission = createTagPermission(tag)
        permission.updatePolicy = Policy.CLOSED
        permission.updateExceptions = [user.id]
        self.assertTrue(permission.allow(Operation.UPDATE_TAG, user.id))

    def testAllowWithClosedPolicyAndUserNotInExceptions(self):
        """
        L{TagPermission.allow} denies access if the policy is L{Policy.CLOSED}
        and the L{User} is not in the exceptions list.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        permission = createTagPermission(tag)
        permission.updatePolicy = Policy.CLOSED
        permission.updateExceptions = []
        self.assertFalse(permission.allow(Operation.UPDATE_TAG, user.id))

    def testAllowWithOpenPolicyAndUserNotInExceptions(self):
        """
        L{TagPermission.allow} grants access if the policy is L{Policy.OPEN}
        and the L{User} is not in the exceptions list.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        permission = createTagPermission(tag)
        permission.updatePolicy = Policy.OPEN
        permission.updateExceptions = []
        self.assertTrue(permission.allow(Operation.UPDATE_TAG, user.id))

    def testAllowWithOpenPolicyAndUserInExceptions(self):
        """
        L{TagPermission.allow} denies access if the policy is L{Policy.OPEN}
        and the L{User} is in the exceptions list.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        permission = createTagPermission(tag)
        permission.updatePolicy = Policy.OPEN
        permission.updateExceptions = [user.id]
        self.assertFalse(permission.allow(Operation.UPDATE_TAG, user.id))

    def testSetWithInvalidOperation(self):
        """
        L{TagPermission.set} raises a C{RuntimeError} if an invalid
        L{Operation} is provided.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        permission = createTagPermission(tag)
        self.assertRaises(RuntimeError, permission.set,
                          Operation.CREATE_NAMESPACE, Policy.OPEN, [])

    def testSet(self):
        """
        L{TagPermission.set} updates the L{Policy} and exceptions list for an
        L{Operation}.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        permission = createTagPermission(tag)
        self.assertEqual(Policy.CLOSED, permission.updatePolicy)
        self.assertEqual([user.id], permission.updateExceptions)
        permission.set(Operation.UPDATE_TAG, Policy.OPEN, [])
        self.assertEqual(Policy.OPEN, permission.updatePolicy)
        self.assertEqual([], permission.updateExceptions)


class CreateTagPermissionTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testCreateTagPermission(self):
        """
        L{createTagPermission} creates a new L{TagPermission} using the
        system-wide default permission settings.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        permission = createTagPermission(tag)
        self.assertNotIdentical(None, permission.tagID)
        self.assertEqual(tag.id, permission.tagID)
        self.assertEqual(Policy.CLOSED, permission.updatePolicy)
        self.assertEqual([user.id], permission.updateExceptions)
        self.assertEqual(Policy.CLOSED, permission.deletePolicy)
        self.assertEqual([user.id], permission.deleteExceptions)
        self.assertEqual(Policy.CLOSED, permission.controlPolicy)
        self.assertEqual([user.id], permission.controlExceptions)
        self.assertEqual(Policy.CLOSED, permission.writeValuePolicy)
        self.assertEqual([user.id], permission.writeValueExceptions)
        self.assertEqual(Policy.OPEN, permission.readValuePolicy)
        self.assertEqual([], permission.readValueExceptions)
        self.assertEqual(Policy.CLOSED, permission.deleteValuePolicy)
        self.assertEqual([user.id], permission.deleteValueExceptions)
        self.assertEqual(Policy.CLOSED, permission.controlValuePolicy)
        self.assertEqual([user.id], permission.controlValueExceptions)

    def testCreateTagWithDefaultPermissions(self):
        """
        L{createTagPermission} creates a default set of permissions based on
        the default L{Namespace}s with permissions.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        createNamespacePermission(namespace)

        tag = createTag(user, namespace, u'tag')
        permission2 = createTagPermission(tag)
        self.assertEqual((Policy.CLOSED, [user.id]),
                         permission2.get(Operation.UPDATE_TAG))
        self.assertEqual((Policy.CLOSED, [user.id]),
                         permission2.get(Operation.DELETE_TAG))
        self.assertEqual((Policy.CLOSED, [user.id]),
                         permission2.get(Operation.CONTROL_TAG))
        self.assertEqual((Policy.CLOSED, [user.id]),
                         permission2.get(Operation.WRITE_TAG_VALUE))
        self.assertEqual((Policy.OPEN, []),
                         permission2.get(Operation.READ_TAG_VALUE))
        self.assertEqual((Policy.CLOSED, [user.id]),
                         permission2.get(Operation.DELETE_TAG_VALUE))
        self.assertEqual((Policy.CLOSED, [user.id]),
                         permission2.get(Operation.CONTROL_TAG_VALUE))

    def testCreateTagPermissionInheritsFromNamespace(self):
        """
        L{createTagPermission} inherits permissions from its parent's
        L{NamespacePermission}s.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        permission1 = createNamespacePermission(namespace)
        permission1.set(Operation.CREATE_NAMESPACE, Policy.OPEN, [])
        permission1.set(Operation.UPDATE_NAMESPACE, Policy.OPEN, [])
        permission1.set(Operation.DELETE_NAMESPACE, Policy.OPEN, [])
        permission1.set(Operation.LIST_NAMESPACE, Policy.CLOSED, [user.id])
        permission1.set(Operation.CONTROL_NAMESPACE, Policy.OPEN, [])

        tag = createTag(user, namespace, u'tag')
        permission2 = createTagPermission(tag)
        self.assertEqual((Policy.OPEN, []),
                         permission2.get(Operation.UPDATE_TAG))
        self.assertEqual((Policy.OPEN, []),
                         permission2.get(Operation.DELETE_TAG))
        self.assertEqual((Policy.OPEN, []),
                         permission2.get(Operation.CONTROL_TAG))
        self.assertEqual((Policy.OPEN, []),
                         permission2.get(Operation.WRITE_TAG_VALUE))
        self.assertEqual((Policy.CLOSED, [user.id]),
                         permission2.get(Operation.READ_TAG_VALUE))
        self.assertEqual((Policy.OPEN, []),
                         permission2.get(Operation.DELETE_TAG_VALUE))
        self.assertEqual((Policy.OPEN, []),
                         permission2.get(Operation.CONTROL_TAG_VALUE))

    def testCreateTagPermissionAddsToStore(self):
        """
        L{createTagPermission} automatically adds the new L{TagPermission} to
        the database.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        tag = createTag(user, namespace, u'tag')
        permission = createTagPermission(tag)
        result = self.store.find(
            TagPermission,
            TagPermission.tagID == tag.id)
        self.assertIdentical(permission, result.one())


class GetTagPermissionsTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testGetTagPermissionsWithUnknownPaths(self):
        """
        L{getTagPermissions} returns an empty C{ResultSet} if L{Tag}s and
        L{TagPermission}s matching the specified L{Tag.path}s are not
        available.
        """
        self.assertEqual([], list(getTagPermissions([u'unknown'])))

    def testGetTagPermissions(self):
        """
        L{getTagPermissions} returns the L{Tag}s and L{TagPermission}s that
        match the specified L{Tag.path}s.
        """
        user = createUser(u'name', u'password', u'Name', u'name@example.com')
        namespace = createNamespace(user, u'name')
        createTag(user, namespace, u'unwanted')
        tag = createTag(user, namespace, u'tag')
        permission = createTagPermission(tag)
        self.assertEqual((tag, permission),
                         getTagPermissions([u'name/tag']).one())
