from fluiddb.data.namespace import createNamespace, Namespace, getNamespaces
from fluiddb.data.permission import (
    createNamespacePermission, createTagPermission)
from fluiddb.data.system import createSystemData
from fluiddb.data.tag import createTag, Tag
from fluiddb.data.user import createUser, User, Role
from fluiddb.data.value import (
    createTagValue, getTagValues, createAboutTagValue)
from fluiddb.model.namespace import NamespaceAPI
from fluiddb.model.tag import TagAPI
from fluiddb.model.user import UserAPI, getUser
from fluiddb.model.value import TagValueAPI
from fluiddb.scripts.checker import (
    NamespaceIntegrityChecker, TagIntegrityChecker, UserIntegrityChecker,
    AboutTagValueIntegrityChecker, TagValueIntegrityChecker, checkIntegrity)
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    DatabaseResource, LoggingResource, ConfigResource)
from uuid import uuid4


class CheckIntegrityTest(FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('log', LoggingResource(format='%(message)s')),
                 ('store', DatabaseResource())]

    def testCheckIntegrityChecksErrorInAllRows(self):
        """
        L{checkIntegrity} should check for integrity errors in L{Namespace}s,
        L{Tag}s, L{User}s, L{AboutTagValue}s and L{TagValue}s.
        """
        createSystemData()
        [(userObjectID, _)] = UserAPI().create([(u'user', u'pass', u'Name',
                                                 u'test@example.com')])
        user = getUser(u'user')
        result = NamespaceAPI(user).create([(u'user/namespace',
                                             u'description')])
        [(namespaceObjectID, _)] = result
        [(tagObjectID, _)] = TagAPI(user).create([(u'user/tag',
                                                   u'description')])
        objectID1 = uuid4()
        objectID2 = uuid4()
        createAboutTagValue(objectID1, u'Bad about tag')
        TagValueAPI(user).set({objectID2: {u'fluiddb/about': 'about value'}})

        TagValueAPI(user).delete([(userObjectID,
                                   u'fluiddb/users/username')])
        TagValueAPI(user).delete([(namespaceObjectID,
                                   u'fluiddb/namespaces/path')])
        TagValueAPI(user).delete([(tagObjectID,
                                   u'fluiddb/tags/description')])
        checkIntegrity()

        self.assertEqual(
            "Integrity Error in namespace u'user/namespace': "
            'Path tag is missing.\n'
            "Integrity Error in tag u'user/tag': Description tag is missing.\n"
            "Integrity Error in user u'user': Username tag is missing.\n"
            "Integrity Error in object %s: AboutTagValue doesn't have an "
            'associated TagValue.\n'
            "Integrity Error in object %s: fluiddb/about TagValue doesn't "
            'have an associated AboutTagValue.\n' %
            (objectID1, objectID2),
            self.log.getvalue())

    def testCheckIntegrityGetsAllRowsUsingMultipleQueries(self):
        """
        L{checkIntegrity} should check all the rows of a given object using
        multiple queries if the C{maxRowsPerQuery} argument is smaller than the
        total number of rows for a given object.
        """
        createSystemData()
        UserAPI().create([(u'user', u'pass', u'Name',
                           u'test@example.com')])
        user = getUser(u'user')
        paths = [u'user/namespace%d' % i for i in xrange(10)]
        values = [(path, u'description') for path in paths]
        NamespaceAPI(user).create(values)
        namespaces = getNamespaces(paths=paths)
        values = [(namespace.objectID, u'fluiddb/namespaces/path')
                  for namespace in namespaces]
        TagValueAPI(user).delete(values)

        checkIntegrity(maxRowsPerQuery=2)

        error = 'Integrity Error in namespace %r: Path tag is missing.'
        expectedErrors = '\n'.join(error % path for path in paths) + '\n'
        self.assertEqual(expectedErrors, self.log.getvalue())


class NamespaceIntegrityCheckerTest(FluidinfoTestCase):

    resources = [('log', LoggingResource(format='%(message)s')),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(NamespaceIntegrityCheckerTest, self).setUp()
        system = createSystemData()
        self.user = createUser(u'user', u'pass', u'Name', u'test@example.com')
        self.superuser = system.users[u'fluiddb']
        self.anonymous = system.users[u'anon']
        self.parent = createNamespace(self.user, u'user', None)
        self.user.namespaceID = self.parent.id
        self.descriptionTag = system.tags['fluiddb/namespaces/description']
        self.pathTag = system.tags['fluiddb/namespaces/path']
        self.aboutTag = system.tags['fluiddb/about']
        self.checker = NamespaceIntegrityChecker()

    def testMissingAboutValue(self):
        """
        L{NamespaceIntegrityChecker.check} logs an error if the given
        L{Namespace} doesn't have a C{fluiddb/about} value.
        """
        test = createNamespace(self.user.id, u'user/test', self.parent.id)
        createNamespacePermission(test)
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for test tag')
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'user/test')
        self.checker.check([test])
        self.assertEqual(u"Integrity Error in namespace u'user/test': "
                         u'About tag is missing.\n',
                         self.log.getvalue())

    def testWrongAboutValue(self):
        """
        L{NamespaceIntegrityChecker.check} logs an error if the given
        L{Namespace} has a wrong C{fluiddb/about} value.
        """
        test = createNamespace(self.user.id, u'user/test', self.parent.id)
        createNamespacePermission(test)
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for test tag')
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'user/test')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       'Wrong about tag value')

        self.checker.check([test])
        self.assertEqual("Integrity Error in namespace u'user/test': "
                         'About tag is incorrect.\n',
                         self.log.getvalue())

    def testMissingPathTagValue(self):
        """
        L{NamespaceIntegrityChecker.check} logs an error if the given
        L{Namespace} doesn't have a C{fluiddb/namespaces/path} value.
        """
        test = createNamespace(self.user.id, u'user/test', self.parent.id)
        createNamespacePermission(test)
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for test tag')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       u'Object for the namespace %s' % test.path)

        self.checker.check([test])
        self.assertEqual("Integrity Error in namespace u'user/test': "
                         'Path tag is missing.\n',
                         self.log.getvalue())

    def testWrongPathTagValue(self):
        """
        L{NamespaceIntegrityChecker.check} logs an error if the given
        L{Namespace} has a wrong C{fluiddb/namespaces/path} value.
        """
        test = createNamespace(self.user.id, u'user/test', self.parent.id)
        createNamespacePermission(test)
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for test tag')
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'wrong/path')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       u'Object for the namespace %s' % test.path)

        self.checker.check([test])
        self.assertEqual("Integrity Error in namespace u'user/test': "
                         'Path tag is incorrect.\n',
                         self.log.getvalue())

    def testMissingDescriptionTagValue(self):
        """
        L{NamespaceIntegrityChecker.check} logs an error if the given
        L{Namespace} doesn't have C{fluiddb/namespaces/description} value.
        """
        test = createNamespace(self.user.id, u'user/test', self.parent.id)
        createNamespacePermission(test)
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'user/test')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       u'Object for the namespace %s' % test.path)

        self.checker.check([test])
        self.assertEqual("Integrity Error in namespace u'user/test': "
                         'Description tag is missing.\n',
                         self.log.getvalue())

    def testMissingPermissions(self):
        """
        L{NamespaceIntegrityChecker.check} logs an error if the given
        L{Namespace} doesn't have the required L{NamespacePermission} entries.
        """
        test = createNamespace(self.user.id, u'user/test', self.parent.id)
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for test tag')
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'user/test')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       u'Object for the namespace %s' % test.path)

        self.checker.check([test])
        self.assertEqual("Integrity Error in namespace u'user/test': "
                         'Permissions row is missing.\n',
                         self.log.getvalue())

    def testNonexistentUserInPermissionExceptions(self):
        """
        L{NamespaceIntegrityChecker.check} logs an error if a nonexistent user
        is in a permission exceptions list.
        """
        test = createNamespace(self.user.id, u'user/test', self.parent.id)
        permission = createNamespacePermission(test)
        permission.createExceptions = [-1]
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for test tag')
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'user/test')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       u'Object for the namespace %s' % test.path)

        self.checker.check([test])
        self.assertEqual("Integrity Error in namespace u'user/test': "
                         'Nonexistent user ID -1 in exceptions list for '
                         'CREATE_NAMESPACE permission.\n',
                         self.log.getvalue())

    def testSuperuserInPermissionExceptions(self):
        """
        L{NamespaceIntegrityChecker.check} logs an error if a superuser is in a
        permission exceptions list.
        """
        test = createNamespace(self.user.id, u'user/test', self.parent.id)
        permission = createNamespacePermission(test)
        permission.createExceptions = [self.user.id, self.superuser.id]
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for test tag')
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'user/test')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       u'Object for the namespace %s' % test.path)

        self.checker.check([test])
        self.assertEqual("Integrity Error in namespace u'user/test': "
                         'A superuser is in the exceptions list for '
                         'CREATE_NAMESPACE permission.\n',
                         self.log.getvalue())

    def testAnonymousUserInPermissionExceptions(self):
        """
        L{NamespaceIntegrityChecker.check} logs an error if an anonymous user
        is in a permission exceptions list for a non-allowed operation.
        """
        test = createNamespace(self.user.id, u'user/test', self.parent.id)
        permission = createNamespacePermission(test)
        permission.createExceptions = [self.user.id, self.anonymous.id]
        permission.listExceptions = [self.user.id, self.anonymous.id]
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for test tag')
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'user/test')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       u'Object for the namespace %s' % test.path)

        self.checker.check([test])
        self.assertEqual("Integrity Error in namespace u'user/test': "
                         'An anonymous user is in the exceptions list for '
                         'CREATE_NAMESPACE permission.\n',
                         self.log.getvalue())

    def testNotAssociatedParent(self):
        """
        L{NamespaceIntegrityChecker.check} logs an error if the given
        L{Namespace} doesn't have an associated parent when it's path suggests
        one.
        """
        test = createNamespace(self.user.id, u'user/test', None)
        createNamespacePermission(test)
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for test tag')
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'user/test')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       u'Object for the namespace %s' % test.path)

        self.checker.check([test])
        self.assertEqual("Integrity Error in namespace u'user/test': "
                         'Parent ID is not specified.\n',
                         self.log.getvalue())

    def testWrongParent(self):
        """
        L{NamespaceIntegrityChecker.check} logs an error if the given
        L{Namespace} has a wrong associated parent.
        """
        parent = createNamespace(self.user.id, u'parent', None)
        test = createNamespace(self.user.id, u'user/test', parent.id)
        createNamespacePermission(test)
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for test tag')
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'user/test')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       u'Object for the namespace %s' % test.path)

        self.checker.check([test])
        self.assertEqual("Integrity Error in namespace u'user/test': "
                         'Assigned parent is incorrect.\n',
                         self.log.getvalue())

    def testInvalidPaths(self):
        """
        L{NamespaceIntegrityChecker.check} logs an error if the given
        L{Namespace} has a wrong path.
        """
        test = Namespace(self.user, u'user/$bad!', u'$bad!', self.parent.id)
        createNamespacePermission(test)
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for $bad! tag')
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'user/$bad!')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       u'Object for the namespace %s' % test.path)

        self.checker.check([test])
        self.assertEqual("Integrity Error in namespace u'user/$bad!': "
                         'Invalid path.\n',
                         self.log.getvalue())


class TagIntegrityCheckerTest(FluidinfoTestCase):

    resources = [('log', LoggingResource(format='%(message)s')),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(TagIntegrityCheckerTest, self).setUp()
        system = createSystemData()
        self.user = createUser(u'user', u'pass', u'Name', u'test@example.com')
        self.superuser = system.users[u'fluiddb']
        self.anonymous = system.users[u'anon']
        self.parent = createNamespace(self.user, u'user', None)
        self.user.namespaceID = self.parent.id
        self.descriptionTag = system.tags['fluiddb/tags/description']
        self.pathTag = system.tags['fluiddb/tags/path']
        self.aboutTag = system.tags['fluiddb/about']
        self.checker = TagIntegrityChecker()

    def testMissingAboutValue(self):
        """
        L{TagIntegrityChecker.check} logs an error if the given L{Tag} doesn't
        have a C{fluiddb/about} value.
        """
        test = createTag(self.user, self.parent, u'test')
        createTagPermission(test)
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for test tag')
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'user/test')

        self.checker.check([test])
        self.assertEqual("Integrity Error in tag u'user/test': "
                         'About tag is missing.\n',
                         self.log.getvalue())

    def testWrongAboutValue(self):
        """
        L{TagIntegrityChecker.check} logs an error if the given L{Tag} has a
        wrong C{fluiddb/about} value.
        """
        test = createTag(self.user, self.parent, u'test')
        createTagPermission(test)
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for test tag')
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'user/test')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       'Wrong about tag value')

        self.checker.check([test])
        self.assertEqual("Integrity Error in tag u'user/test': "
                         'About tag is incorrect.\n',
                         self.log.getvalue())

    def testMissingPathTagValue(self):
        """
        L{TagIntegrityChecker.check} logs an error if the given L{Tag} doesn't
        have a C{fluiddb/tags/path} value.
        """
        test = createTag(self.user, self.parent, u'test')
        createTagPermission(test)
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for test tag')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       u'Object for the attribute %s' % test.path)

        self.checker.check([test])
        self.assertEqual("Integrity Error in tag u'user/test': "
                         'Path tag is missing.\n',
                         self.log.getvalue())

    def testWrongPathTagValue(self):
        """
        L{TagIntegrityChecker.check} logs an error if the given L{Tag} has a
        wrong C{fluiddb/tags/path} value.
        """
        test = createTag(self.user, self.parent, u'test')
        createTagPermission(test)
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for test tag')
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'wrong/path')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       u'Object for the attribute %s' % test.path)

        self.checker.check([test])
        self.assertEqual("Integrity Error in tag u'user/test': "
                         'Path tag is incorrect.\n',
                         self.log.getvalue())

    def testMissingDescriptionTagValue(self):
        """
        L{TagIntegrityChecker.check} logs an error if the given L{Tag} doesn't
        have C{fluiddb/tags/description} value.
        """
        test = createTag(self.user, self.parent, u'test')
        createTagPermission(test)
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'user/test')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       u'Object for the attribute %s' % test.path)

        self.checker.check([test])
        self.assertEqual("Integrity Error in tag u'user/test': "
                         'Description tag is missing.\n',
                         self.log.getvalue())

    def testMissingPermissions(self):
        """
        L{TagIntegrityChecker.check} logs an error if the given L{Tag} doesn't
        have the required L{TagPermission}.
        """
        test = createTag(self.user, self.parent, u'test')
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for test tag')
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'user/test')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       u'Object for the attribute %s' % test.path)

        self.checker.check([test])
        self.assertEqual("Integrity Error in tag u'user/test': "
                         'Permissions row is missing.\n',
                         self.log.getvalue())

    def testNonexistentUserInPermissionExceptions(self):
        """
        L{TagIntegrityChecker.check} logs an error if a nonexistent user is in
        a permission exceptions list.
        """
        test = createTag(self.user, self.parent, u'test')
        permission = createTagPermission(test)
        permission.updateExceptions = [-1]
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for test tag')
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'user/test')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       u'Object for the attribute %s' % test.path)

        self.checker.check([test])
        self.assertEqual("Integrity Error in tag u'user/test': "
                         'Nonexistent user ID -1 in exceptions list for '
                         'UPDATE_TAG permission.\n',
                         self.log.getvalue())

    def testSuperuserInPermissionExceptions(self):
        """
        L{TagIntegrityChecker.check} logs an error if a superuser is in a
        permission exceptions list.
        """
        test = createTag(self.user, self.parent, u'test')
        permission = createTagPermission(test)
        permission.updateExceptions = [self.user.id, self.superuser.id]
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for test tag')
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'user/test')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       u'Object for the attribute %s' % test.path)

        self.checker.check([test])
        self.assertEqual("Integrity Error in tag u'user/test': "
                         'A superuser is in the exceptions list for '
                         'UPDATE_TAG permission.\n',
                         self.log.getvalue())

    def testAnonymousUserInPermissionExceptions(self):
        """
        L{TagIntegrityChecker.check} logs an error if an anonymous user is in a
        permission exceptions list for a non-allowed operation.
        """
        test = createTag(self.user, self.parent, u'test')
        permission = createTagPermission(test)
        permission.updateExceptions = [self.user.id, self.anonymous.id]
        permission.readValueExceptions = [self.user.id, self.anonymous.id]
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for test tag')
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'user/test')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       u'Object for the attribute %s' % test.path)

        self.checker.check([test])
        self.assertEqual("Integrity Error in tag u'user/test': "
                         'An anonymous user is in the exceptions list for '
                         'UPDATE_TAG permission.\n',
                         self.log.getvalue())

    def testInvalidPaths(self):
        """
        L{TagIntegrityChecker.check} logs an error if the given L{Tag} has a
        wrong path.
        """
        test = Tag(self.user, self.parent, u'user/$bad!', u'$bad!')
        createTagPermission(test)
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for $bad! tag')
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'user/$bad!')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       u'Object for the attribute %s' % test.path)

        self.checker.check([test])
        self.assertEqual("Integrity Error in tag u'user/$bad!': "
                         'Invalid path.\n',
                         self.log.getvalue())

    def testWrongParent(self):
        """
        L{TagIntegrityChecker.check} logs an error if the given L{Tag} has a
        wrong associated parent.
        """
        test = Tag(self.user, self.parent, u'wrong/test', u'test')
        createTagPermission(test)
        createTagValue(self.user.id, self.descriptionTag.id, test.objectID,
                       u'Description for test tag')
        createTagValue(self.user.id, self.pathTag.id, test.objectID,
                       u'wrong/test')
        createTagValue(self.user.id, self.aboutTag.id, test.objectID,
                       u'Object for the attribute %s' % test.path)

        self.checker.check([test])
        self.assertEqual("Integrity Error in tag u'wrong/test': "
                         'Assigned parent is incorrect.\n',
                         self.log.getvalue())


class UserIntegrityCheckerTest(FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('log', LoggingResource(format='%(message)s')),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(UserIntegrityCheckerTest, self).setUp()
        system = createSystemData()
        self.superuser = system.users[u'fluiddb']
        self.anonymous = system.users[u'anon']
        self.aboutTag = system.tags['fluiddb/about']
        self.usernameTag = system.tags['fluiddb/users/username']
        self.nameTag = system.tags['fluiddb/users/name']
        self.emailTag = system.tags['fluiddb/users/email']
        self.checker = UserIntegrityChecker()

    def createTestUser(self, username):
        """
        Create a test L{User} using low level functions to avoid integrity
        checks made by high level ones.

        @param username: The username of the new L{User}.
        @return: A L{User} instance.
        """
        user = User(username, 'hash', u'Name', u'test@example.com', Role.USER)
        namespace = Namespace(user, username, username)
        self.store.add(user)
        self.store.add(namespace)
        user.namespaceID = namespace.id
        createTagValue(user.id, self.usernameTag.id, user.objectID, username)
        createTagValue(user.id, self.nameTag.id, user.objectID, u'Name')
        createTagValue(user.id, self.emailTag.id, user.objectID,
                       u'test@example.com')
        createTagValue(user.id, self.aboutTag.id, user.objectID,
                       u'@%s' % username)
        return user

    def testMissingAboutValue(self):
        """
        L{UserIntegrityChecker.check} logs an error if the given L{User}
        doesn't have a C{fluiddb/about} value.
        """
        user = self.createTestUser(u'user')
        getTagValues([(user.objectID, self.aboutTag.id)]).remove()
        self.checker.check([user])
        self.assertEqual("Integrity Error in user u'user': "
                         'About tag is missing.\n',
                         self.log.getvalue())

    def testWrongAboutValue(self):
        """
        L{UserIntegrityChecker.check} logs an error if the given L{User}
        has a wrong C{fluiddb/about} value.
        """
        user = self.createTestUser(u'user')
        about = getTagValues([(user.objectID, self.aboutTag.id)]).one()
        about.value = u'Wrong about value.'
        self.checker.check([user])
        self.assertEqual("Integrity Error in user u'user': "
                         'About tag is incorrect.\n',
                         self.log.getvalue())

    def testMissingUsernameValue(self):
        """
        L{UserIntegrityChecker.check} logs an error if the given L{User}
        doesn't have a C{fluiddb/users/username} value.
        """
        user = self.createTestUser(u'user')
        getTagValues([(user.objectID, self.usernameTag.id)]).remove()
        self.checker.check([user])
        self.assertEqual("Integrity Error in user u'user': "
                         'Username tag is missing.\n',
                         self.log.getvalue())

    def testWrongUsernameValue(self):
        """
        L{UserIntegrityChecker.check} logs an error if the given L{User}
        has a wrong C{fluiddb/users/username} value.
        """
        user = self.createTestUser(u'user')
        username = getTagValues([(user.objectID, self.usernameTag.id)]).one()
        username.value = u'wrongusername'
        self.checker.check([user])
        self.assertEqual("Integrity Error in user u'user': "
                         'Username tag is incorrect.\n',
                         self.log.getvalue())

    def testMissingNameValue(self):
        """
        L{UserIntegrityChecker.check} logs an error if the given L{User}
        doesn't have a C{fluiddb/users/name} value.
        """
        user = self.createTestUser(u'user')
        getTagValues([(user.objectID, self.nameTag.id)]).remove()
        self.checker.check([user])
        self.assertEqual("Integrity Error in user u'user': "
                         'Name tag is missing.\n',
                         self.log.getvalue())

    def testWrongNameValue(self):
        """
        L{UserIntegrityChecker.check} logs an error if the given L{User}
        has a wrong C{fluiddb/users/name} value.
        """
        user = self.createTestUser(u'user')
        name = getTagValues([(user.objectID, self.nameTag.id)]).one()
        name.value = u'Wrong Name'
        self.checker.check([user])
        self.assertEqual("Integrity Error in user u'user': "
                         'Name tag is incorrect.\n',
                         self.log.getvalue())

    def testMissingEmailValue(self):
        """
        L{UserIntegrityChecker.check} logs an error if the given L{User}
        doesn't have a C{fluiddb/users/email} value.
        """
        user = self.createTestUser(u'user')
        getTagValues([(user.objectID, self.emailTag.id)]).remove()
        self.checker.check([user])
        self.assertEqual("Integrity Error in user u'user': "
                         'Email tag is missing.\n',
                         self.log.getvalue())

    def testWrongEmailValue(self):
        """
        L{UserIntegrityChecker.check} logs an error if the given L{User}
        has a wrong C{fluiddb/users/email} value.
        """
        user = self.createTestUser(u'user')
        email = getTagValues([(user.objectID, self.emailTag.id)]).one()
        email.value = u'wrong@example.com'
        self.checker.check([user])
        self.assertEqual("Integrity Error in user u'user': "
                         'Email tag is incorrect.\n',
                         self.log.getvalue())

    def testMissingNamespace(self):
        """
        L{UserIntegrityChecker.check} logs an error if the given L{User}
        doesn't have a L{Namespace} with the same name.
        """
        user = self.createTestUser(u'user')
        getNamespaces(paths=[u'user']).remove()
        self.checker.check([user])
        self.assertEqual("Integrity Error in user u'user': "
                         'Root namespace is missing.\n',
                         self.log.getvalue())

    def testWrongNamespace(self):
        """
        L{UserIntegrityChecker.check} logs an error if the given L{User}
        have a wrong associated L{Namespace}.
        """
        user = self.createTestUser(u'user')
        user.namespaceID = getNamespaces(paths=[u'fluiddb']).one().id
        self.checker.check([user])
        self.assertEqual("Integrity Error in user u'user': "
                         'Assigned namespace is incorrect.\n',
                         self.log.getvalue())

    def testInvalidUsername(self):
        """
        L{UserIntegrityChecker.check} logs an error if the given L{User}
        have a wrong associated L{Namespace}.
        """
        user = self.createTestUser(u'!wrong$')
        self.checker.check([user])
        self.assertEqual("Integrity Error in user u'!wrong$': "
                         'Invalid username.\n',
                         self.log.getvalue())


class AboutTagValueIntegrityCheckerTest(FluidinfoTestCase):

    resources = [('log', LoggingResource(format='%(message)s')),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(AboutTagValueIntegrityCheckerTest, self).setUp()
        system = createSystemData()
        self.aboutTag = system.tags['fluiddb/about']
        self.checker = AboutTagValueIntegrityChecker()
        self.superuser = system.users[u'fluiddb']

    def testAboutTagValueWithoutValue(self):
        """
        L{AboutTagValueIntegrityChecker.check} logs an error if the given
        L{AboutTagValue} doesn't have an associated L{TagValue}.
        """
        object1 = uuid4()
        object2 = uuid4()
        aboutTagValue1 = createAboutTagValue(object1, u'Test object 1')
        aboutTagValue2 = createAboutTagValue(object2, u'Test object 2')
        createTagValue(self.superuser.id, self.aboutTag.id, object2,
                       u'Test object 2')

        self.checker.check([aboutTagValue1, aboutTagValue2])
        self.assertEqual('Integrity Error in object %s: '
                         "AboutTagValue doesn't have an associated TagValue.\n"
                         % object1,
                         self.log.getvalue())

    def testAboutTagValueWithWrongValue(self):
        """
        L{AboutTagValueIntegrityChecker.check} logs an error if the given
        L{AboutTagValue} and its L{TagValue} dont match.
        """
        object1 = uuid4()
        object2 = uuid4()
        aboutTagValue1 = createAboutTagValue(object1, u'Test object 1')
        createTagValue(self.superuser.id, self.aboutTag.id, object1,
                       u'Wrong tag value')
        aboutTagValue2 = createAboutTagValue(object2, u'Test object 2')
        createTagValue(self.superuser.id, self.aboutTag.id, object2,
                       u'Test object 2')

        self.checker.check([aboutTagValue1, aboutTagValue2])
        self.assertEqual('Integrity Error in object %s: '
                         "AboutTagValue doesn't match its TagValue.\n"
                         % object1,
                         self.log.getvalue())


class TagValueIntegrityCheckerTest(FluidinfoTestCase):

    resources = [('log', LoggingResource(format='%(message)s')),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(TagValueIntegrityCheckerTest, self).setUp()
        self.system = createSystemData()
        self.user = createUser(u'user', u'pass', u'Name', u'test@example.com')
        self.parent = createNamespace(self.user, u'user', None)
        self.user.namespaceID = self.parent.id
        self.checker = TagValueIntegrityChecker()
        self.superuser = self.system.users[u'fluiddb']

    def testAboutValueWithoutAboutTagValue(self):
        """
        L{TagValueIntegrityChecker.check} logs an error if a given L{TagValue}
        for fluiddb/about doesn't have an associated L{AboutTagValue} row.
        """
        tag = self.system.tags[u'fluiddb/about']
        tagValue1 = createTagValue(self.superuser.id, tag.id, uuid4(),
                                   u'Test object 1')
        tagValue2 = createTagValue(self.superuser.id, tag.id, uuid4(),
                                   u'Test object 2')
        createAboutTagValue(tagValue2.objectID, u'Test object 2')

        self.checker.check([tagValue1, tagValue2])
        self.assertEqual('Integrity Error in object %s: '
                         "fluiddb/about TagValue doesn't have an associated "
                         'AboutTagValue.\n' % tagValue1.objectID,
                         self.log.getvalue())

    def testNamespacePathValueWithoutNamespace(self):
        """
        L{TagValueIntegrityChecker.check} logs an error if a given L{TagValue}
        for fluiddb/namespaces/path doesn't have an associated L{Namespace}
        row.
        """
        tag = self.system.tags[u'fluiddb/namespaces/path']
        tagValue1 = createTagValue(self.superuser.id, tag.id, uuid4(),
                                   u'missing/namespace')
        namespace = createNamespace(self.user, u'user/namesace',
                                    self.user.namespaceID)
        tagValue2 = createTagValue(self.superuser.id, tag.id,
                                   namespace.objectID, u'user/namespace')

        self.checker.check([tagValue1, tagValue2])
        self.assertEqual('Integrity Error in object %s: '
                         "fluiddb/namespaces/path TagValue doesn't have an "
                         'associated Namespace.\n' % tagValue1.objectID,
                         self.log.getvalue())

    def testNamespaceDescriptionValueWithoutNamespace(self):
        """
        L{TagValueIntegrityChecker.check} logs an error if a given L{TagValue}
        for fluiddb/namespaces/description doesn't have an associated
        L{Namespace} row.
        """
        tag = self.system.tags[u'fluiddb/namespaces/description']
        tagValue1 = createTagValue(self.superuser.id, tag.id, uuid4(),
                                   u'Lonely Description')
        namespace = createNamespace(self.user, u'user/namesace',
                                    self.user.namespaceID)
        tagValue2 = createTagValue(self.superuser.id, tag.id,
                                   namespace.objectID, u'Description')

        self.checker.check([tagValue1, tagValue2])
        self.assertEqual('Integrity Error in object %s: '
                         "fluiddb/namespaces/description TagValue doesn't have"
                         ' an associated Namespace.\n' % tagValue1.objectID,
                         self.log.getvalue())

    def testTagPathValueWithoutNamespace(self):
        """
        L{TagValueIntegrityChecker.check} logs an error if a given L{TagValue}
        for fluiddb/tags/path doesn't have an associated L{Tag} row.
        """
        tag = self.system.tags[u'fluiddb/tags/path']
        tagValue1 = createTagValue(self.superuser.id, tag.id, uuid4(),
                                   u'missing/tag')
        tag = createTag(self.user, self.parent, u'tag')
        tagValue2 = createTagValue(self.superuser.id, tag.id, tag.objectID,
                                   u'user/tag')

        self.checker.check([tagValue1, tagValue2])
        self.assertEqual('Integrity Error in object %s: '
                         "fluiddb/tags/path TagValue doesn't have an "
                         'associated Tag.\n' % tagValue1.objectID,
                         self.log.getvalue())

    def testTagDescriptionValueWithoutNamespace(self):
        """
        L{TagValueIntegrityChecker.check} logs an error if a given L{TagValue}
        for fluiddb/tags/description doesn't have an associated L{Tag} row.
        """
        tag = self.system.tags[u'fluiddb/tags/description']
        tagValue1 = createTagValue(self.superuser.id, tag.id, uuid4(),
                                   u'Lonely Description')
        tag = createTag(self.user, self.parent, u'tag')
        tagValue2 = createTagValue(self.superuser.id, tag.id, tag.objectID,
                                   u'Description')

        self.checker.check([tagValue1, tagValue2])
        self.assertEqual('Integrity Error in object %s: '
                         "fluiddb/tags/description TagValue doesn't have"
                         ' an associated Tag.\n' % tagValue1.objectID,
                         self.log.getvalue())

    def testUsernameValueWithoutUser(self):
        """
        L{TagValueIntegrityChecker.check} logs an error if a given L{TagValue}
        for fluiddb/users/username doesn't have an associated L{User} row.
        """
        tag = self.system.tags[u'fluiddb/users/username']
        tagValue1 = createTagValue(self.superuser.id, tag.id, uuid4(),
                                   u'missing_user')
        tagValue2 = getTagValues([(self.superuser.objectID, tag.id)]).one()

        self.checker.check([tagValue1, tagValue2])
        self.assertEqual('Integrity Error in object %s: '
                         "fluiddb/users/username TagValue doesn't have "
                         'an associated User.\n' % tagValue1.objectID,
                         self.log.getvalue())

    def testNameValueWithoutUser(self):
        """
        L{TagValueIntegrityChecker.check} logs an error if a given L{TagValue}
        for fluiddb/users/name doesn't have an associated L{User} row.
        """
        tag = self.system.tags[u'fluiddb/users/name']
        tagValue1 = createTagValue(self.superuser.id, tag.id, uuid4(),
                                   u'Missing User')
        tagValue2 = getTagValues([(self.superuser.objectID, tag.id)]).one()

        self.checker.check([tagValue1, tagValue2])
        self.assertEqual('Integrity Error in object %s: '
                         "fluiddb/users/name TagValue doesn't have "
                         'an associated User.\n' % tagValue1.objectID,
                         self.log.getvalue())

    def testEmailValueWithoutUser(self):
        """
        L{TagValueIntegrityChecker.check} logs an error if a given L{TagValue}
        for fluiddb/users/email doesn't have an associated L{User} row.
        """
        tag = self.system.tags[u'fluiddb/users/email']
        tagValue1 = createTagValue(self.superuser.id, tag.id, uuid4(),
                                   u'missing@example.com')
        tagValue2 = getTagValues([(self.superuser.objectID, tag.id)]).one()

        self.checker.check([tagValue1, tagValue2])
        self.assertEqual('Integrity Error in object %s: '
                         "fluiddb/users/email TagValue doesn't have "
                         'an associated User.\n' % tagValue1.objectID,
                         self.log.getvalue())
