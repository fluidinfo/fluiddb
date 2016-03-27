from storm.exceptions import IntegrityError

from fluiddb.data.exceptions import MalformedPathError
from fluiddb.data.namespace import createNamespace
from fluiddb.data.tag import createTag, Tag, getTags
from fluiddb.data.user import createUser
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import DatabaseResource


class CreateTagTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testCreateTag(self):
        """L{createTag} creates a new L{Tag}."""
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag = createTag(user, user.namespace, u'tag')
        self.assertIdentical(user, tag.creator)
        self.assertIdentical(user.namespace, tag.namespace)
        self.assertEqual(u'username/tag', tag.path)
        self.assertEqual(u'tag', tag.name)

    def testCreateTagWithMalformedPath(self):
        """
        L{createTag} raises a L{MalformedPathError} if an invalid path is
        provided.
        """
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        self.assertRaises(MalformedPathError, createTag, user, user.namespace,
                          u'')

    def testCreateTagAddsToStore(self):
        """L{createTag} adds the new L{Tag} to the main store."""
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag = createTag(user, user.namespace, u'tag')
        result = self.store.find(Tag, Tag.path == u'username/tag')
        self.assertIdentical(tag, result.one())


class GetTagsTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testGetTags(self):
        """L{getTags} returns all L{Tag}s in the database, by default."""
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag = createTag(user, user.namespace, u'name')
        self.assertEqual(tag, getTags().one())

    def testGetTagsWithPaths(self):
        """
        When L{Tag.path}s are provided L{getTags} returns matching L{Tag}s.
        """
        user = createUser(u'username', u'password', u'User',
                          u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag = createTag(user, user.namespace, u'name1')
        createTag(user, user.namespace, u'name2')
        result = getTags(paths=[u'username/name1'])
        self.assertIdentical(tag, result.one())


class TagSchemaTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testUniquePathConstraint(self):
        """
        An C{IntegrityError} is raised if a L{Tag} with a duplicate path is
        added to the database.
        """
        user = createUser(u'name', u'password', u'User', u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        self.store.add(Tag(user, user.namespace, u'name/tag', u'tag'))
        self.store.flush()
        self.store.add(Tag(user, user.namespace, u'name/tag', u'tag'))
        self.assertRaises(IntegrityError, self.store.flush)
        self.store.rollback()

    def testUniqueObjectIDConstraint(self):
        """
        An C{IntegrityError} is raised if a L{Tag} with a duplicate object ID
        is added to the database.
        """
        user = createUser(u'name', u'password', u'User', u'user@example.com')
        user.namespaceID = createNamespace(user, user.username, None).id
        tag1 = Tag(user, user.namespace, u'name/tag1', u'tag1')
        self.store.add(tag1)
        self.store.flush()
        tag2 = Tag(user, user.namespace, u'name/tag2', u'tag2')
        tag2.objectID = tag1.objectID
        self.store.add(tag2)
        self.assertRaises(IntegrityError, self.store.flush)
        self.store.rollback()
