from fluiddb.data.system import createSystemData
from fluiddb.model.factory import APIFactory
from fluiddb.model.namespace import NamespaceAPI
from fluiddb.model.object import ObjectAPI
from fluiddb.model.permission import PermissionAPI, PermissionCheckerAPI
from fluiddb.model.recentactivity import RecentActivityAPI
from fluiddb.model.tag import TagAPI
from fluiddb.model.user import UserAPI, getUser
from fluiddb.model.value import TagValueAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import ConfigResource, DatabaseResource


class APIFactoryTest(FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(APIFactoryTest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        self.user = getUser(u'user')
        self.factory = APIFactory()

    def testUsers(self):
        """L{APIFactory.users} returns a usable L{UserAPI} instance."""
        self.assertIsInstance(self.factory.users(), UserAPI)

    def testObjects(self):
        """L{APIFactory.objects} returns a usable L{ObjectAPI} instance."""
        self.assertIsInstance(self.factory.objects(self.user), ObjectAPI)

    def testNamespaces(self):
        """
        L{APIFactory.namespaces} returns a usable L{NamespaceAPI} instance.
        """
        self.assertIsInstance(self.factory.namespaces(self.user), NamespaceAPI)

    def testTags(self):
        """L{APIFactory.tags} returns a usable L{TagAPI} instance."""
        self.assertIsInstance(self.factory.tags(self.user), TagAPI)

    def testTagValues(self):
        """L{APIFactory.tagValues} returns a usable L{TagValueAPI} instance."""
        self.assertIsInstance(self.factory.tagValues(self.user), TagValueAPI)

    def testPermissions(self):
        """
        L{APIFactory.permissions} returns a usable L{PermissionAPI} instance.
        """
        self.assertIsInstance(self.factory.permissions(self.user),
                              PermissionAPI)

    def testPermissionCheckers(self):
        """
        L{APIFactory.permissionCheckers} returns a usable
        L{PermissionCheckerAPI} instance.
        """
        self.assertIsInstance(self.factory.permissionCheckers(),
                              PermissionCheckerAPI)

    def testRecentActivity(self):
        """
        L{APIFactory.recentActivity} returns a usable L{RecentActivityAPI}
        instance.
        """
        self.assertIsInstance(self.factory.recentActivity(), RecentActivityAPI)
