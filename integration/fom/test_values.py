import os
import unittest

from fom.session import Fluid


class TestGET(unittest.TestCase):

    def setUp(self):
        endpoint = os.environ.get('FLUIDDB_ENDPOINT', 'http://localhost:9000')
        username = os.environ.get('FLUIDDB_ADMIN_USERNAME', 'fluiddb')
        password = os.environ.get('FLUIDDB_ADMIN_PASSWORD', 'secret')
        self.fluiddb = Fluid(endpoint)
        self.fluiddb.login(username, password)

    def test_resultsStructure(self):
        """
        Verify the structure of the results object in the response of a
        GET request to /values.
        """

        # Create a new object.
        response = self.fluiddb.objects.post('about')
        objectId = response.value['id']

        path = 'fluiddb/testing/test1'
        value = 'value'

        try:
            # Add a new set tag to the object.
            self.fluiddb.objects[objectId][path].put(value)

            # Get the tag value using the values API.
            response = self.fluiddb.values.get('fluiddb/about = "about"',
                                               [path])
            self.assertTrue('results' in response.value)
            results = response.value['results']
            self.assertTrue('id' in results)
            ids = results['id']
            self.assertTrue(objectId in ids)
            paths = ids[objectId]
            self.assertTrue(path in paths)
            tagInfo = paths[path]
            self.assertTrue("value" in tagInfo)

        finally:
            # Clean created tags.
            self.fluiddb.objects[objectId][path].delete()

    def test_setOfStrings(self):
        """
        Check if the respose is correct when requesting a tag of type set
        using GET requests to /values. Bug #677215.
        """

        # Create a new object.
        response = self.fluiddb.objects.post('about')
        objectId = response.value['id']

        path = 'fluiddb/testing/test1'
        value = ['one', 'two', 'three']

        try:
            # Add a new set tag to the object.
            self.fluiddb.objects[objectId][path].put(value)

            # Get the tag value using the values API.
            response = self.fluiddb.values.get('fluiddb/about = "about"',
                                               [path])
            expected = response.value['results']['id'][objectId][path]['value']
            self.assertEqual(set(expected), set(value))
        finally:
            # Clean created tags.
            self.fluiddb.objects[objectId][path].delete()
