import os
import unittest

from fom.session import Fluid


class TestPUT(unittest.TestCase):

    def setUp(self):
        endpoint = os.environ.get('FLUIDDB_ENDPOINT', 'http://localhost:9000')
        self.username = os.environ.get('FLUIDDB_ADMIN_USERNAME', 'fluiddb')
        password = os.environ.get('FLUIDDB_ADMIN_PASSWORD', 'secret')
        self.fluiddb = Fluid(endpoint)
        self.fluiddb.login(self.username, password)
        self.fluiddb.bind()

    def testChangesTakeEffect(self):
        """
        When PUTting updated values for a user's password, email or full-name
        make sure the changes propogate to the database for later retrieval.
        """
        newName = 'Kathpakalaxmikanthan'
        body = {'name': newName}
        response = self.fluiddb.db('PUT', ['users', 'testuser1'], body)
        userID = self.fluiddb.users['testuser1'].get().value['id']
        response = self.fluiddb.objects[userID]['fluiddb/users/name'].get()
        self.assertEqual(newName, response.value)
