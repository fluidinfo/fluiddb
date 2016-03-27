from fluiddb.data.namespace import createNamespace
from fluiddb.data.path import getParentPath, getPathName
from fluiddb.data.permission import (
    Operation, Policy, createNamespacePermission, createTagPermission)
from fluiddb.data.tag import createTag
from fluiddb.data.user import Role, createUser
from fluiddb.data.value import createTagValue, createAboutTagValue


class SystemData(object):
    """System data required for Fluidinfo to operate properly.

    @ivar namespaces: A C{dict} mapping L{Namespace.path}s to L{Namespace}
        instances for the builtin namespaces.
    @ivar tags: A C{dict} mapping L{Tag.path}s to L{Tag} instances for the
        builtin tags.
    @ivar users: A C{dict} mapping L{User.name}s to L{User} instances for the
        builtin users.

    @param data: a C{dict} with the bootstrap data in the following format::

        {'users': [{'role': <role>,
                    'username': <username>,
                    'name': <fullname>,
                    'email': <email>,
                    'password': <password>}, ...],
         'namespaces': [{'path': <path>, 'description': <description>}, ...],
         'tags' : [{'path': <path>, 'description': <description>}, ...]}
    """

    def __init__(self, data):
        self._data = data

        self.users = {}
        self.namespaces = {}
        self.tags = {}

        self._createUsers()
        self._createNamespaces()
        self._createTags()
        self._createMetaData()

        self.superuser = self.users[u'fluiddb']
        self.anonymous = self.users[u'anon']
        self.paths = self.namespaces.keys() + self.tags.keys()

    def _createUsers(self):
        """Create L{User}s."""
        for userData in self._data['users']:
            user = createUser(userData['username'], userData['password'],
                              userData['name'], userData['email'],
                              userData['role'])
            self.users[user.username] = user

    def _createNamespaces(self):
        """Create L{Namespace}s."""
        superuser = self.users[u'fluiddb']
        for namespaceData in self._data['namespaces']:
            path = namespaceData['path']
            parentPath = getParentPath(path)
            parentNamespace = self.namespaces.get(parentPath, None)
            parentID = parentNamespace.id if parentNamespace else None
            namespace = createNamespace(superuser, path, parentID)
            self._createNamespacePermissions(namespace)
            self.namespaces[path] = namespace
            if path in self.users:
                self.users[path].namespaceID = namespace.id

    def _createNamespacePermissions(self, namespace):
        """Create L{NamespacePermission}s."""
        permission = createNamespacePermission(namespace)
        permission.set(Operation.CREATE_NAMESPACE, Policy.CLOSED, [])
        permission.set(Operation.UPDATE_NAMESPACE, Policy.CLOSED, [])
        permission.set(Operation.DELETE_NAMESPACE, Policy.CLOSED, [])
        permission.set(Operation.LIST_NAMESPACE, Policy.CLOSED, [])
        permission.set(Operation.CONTROL_NAMESPACE, Policy.CLOSED, [])

    def _createTags(self):
        """Create tags."""
        superuser = self.users[u'fluiddb']
        for tag in self._data['tags']:
            path = tag['path']
            parentPath = getParentPath(path)
            name = getPathName(path)
            parentNamespace = self.namespaces[parentPath]
            tagObject = createTag(superuser, parentNamespace, name)
            self._createTagPermissions(tagObject)
            self.tags[path] = tagObject

    def _createTagPermissions(self, tag):
        """Create L{TagPermission}s."""
        permission = createTagPermission(tag)
        permission.set(Operation.UPDATE_TAG, Policy.CLOSED, [])
        permission.set(Operation.DELETE_TAG, Policy.CLOSED, [])
        permission.set(Operation.CONTROL_TAG, Policy.CLOSED, [])
        permission.set(Operation.WRITE_TAG_VALUE, Policy.CLOSED, [])
        permission.set(Operation.READ_TAG_VALUE, Policy.OPEN, [])
        permission.set(Operation.DELETE_TAG_VALUE, Policy.CLOSED, [])
        permission.set(Operation.CONTROL_TAG_VALUE, Policy.CLOSED, [])

    def _createMetaData(self):
        """Create system data."""
        superuser = self.users[u'fluiddb']
        tags = self.tags
        for user in self._data['users']:
            userObjectID = self.users[user['username']].objectID
            aboutValue = u'@%s' % user['username']
            createAboutTagValue(userObjectID, aboutValue)
            createTagValue(superuser.id, tags[u'fluiddb/about'].id,
                           userObjectID, aboutValue)
            createTagValue(superuser.id, tags[u'fluiddb/users/username'].id,
                           userObjectID, user['username'])
            createTagValue(superuser.id, tags[u'fluiddb/users/name'].id,
                           userObjectID, user['name'])
            createTagValue(superuser.id, tags[u'fluiddb/users/email'].id,
                           userObjectID, user['email'])
            createTagValue(superuser.id, tags[u'fluiddb/users/role'].id,
                           userObjectID, str(user['role']))

        for namespace in self._data['namespaces']:
            namespaceObjectID = self.namespaces[namespace['path']].objectID
            aboutValue = u'Object for the namespace %s' % namespace['path']
            createAboutTagValue(namespaceObjectID, aboutValue)
            createTagValue(superuser.id, tags[u'fluiddb/about'].id,
                           namespaceObjectID, aboutValue)
            createTagValue(superuser.id, tags[u'fluiddb/namespaces/path'].id,
                           namespaceObjectID, namespace['path'])
            createTagValue(superuser.id,
                           tags[u'fluiddb/namespaces/description'].id,
                           namespaceObjectID, namespace['description'])

        for tag in self._data['tags']:
            tagObjectID = self.tags[tag['path']].objectID
            aboutValue = u'Object for the attribute %s' % tag['path']
            createAboutTagValue(tagObjectID, aboutValue)
            createTagValue(superuser.id, tags[u'fluiddb/about'].id,
                           tagObjectID, aboutValue)
            createTagValue(superuser.id, tags[u'fluiddb/tags/path'].id,
                           tagObjectID, tag['path'])
            createTagValue(superuser.id, tags[u'fluiddb/tags/description'].id,
                           tagObjectID, tag['description'])


DEFAULT_SYSTEM_DATA = {
    'users': [
        {
            'username': u'fluiddb',
            'name': u'FluidDB administrator',
            'email': u'fluidDB@example.com',
            'password': 'secret',
            'role': Role.SUPERUSER,
        },
        {
            'username': u'anon',
            'name': u'FluidDB anonymous user',
            'email': u'noreply@example.com',
            'password': '!',
            'role': Role.ANONYMOUS,
        }],

    'namespaces': [
        {
            'path': u'fluiddb',
            'description': u"FluidDB admin user's top-level namespace."
        },
        {
            'path': u'anon',
            'description': u"FluidDB anonymous user's top-level namespace."
        },
        {
            'path': u'fluiddb/users',
            'description': u'Holds tags that concern FluidDB users.'
        },
        {
            'path': u'fluiddb/namespaces',
            'description': u'Holds information about namespaces.'
        },
        {
            'path': u'fluiddb/tags',
            'description': u'Holds information about tags.'
        }],

    'tags': [
        {
            'path': u'fluiddb/about',
            'description': u'A description of what an object is about.'
        },
        {
            'path': u'fluiddb/users/username',
            'description': u"Holds FluidDB users' usernames."
        },
        {
            'path': u'fluiddb/users/name',
            'description': u"Holds FluidDB users' names."
        },
        {
            'path': u'fluiddb/users/email',
            'description': u"Holds FluidDB users' email addresses."
        },
        {
            'path': u'fluiddb/users/role',
            'description': u"Holds FluidDB users' role."
        },
        {
            'path': u'fluiddb/namespaces/path',
            'description': u'The path of a namespace.'
        },
        {
            'path': u'fluiddb/namespaces/description',
            'description': u'Describes a namespace.'
        },
        {
            'path': u'fluiddb/tags/path',
            'description': u'The path of a tag.'
        },
        {
            'path': u'fluiddb/tags/description',
            'description': u'Describes a tag.'
        },
    ]
}


def createSystemData():
    """Create system data.

    @return: A L{SystemData} instance with information about builtin L{User}s,
        L{Namespace}s and L{Tag}s.
    """
    return SystemData(DEFAULT_SYSTEM_DATA)
