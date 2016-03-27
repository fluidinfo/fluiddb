from fluiddb.data.namespace import Namespace
from fluiddb.data.permission import (
    Operation, Policy, getNamespacePermissions, getTagPermissions)
from fluiddb.data.system import createSystemData
from fluiddb.data.tag import Tag
from fluiddb.data.user import Role, User
from fluiddb.data.value import TagValue
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import DatabaseResource


class SystemDataTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def assertUser(self, username, name, email, role):
        """
        Check that a L{User} is properly created including its namespace and
        meta-tags C{fluiddb/users/*} and C{fluiddb/about}.
        """
        result = self.store.find(User,
                                 User.username == username,
                                 User.fullname == name,
                                 User.email == email,
                                 User.role == role)
        user = result.one()
        self.assertNotIdentical(None, user,
                                msg='User %r was not created.' % username)

        result = self.store.find(Namespace, Namespace.path == username)
        self.assertFalse(result.is_empty(),
                         msg='Namespace for user %r was not created.'
                         % username)

        result = self.store.find(TagValue,
                                 TagValue.tagID == Tag.id,
                                 Tag.path == u'fluiddb/about',
                                 TagValue.objectID == user.objectID)
        aboutValue = result.one()
        self.assertNotIdentical(None, aboutValue,
                                msg='About tag was not created for %r.'
                                % username)
        self.assertEqual(u'@%s' % username, aboutValue.value,
                         msg='About tag is not correct for %r.' % username)

        result = self.store.find(TagValue,
                                 TagValue.tagID == Tag.id,
                                 Tag.path == u'fluiddb/users/username',
                                 TagValue.objectID == user.objectID)
        value = result.one()
        self.assertNotIdentical(None, value,
                                msg='Username tag was not created for %r.'
                                % username)
        self.assertEqual(username, value.value,
                         msg='Username tag is not correct for %r.' % username)

        result = self.store.find(TagValue,
                                 TagValue.tagID == Tag.id,
                                 Tag.path == u'fluiddb/users/name',
                                 TagValue.objectID == user.objectID)
        value = result.one()
        self.assertNotIdentical(None, value,
                                msg='Name tag was not created for %r.'
                                % username)
        self.assertEqual(name, value.value,
                         msg='Name tag is not correct for %r.' % username)

        result = self.store.find(TagValue,
                                 TagValue.tagID == Tag.id,
                                 Tag.path == u'fluiddb/users/email',
                                 TagValue.objectID == user.objectID)
        value = result.one()
        self.assertNotIdentical(None, value,
                                msg='Email tag was not created for %r.'
                                % username)
        self.assertEqual(email, value.value,
                         msg='Email tag is not correct for %r.' % username)

        result = self.store.find(TagValue,
                                 TagValue.tagID == Tag.id,
                                 Tag.path == u'fluiddb/users/role',
                                 TagValue.objectID == user.objectID)
        value = result.one()
        self.assertNotIdentical(None, value,
                                msg='Role tag was not created for %r.'
                                % username)
        self.assertEqual(str(role), value.value,
                         msg='Role tag is not correct for %r.' % username)

    def assertNamespace(self, path, description):
        """
        Check that a L{Namespace} is created including its meta-tags
        C{fluiddb/namespaces/path}, C{fluiddb/namespaces/description} and
        C{fluiddb/about}. Additionally, check that the assigned permissions are
        correct.
        """
        result = self.store.find(Namespace, Namespace.path == path)
        namespace = result.one()
        self.assertNotIdentical(None, namespace,
                                msg='Namespace %r was not created.' % path)

        result = self.store.find(TagValue,
                                 TagValue.tagID == Tag.id,
                                 Tag.path == u'fluiddb/about',
                                 TagValue.objectID == namespace.objectID)
        aboutValue = result.one()
        self.assertNotIdentical(None, aboutValue,
                                msg='About tag was not created for %r.' % path)
        self.assertEqual(u'Object for the namespace %s' % path,
                         aboutValue.value,
                         msg='About tag is not correct for %r.' % path)

        result = self.store.find(TagValue,
                                 TagValue.tagID == Tag.id,
                                 Tag.path == u'fluiddb/namespaces/path',
                                 TagValue.objectID == namespace.objectID)
        pathValue = result.one()
        self.assertNotIdentical(None, pathValue,
                                msg='Path tag was not created for %r.' % path)
        self.assertEqual(path, pathValue.value,
                         msg='Path tag is not correct for %r.' % path)

        result = self.store.find(TagValue,
                                 TagValue.tagID == Tag.id,
                                 Tag.path == u'fluiddb/namespaces/description',
                                 TagValue.objectID == namespace.objectID)
        descriptionValue = result.one()
        self.assertNotIdentical(None, descriptionValue,
                                msg='Description tag was not created for %r.'
                                % path)
        self.assertEqual(description, descriptionValue.value,
                         msg='Description tag is not correct for %r.' % path)

        namespace, permission = getNamespacePermissions([path]).one()
        self.assertNotIdentical(None, permission.namespaceID)
        self.assertEqual(namespace.id, permission.namespaceID)
        self.assertEqual((Policy.CLOSED, []),
                         permission.get(Operation.CREATE_NAMESPACE))
        self.assertEqual((Policy.CLOSED, []),
                         permission.get(Operation.UPDATE_NAMESPACE))
        self.assertEqual((Policy.CLOSED, []),
                         permission.get(Operation.DELETE_NAMESPACE))
        self.assertEqual((Policy.CLOSED, []),
                         permission.get(Operation.LIST_NAMESPACE))
        self.assertEqual((Policy.CLOSED, []),
                         permission.get(Operation.CONTROL_NAMESPACE))

    def assertTag(self, path, description):
        """
        Check that a L{Tag} is created including its meta-tags
        C{fluiddb/tags/path}, C{fluiddb/tags/description} and C{fluiddb/about}.
        Additionally, check that the assigned permissions are correct.
        """
        result = self.store.find(Tag, Tag.path == path)
        tag = result.one()
        self.assertNotIdentical(None, tag,
                                msg='Tag %r was not created.' % path)

        result = self.store.find(TagValue,
                                 TagValue.tagID == Tag.id,
                                 Tag.path == u'fluiddb/about',
                                 TagValue.objectID == tag.objectID)
        aboutValue = result.one()
        self.assertNotIdentical(None, aboutValue,
                                msg='About tag was not created for %r.' % path)
        self.assertEqual(u'Object for the attribute %s' % path,
                         aboutValue.value,
                         msg='About tag is not correct for %r.' % path)

        result = self.store.find(TagValue,
                                 TagValue.tagID == Tag.id,
                                 Tag.path == u'fluiddb/tags/path',
                                 TagValue.objectID == tag.objectID)
        pathValue = result.one()
        self.assertNotIdentical(
            None, pathValue,
            msg='Path tag was not created for %r.' % path)
        self.assertEqual(path, pathValue.value,
                         msg='Path tag is not correct for %r.' % path)

        result = self.store.find(TagValue,
                                 TagValue.tagID == Tag.id,
                                 Tag.path == u'fluiddb/tags/description',
                                 TagValue.objectID == tag.objectID)
        descriptionValue = result.one()
        self.assertNotIdentical(
            None, descriptionValue,
            msg='Description tag was not created for %r.' % path)
        self.assertEqual(description, descriptionValue.value,
                         msg='Description tag is not correct for %r.' % path)

        tag, permission = getTagPermissions([path]).one()
        self.assertNotIdentical(None, permission.tagID)
        self.assertEqual(tag.id, permission.tagID)
        self.assertEqual((Policy.CLOSED, []),
                         permission.get(Operation.UPDATE_TAG))
        self.assertEqual((Policy.CLOSED, []),
                         permission.get(Operation.DELETE_TAG))
        self.assertEqual((Policy.CLOSED, []),
                         permission.get(Operation.CONTROL_TAG))
        self.assertEqual((Policy.CLOSED, []),
                         permission.get(Operation.WRITE_TAG_VALUE))
        self.assertEqual((Policy.OPEN, []),
                         permission.get(Operation.READ_TAG_VALUE))
        self.assertEqual((Policy.CLOSED, []),
                         permission.get(Operation.DELETE_TAG_VALUE))
        self.assertEqual((Policy.CLOSED, []),
                         permission.get(Operation.CONTROL_TAG_VALUE))

    def testCreateUsers(self):
        """L{createSystemData} creates all the system L{User}s needed."""
        createSystemData()
        self.assertUser(u'fluiddb', u'FluidDB administrator',
                        u'fluidDB@example.com', Role.SUPERUSER)
        self.assertUser(u'anon', u'FluidDB anonymous user',
                        u'noreply@example.com', Role.ANONYMOUS)

    def testCreateNamespaces(self):
        """L{createSystemData} creates all the system L{Namespace}s needed."""
        createSystemData()
        self.assertNamespace(u'fluiddb',
                             u"FluidDB admin user's top-level namespace.")
        self.assertNamespace(u'anon',
                             u"FluidDB anonymous user's top-level namespace.")
        self.assertNamespace(u'fluiddb/users',
                             u'Holds tags that concern FluidDB users.')
        self.assertNamespace(u'fluiddb/namespaces',
                             u'Holds information about namespaces.')
        self.assertNamespace(u'fluiddb/tags',
                             u'Holds information about tags.')

    def testCreateTags(self):
        """L{createSystemData} creates all the system L{Tag}s needed."""
        createSystemData()
        self.assertTag(u'fluiddb/users/username',
                       u"Holds FluidDB users' usernames.")
        self.assertTag(u'fluiddb/users/name',
                       u"Holds FluidDB users' names.")
        self.assertTag(u'fluiddb/users/email',
                       u"Holds FluidDB users' email addresses.")
        self.assertTag(u'fluiddb/namespaces/path',
                       u'The path of a namespace.')
        self.assertTag(u'fluiddb/namespaces/description',
                       u'Describes a namespace.')
        self.assertTag(u'fluiddb/tags/path',
                       u'The path of a tag.')
        self.assertTag(u'fluiddb/tags/description',
                       u'Describes a tag.')
