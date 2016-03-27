from uuid import uuid4

from storm.locals import Not

from fluiddb.data.namespace import Namespace, createNamespace
from fluiddb.data.object import getDirtyObjects, DirtyObject
from fluiddb.data.permission import (
    NamespacePermission, Operation, Policy, TagPermission, createTagPermission,
    getTagPermissions)
from fluiddb.data.system import createSystemData
from fluiddb.data.tag import Tag, createTag, getTags
from fluiddb.data.value import createTagValue, getTagValues
from fluiddb.exceptions import FeatureError
from fluiddb.model.exceptions import DuplicatePathError
from fluiddb.model.permission import PermissionAPI
from fluiddb.model.tag import TagAPI
from fluiddb.model.user import UserAPI, getUser
from fluiddb.model.value import TagValueAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import ConfigResource, DatabaseResource


class TagAPITestMixin(object):

    def assertDefaultPermissions(self, user, tagPath):
        """
        Assert that a L{TagPermission} exists for the specified L{Tag.path}
        and that it uses the default system-wide policy.
        """
        tag, permission = getTagPermissions([tagPath]).one()
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

    def testCreateWithoutData(self):
        """
        L{SecureTagAPI.create} raises a L{FeatureError} when no L{Tag}
        data is provided.
        """
        self.assertRaises(FeatureError, self.tags.create, [])

    def testCreate(self):
        """L{TagAPI.create} creates new L{Tag}s using the provided data."""
        values = [(u'username/tag', u'A description')]
        self.tags.create(values)
        systemTags = self.system.tags.keys()
        tag = self.store.find(Tag, Not(Tag.path.is_in(systemTags))).one()
        self.assertEqual(u'username/tag', tag.path)
        self.assertEqual(u'tag', tag.name)
        self.assertIdentical(self.user.namespace, tag.namespace)

    def testCreateCreatesPermissions(self):
        """
        L{TagAPI.create} creates permissions for the newly created L{Tag}s.
        """
        self.tags.create([(u'username/tag', u'A description')])
        self.assertDefaultPermissions(self.user, u'username/tag')

    def testCreateChildTagInheritsPermissions(self):
        """
        L{TagAPI.create} creates new L{Namespace}s based on the provided data.
        """
        UserAPI().create([(u'user', u'secret', u'name', u'user@example.com')])
        user = getUser(u'user')
        TagAPI(user).create([(u'user/tag', u'A description')])
        self.assertDefaultPermissions(user, u'user/tag')

    def testCreateChildTagInheritsParentNamespacePermissions(self):
        """
        L{TagAPI.create} creates new L{Tag}s with permissions inherited from
        the parent L{Namespace}'s permissions.
        """
        PermissionAPI(self.user).set([
            (u'username', Operation.CREATE_NAMESPACE, Policy.CLOSED,
             [u'username']),
            (u'username', Operation.UPDATE_NAMESPACE, Policy.OPEN, []),
            (u'username', Operation.DELETE_NAMESPACE, Policy.OPEN, []),
            (u'username', Operation.LIST_NAMESPACE, Policy.CLOSED,
             [u'username']),
            (u'username', Operation.CONTROL_NAMESPACE, Policy.OPEN, [])])

        self.tags.create([(u'username/tag', u'A child tag')])
        result = getTagPermissions([u'username/tag'])
        tag, permission = result.one()
        self.assertEqual((Policy.CLOSED, [self.user.id]),
                         permission.get(Operation.UPDATE_TAG))
        self.assertEqual((Policy.CLOSED, [self.user.id]),
                         permission.get(Operation.DELETE_TAG))
        self.assertEqual((Policy.OPEN, []),
                         permission.get(Operation.CONTROL_TAG))
        self.assertEqual((Policy.CLOSED, [self.user.id]),
                         permission.get(Operation.WRITE_TAG_VALUE))
        self.assertEqual((Policy.CLOSED, [self.user.id]),
                         permission.get(Operation.READ_TAG_VALUE))
        self.assertEqual((Policy.CLOSED, [self.user.id]),
                         permission.get(Operation.DELETE_TAG_VALUE))
        self.assertEqual((Policy.OPEN, []),
                         permission.get(Operation.CONTROL_TAG_VALUE))

    def testCreateChildTagWithDelegatedCreator(self):
        """
        L{TagAPI.create} always ensures that a new L{Tag} is usable by the
        L{User} that created it.  In the case of default permissions, the user
        creating the new L{Tag} is granted L{Operation.UPDATE_TAG},
        L{Operation.DELETE_TAG}, L{Operation.WRITE_TAG_VALUE} and
        L{Operation.DELETE_TAG_VALUE}.
        """
        UserAPI().create(
            [(u'friend', u'secret', u'name', u'user1@example.com')])
        PermissionAPI(self.user).set(
            [(u'username', Operation.CREATE_NAMESPACE,
              Policy.CLOSED, [u'username', u'friend'])])

        friend = getUser(u'friend')
        TagAPI(friend).create([(u'username/tag', u'A shared tag')])
        result = getTagPermissions([u'username/tag'])
        tag, permission = result.one()
        self.assertEqual((Policy.CLOSED, [self.user.id, friend.id]),
                         permission.get(Operation.UPDATE_TAG))
        self.assertEqual((Policy.CLOSED, [self.user.id, friend.id]),
                         permission.get(Operation.DELETE_TAG))
        self.assertEqual((Policy.CLOSED, [self.user.id]),
                         permission.get(Operation.CONTROL_TAG))
        self.assertEqual((Policy.CLOSED, [self.user.id, friend.id]),
                         permission.get(Operation.WRITE_TAG_VALUE))
        self.assertEqual((Policy.OPEN, []),
                         permission.get(Operation.READ_TAG_VALUE))
        self.assertEqual((Policy.CLOSED, [self.user.id, friend.id]),
                         permission.get(Operation.DELETE_TAG_VALUE))
        self.assertEqual((Policy.CLOSED, [self.user.id]),
                         permission.get(Operation.CONTROL_TAG_VALUE))

    def testCreatePublicChildTagWithDelegatedCreator(self):
        """
        L{TagAPI.create} always ensures that a new L{Tag} is usable by the
        L{User} that created it.
        """
        UserAPI().create(
            [(u'friend', u'secret', u'name', u'user1@example.com')])
        PermissionAPI(self.user).set(
            [(u'username', Operation.CREATE_NAMESPACE, Policy.OPEN, [])])

        friend = getUser(u'friend')
        TagAPI(friend).create([(u'username/tag', u'A shared tag')])
        result = getTagPermissions([u'username/tag'])
        tag, permission = result.one()
        self.assertEqual((Policy.OPEN, []),
                         permission.get(Operation.UPDATE_TAG))
        self.assertEqual((Policy.OPEN, []),
                         permission.get(Operation.DELETE_TAG))
        self.assertEqual((Policy.CLOSED, [self.user.id]),
                         permission.get(Operation.CONTROL_TAG))
        self.assertEqual((Policy.OPEN, []),
                         permission.get(Operation.WRITE_TAG_VALUE))
        self.assertEqual((Policy.OPEN, []),
                         permission.get(Operation.READ_TAG_VALUE))
        self.assertEqual((Policy.OPEN, []),
                         permission.get(Operation.DELETE_TAG_VALUE))
        self.assertEqual((Policy.CLOSED, [self.user.id]),
                         permission.get(Operation.CONTROL_TAG_VALUE))

    def testCreatePrivateChildTagWithDelegatedCreator(self):
        """
        L{TagAPI.create} always ensures that a new L{Tag} is usable by the
        L{User} that created it.  If the L{Operation.READ_TAG_VALUE}
        permission is L{Policy.CLOSED} the creator is added to the exceptions
        list.
        """
        UserAPI().create(
            [(u'friend', u'secret', u'name', u'user1@example.com')])
        PermissionAPI(self.user).set(
            [(u'username', Operation.CREATE_NAMESPACE, Policy.CLOSED,
              [u'username', u'friend']),
             (u'username', Operation.LIST_NAMESPACE, Policy.CLOSED,
              [u'username', u'friend'])])

        friend = getUser(u'friend')
        TagAPI(friend).create([(u'username/tag', u'A shared tag')])
        result = getTagPermissions([u'username/tag'])
        tag, permission = result.one()
        self.assertEqual((Policy.CLOSED, [self.user.id, friend.id]),
                         permission.get(Operation.UPDATE_TAG))
        self.assertEqual((Policy.CLOSED, [self.user.id, friend.id]),
                         permission.get(Operation.DELETE_TAG))
        self.assertEqual((Policy.CLOSED, [self.user.id]),
                         permission.get(Operation.CONTROL_TAG))
        self.assertEqual((Policy.CLOSED, [self.user.id, friend.id]),
                         permission.get(Operation.WRITE_TAG_VALUE))
        self.assertEqual((Policy.CLOSED, [self.user.id, friend.id]),
                         permission.get(Operation.READ_TAG_VALUE))
        self.assertEqual((Policy.CLOSED, [self.user.id, friend.id]),
                         permission.get(Operation.DELETE_TAG_VALUE))
        self.assertEqual((Policy.CLOSED, [self.user.id]),
                         permission.get(Operation.CONTROL_TAG_VALUE))

    def testCreateStoresTagDescriptions(self):
        """
        L{TagAPI.create} creates new C{fluiddb/tags/description} L{TagValue}s
        to store the specified L{Tag} descriptions.
        """
        values = [(u'username/tag', u'A tag description')]
        [(objectID, path)] = self.tags.create(values)
        tag = getTags(paths=[u'fluiddb/tags/description']).one()
        value = getTagValues([(objectID, tag.id)]).one()
        self.assertEqual(u'A tag description', value.value)

    def testCreateStoresTagPaths(self):
        """
        L{TagAPI.create} creates new C{fluiddb/tags/path} L{TagValue}s to store
        the specified L{Tag} paths.
        """
        values = [(u'username/tag', u'A tag description')]
        [(objectID, path)] = self.tags.create(values)
        tag = getTags(paths=[u'fluiddb/tags/path']).one()
        value = getTagValues([(objectID, tag.id)]).one()
        self.assertEqual(u'username/tag', value.value)

    def testCreateCreatesAboutTag(self):
        """
        L{TagAPI.create} creates new C{fluiddb/about} L{TagValue}s when
        creating new L{Tag}s.
        """
        values = [(u'username/tag', u'A tag description')]
        [(objectID, path)] = self.tags.create(values)
        tag = getTags(paths=[u'fluiddb/about']).one()
        value = getTagValues([(objectID, tag.id)]).one()
        self.assertEqual(u'Object for the attribute username/tag', value.value)

    def testCreateReusesPreviousObjectIDs(self):
        """
        If a L{Tag} is deleted and created again, L{TagAPI.create}
        uses the old object ID.
        """
        values = [(u'username/tag', u'A tag description')]
        [(firstObjectID, path)] = self.tags.create(values)
        self.tags.delete([u'username/tag'])
        [(secondObjectID, path)] = self.tags.create(values)
        self.assertEqual(firstObjectID, secondObjectID)

    def testCreateWithExistingNamespacePath(self):
        """
        L{TagAPI.create} can be used to create L{Tag}s with the same path as
        an existing L{Namespace}.
        """
        createNamespace(self.user, u'username/name', self.user.namespace.id)
        values = [(u'username/name', u'A description')]
        self.tags.create(values)
        systemTags = self.system.tags.keys()
        tag = self.store.find(Tag, Not(Tag.path.is_in(systemTags))).one()
        self.assertEqual(u'username/name', tag.path)
        self.assertEqual(u'name', tag.name)
        self.assertIdentical(self.user.namespace, tag.namespace)

    def testCreateWithExistingTagPath(self):
        """
        L{TagAPI.create} raises a L{DuplicatePathError} exception if an
        attempt to create a L{Tag} with the same path an existing L{Tag} is
        made.
        """
        createTag(self.user, self.user.namespace, u'name')
        self.assertRaises(
            DuplicatePathError, self.tags.create,
            [(u'username/name', u'Already used tag path.')])

    def testCreatePermissionsWithImplicitNamespace(self):
        """
        L{TagAPI.create} creates permissions for the newly created
        L{Namespace}s and L{Tag}s.
        """
        values = [(u'username/namespace/tag', u'A description')]
        self.tags.create(values)

        result = self.store.find(
            NamespacePermission,
            NamespacePermission.namespaceID == Namespace.id,
            Namespace.path == u'username/namespace')
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

        self.assertDefaultPermissions(self.user, u'username/namespace/tag')

    def testDelete(self):
        """L{TagAPI.delete} removes L{Tag}s."""
        self.tags.create([(u'username/child', u'A description')])
        self.tags.delete([u'username/child'])
        self.assertIdentical(None, getTags(paths=[u'username/child']).one())

    def testDeleteDoesNotDeleteOtherTags(self):
        """
        L{TagAPI.delete} removes just the L{Tag} is is asked to and not any
        other tags.
        """
        self.tags.create([(u'username/child1', u'A description')])
        self.tags.create([(u'username/child2', u'A description')])
        self.tags.delete([u'username/child1'])
        tag = getTags(paths=[u'username/child2']).one()
        self.assertEqual(u'username/child2', tag.path)

    def testDeleteDoesNotDeleteOtherTagsWhenPassedAGenerator(self):
        """
        L{TagAPI.delete} removes just the L{Tag} is is asked to and not any
        other tags when it is passed a generator (as opposed to a C{list}).
        """
        self.tags.create([(u'username/child1', u'A description')])
        self.tags.create([(u'username/child2', u'A description')])
        self.tags.delete(name for name in [u'username/child1'])
        tag = getTags(paths=[u'username/child2']).one()
        self.assertEqual(u'username/child2', tag.path)

    def testDeleteRemovesDescription(self):
        """
        L{TagAPI.delete} removes the C{fluiddb/tags/description} values stored
        for deleted L{Tag}s.
        """
        values = [(u'username/tag', u'A description')]
        [(objectID, path)] = self.tags.create(values)
        self.tags.delete([u'username/tag'])
        result = TagValueAPI(self.user).get(
            objectIDs=[objectID], paths=[u'fluiddb/tags/description'])
        self.assertEqual({}, result)

    def testDeleteRemovesPath(self):
        """
        L{TagAPI.delete} removes the C{fluiddb/tags/path} values stored
        for deleted L{Tag}s.
        """
        values = [(u'username/tag', u'A description')]
        [(objectID, path)] = self.tags.create(values)
        self.tags.delete([u'username/tag'])
        result = TagValueAPI(self.user).get(
            objectIDs=[objectID], paths=[u'fluiddb/tags/path'])
        self.assertEqual({}, result)

    def testDeleteKeepsTheAboutTag(self):
        """
        L{TagAPI.delete} keeps the C{fluiddb/about} tag value for the deleted
        tag.
        """
        values = [(u'username/tag', u'A tag description')]
        [(objectID, path)] = self.tags.create(values)
        self.tags.delete([u'username/tag'])
        tag = getTags(paths=[u'fluiddb/about']).one()
        value = getTagValues([(objectID, tag.id)]).one()
        self.assertEqual(u'Object for the attribute username/tag', value.value)

    def testDeleteRemovesPermissions(self):
        """L{TagAPI.delete} removes permissions when L{Tag}s are deleted."""
        values = [(u'username/tag', u'A description')]
        self.tags.create(values)

        self.tags.delete([u'username/tag'])
        result = self.store.find(TagPermission,
                                 TagPermission.tagID == Tag.id,
                                 Tag.path == u'username/tag')
        self.assertTrue(result.is_empty())

    def testDeleteReturnsObjectIDs(self):
        """
        L{TagAPI.delete} returns a list of C{(objectID, Tag.path)} 2-tuples
        for L{Tag}s that were removed.
        """
        result1 = self.tags.create([(u'username/child', u'A description')])
        result2 = self.tags.delete([u'username/child'])
        self.assertEqual(result1, result2)

    def testDeleteUpdatesObjectsTagged(self):
        """
        L{TagAPI.delete} updates the objects previously tagged with the given
        paths.
        """
        objectID = uuid4()
        self.tags.create([(u'username/child', u'A description')])
        TagValueAPI(self.user).set({objectID: {u'username/child': 64}})
        getDirtyObjects([objectID]).remove()
        self.tags.delete([u'username/child'])
        self.assertIn(objectID, getDirtyObjects().values(DirtyObject.objectID))

    def testGetWithoutData(self):
        """
        L{TagAPI.get} raises a L{FeatureError} if no L{Tag.path}s are
        provided.
        """
        self.assertRaises(FeatureError, self.tags.get, [])

    def testGet(self):
        """L{TagAPI.get} returns L{Tag}s that match the specified paths."""
        createTag(self.user, self.user.namespace, u'ignored')
        tag = createTag(self.user, self.user.namespace, u'tag')
        self.assertEqual({u'username/tag': {'id': tag.objectID}},
                         self.tags.get([u'username/tag']))

    def testGetWithDescriptions(self):
        """
        L{TagAPI.get} can optionally include L{Tag.description}s in the
        result.
        """
        descriptionTag = self.system.tags[u'fluiddb/tags/description']
        tag = createTag(self.user, self.user.namespace, u'tag')
        createTagValue(self.user.id, descriptionTag.id, tag.objectID, u'A tag')
        result = self.tags.get([u'username/tag'], withDescriptions=True)
        self.assertEqual(tag.objectID, result[u'username/tag']['id'])
        self.assertEqual(u'A tag', result[u'username/tag']['description'])

    def testGetWithNonexistentDescriptions(self):
        """
        L{TagAPI.get} returns an empty string as description if the
        C{fluiddb/tags/description} tag is not present on the tag object.
        """
        tag = createTag(self.user, self.user.namespace, u'tag')
        result = self.tags.get([u'username/tag'], withDescriptions=True)
        self.assertEqual(tag.objectID, result[u'username/tag']['id'])
        self.assertEqual(u'', result[u'username/tag']['description'])

    def testSet(self):
        """L{TagAPI.set} updates the description for the specified L{Tag}s."""
        descriptionTag = self.system.tags[u'fluiddb/tags/description']
        tag = createTag(self.user, self.user.namespace, u'tag')
        createTagPermission(tag)
        self.tags.set({u'username/tag': u'A fancy new description.'})
        result = getTagValues([(tag.objectID, descriptionTag.id)])
        description = result.one()
        self.assertEqual(u'A fancy new description.', description.value)

    def testSetReturnsUpdateResultWithObjectIDAndPathPairs(self):
        """
        L{TagAPI.delete} returns a list of C{(objectID, Tag.path)} 2-tuples
        for L{Tag}s that were updated.
        """
        result1 = self.tags.create([(u'username/tag', u'A description')])
        result2 = self.tags.set({u'username/tag': u'A fancy new description.'})
        self.assertEqual(result1, result2)


class TagAPITest(TagAPITestMixin, FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(TagAPITest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = PermissionAPI(self.user)
        self.tags = TagAPI(self.user)
