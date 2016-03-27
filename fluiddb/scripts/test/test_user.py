from fluiddb.data.system import createSystemData
from fluiddb.data.user import Role
from fluiddb.scripts.user import createUser, deleteUser
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import DatabaseResource, ConfigResource
from fluiddb.model.user import getUser
from fluiddb.model.value import TagValueAPI


class CreateUserTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource()),
                 ('config', ConfigResource())]

    def testCreateAnonUser(self):
        """The L{createUser} command can create a new anonymous User."""
        createSystemData()
        [(objectID, _)] = createUser(u'test', 'pwd', u'Name',
                                     u'test@example.com', Role.ANONYMOUS)
        user = getUser(u'test')
        self.assertEqual(u'test', user.username)
        self.assertEqual(u'Name', user.fullname)
        self.assertEqual(u'test@example.com', user.email)
        self.assertEqual(Role.ANONYMOUS, user.role)
        result = TagValueAPI(user).get([objectID], [u'fluiddb/users/role'])
        self.assertEqual(u'ANONYMOUS',
                         result[objectID][u'fluiddb/users/role'].value)

    def testCreateRegularUser(self):
        """The L{createUser} command can create a new regular User."""
        createSystemData()
        [(objectID, _)] = createUser(u'test', 'pwd', u'Name',
                                     u'test@example.com', Role.USER)
        user = getUser(u'test')
        self.assertEqual(u'test', user.username)
        self.assertEqual(u'Name', user.fullname)
        self.assertEqual(u'test@example.com', user.email)
        result = TagValueAPI(user).get([objectID], [u'fluiddb/users/role'])
        self.assertEqual(u'USER',
                         result[objectID][u'fluiddb/users/role'].value)

    def testCreateUserManagerUser(self):
        """The L{createUser} command can create a new user manager User."""
        createSystemData()
        [(objectID, _)] = createUser(u'test', 'pwd', u'Name',
                                     u'test@example.com', Role.USER_MANAGER)
        user = getUser(u'test')
        self.assertEqual(u'test', user.username)
        self.assertEqual(u'Name', user.fullname)
        self.assertEqual(u'test@example.com', user.email)
        self.assertEqual(Role.USER_MANAGER, user.role)
        result = TagValueAPI(user).get([objectID], [u'fluiddb/users/role'])
        self.assertEqual(u'USER_MANAGER',
                         result[objectID][u'fluiddb/users/role'].value)

    def testCreateSuperuserUser(self):
        """The L{createUser} command can create a new superuser User."""
        createSystemData()
        [(objectID, _)] = createUser(u'test', 'pwd', u'Name',
                                     u'test@example.com', Role.SUPERUSER)
        user = getUser(u'test')
        self.assertEqual(u'test', user.username)
        self.assertEqual(u'Name', user.fullname)
        self.assertEqual(u'test@example.com', user.email)
        self.assertEqual(Role.SUPERUSER, user.role)
        result = TagValueAPI(user).get([objectID], [u'fluiddb/users/role'])
        self.assertEqual(u'SUPERUSER',
                         result[objectID][u'fluiddb/users/role'].value)


class DeleteUserTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource()),
                 ('config', ConfigResource())]

    def testDeleteUser(self):
        """The L{deleteUser} command deletes a Fluidinfo user."""
        createSystemData()
        createUser(u'test', 'pwd', u'Name', u'test@example.com', Role.USER)
        deleteUser(u'test')
        user = getUser(u'test')
        self.assertIdentical(None, user)
