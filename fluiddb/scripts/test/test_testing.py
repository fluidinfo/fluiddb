from fluiddb.data.system import createSystemData
from fluiddb.model.namespace import NamespaceAPI
from fluiddb.model.tag import TagAPI
from fluiddb.model.user import UserAPI
from fluiddb.scripts.testing import prepareForTesting, removeTestingData
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import ConfigResource, DatabaseResource


class PrepareForTestingTest(FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(PrepareForTestingTest, self).setUp()
        system = createSystemData()
        self.admin = system.users[u'fluiddb']

    def testPrepareForTestingCreatesUsers(self):
        """
        L{prepareForTesting} creates all the necessary testing L{User}s.
        """
        prepareForTesting()

        usernames = [u'testuser1', u'testuser2']
        users = UserAPI().get(usernames)
        self.assertEquals(usernames, sorted(users.iterkeys()))

    def testPrepareForTestingCreatesNamespaces(self):
        """
        L{prepareForTesting} creates all the necessary testing L{Namespace}s.
        """
        prepareForTesting()

        paths = [u'fluiddb/testing/testing',
                 u'testuser1/testing/testing',
                 u'testuser2/testing/testing']
        namespaces = NamespaceAPI(self.admin).get(paths)
        self.assertEqual(paths, sorted(namespaces.iterkeys()))

    def testPrepareForTestingCreatesTags(self):
        """
        L{prepareForTesting} creates all the necessary testing L{Tag}s.
        """
        prepareForTesting()

        paths = [u'fluiddb/testing/test1',
                 u'fluiddb/testing/test2',
                 u'testuser1/testing/test1',
                 u'testuser1/testing/test2',
                 u'testuser2/testing/test1',
                 u'testuser2/testing/test2']
        tags = TagAPI(self.admin).get(paths)
        self.assertEqual(paths, sorted(tags.iterkeys()))


class RemoveTestingDataTest(FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(RemoveTestingDataTest, self).setUp()
        system = createSystemData()
        self.admin = system.users[u'fluiddb']

    def testRemoveTestingDataRemovesUsers(self):
        """L{removeTestingData} removes all the testing L{User}s."""
        prepareForTesting()
        removeTestingData()

        users = UserAPI().get([u'testuser1', u'testuser2'])
        self.assertEquals({}, users)

    def testRemoveTestingDataRemovesNamespaces(self):
        """L{removeTestingData} removes all the testing L{Namespace}s."""
        prepareForTesting()
        removeTestingData()

        paths = [u'fluiddb/testing/testing',
                 u'testuser1/testing/testing',
                 u'testuser2/testing/testing']
        namespaces = NamespaceAPI(self.admin).get(paths)
        self.assertEqual({}, namespaces)

    def testRemoveTestingDataRemovesCreatesTags(self):
        """L{removeTestingData} removes all the testing L{Tag}s."""
        prepareForTesting()
        removeTestingData()

        paths = [u'fluiddb/testing/test1',
                 u'fluiddb/testing/test2',
                 u'testuser1/testing/test1',
                 u'testuser1/testing/test2',
                 u'testuser2/testing/test1',
                 u'testuser2/testing/test2']
        tags = TagAPI(self.admin).get(paths)
        self.assertEqual({}, tags)

    def testRemoveTestingDataWithNonexistentData(self):
        """
        L{removeTestingData} doesn't remove anything it the testing data
        doesn't exist.
        """
        removeTestingData()

        paths = [u'fluiddb/testing/test1',
                 u'fluiddb/testing/test2',
                 u'testuser1/testing/test1',
                 u'testuser1/testing/test2',
                 u'testuser2/testing/test1',
                 u'testuser2/testing/test2']
        tags = TagAPI(self.admin).get(paths)
        self.assertEqual({}, tags)
        paths = [u'fluiddb/testing/testing',
                 u'testuser1/testing/testing',
                 u'testuser2/testing/testing']
        namespaces = NamespaceAPI(self.admin).get(paths)
        self.assertEqual({}, namespaces)
        users = UserAPI().get([u'testuser1', u'testuser2'])
        self.assertEquals({}, users)

    def testRemoveTestingDataWithPartialData(self):
        """
        L{removeTestingData} only tries to remove testing data that exists.
        """
        UserAPI().create([(u'testuser1', 'secret', u'Test user',
                           u'test@example.com')])
        NamespaceAPI(self.admin).delete([u'testuser1/private'])
        removeTestingData()
        users = UserAPI().get([u'testuser1', u'testuser2'])
        self.assertEquals({}, users)
