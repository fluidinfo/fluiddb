import os
import unittest

from fom.session import Fluid


class TestGETHEAD(unittest.TestCase):

    def setUp(self):
        endpoint = os.environ.get('FLUIDDB_ENDPOINT', 'http://localhost:9000')
        username = os.environ.get('FLUIDDB_ADMIN_USERNAME', 'fluiddb')
        password = os.environ.get('FLUIDDB_ADMIN_PASSWORD', 'secret')
        self.fluiddb = Fluid(endpoint)
        self.fluiddb.login(username, password)
        self.fluiddb.bind()

    def testTagValueTypeHeaderFloat(self):
        """
        When requesting a primitive tag value using a GET or HEAD request to
        /objects/id/namespace/tag, the response should put an X-FluidDB-Type
        header indicating the type of the response. This particular test
        checks header values for the float type.
        """
        # Create and object and add one tag.
        self.fluiddb.about.post('about').value['id']
        path = 'fluiddb/testing/test1'
        self.fluiddb.about['about'][path].put(1.1)

        try:
            response = self.fluiddb.about['about'][path].get()
            self.assertEqual('float',
                             response.response.headers.get('x-fluiddb-type'))

            response = self.fluiddb.about['about'][path].head()
            self.assertEqual('float',
                             response.response.headers.get('x-fluiddb-type'))
        finally:
            self.fluiddb.about['about'][path].delete()

    def testTagValueTypeHeaderString(self):
        """
        When requesting a primitive tag value using a GET or HEAD request to
        /objects/id/namespace/tag, the response should put an X-FluidDB-Type
        header indicating the type of the response. This particular test
        checks header values for the string type.
        """
        # Create and object and add one tag.
        self.fluiddb.about.post('about').value['id']
        path = 'fluiddb/testing/test1'
        self.fluiddb.about['about'][path].put('hello')

        try:
            response = self.fluiddb.about['about'][path].get()
            self.assertEqual('string',
                             response.response.headers.get('x-fluiddb-type'))

            response = self.fluiddb.about['about'][path].head()
            self.assertEqual('string',
                             response.response.headers.get('x-fluiddb-type'))
        finally:
            self.fluiddb.about['about'][path].delete()

    def testTagValueTypeHeaderBool(self):
        """
        When requesting a primitive tag value using a GET or HEAD request to
        /objects/id/namespace/tag, the response should put an X-FluidDB-Type
        header indicating the type of the response. This particular test
        checks header values for the bool type.
        """
        # Create and object and add one tag.
        self.fluiddb.about.post('about').value['id']
        path = 'fluiddb/testing/test1'
        self.fluiddb.about['about'][path].put(True)

        try:
            response = self.fluiddb.about['about'][path].get()
            self.assertEqual('boolean',
                             response.response.headers.get('x-fluiddb-type'))

            response = self.fluiddb.about['about'][path].head()
            self.assertEqual('boolean',
                             response.response.headers.get('x-fluiddb-type'))
        finally:
            self.fluiddb.about['about'][path].delete()

    def testTagValueTypeHeaderNull(self):
        """
        When requesting a primitive tag value using a GET or HEAD request to
        /objects/id/namespace/tag, the response should put an X-FluidDB-Type
        header indicating the type of the response. This particular test
        checks header values for the none type.
        """
        # Create and object and add one tag.
        self.fluiddb.about.post('about').value['id']
        path = 'fluiddb/testing/test1'
        self.fluiddb.about['about'][path].put(None)

        try:
            response = self.fluiddb.about['about'][path].get()
            self.assertEqual('null',
                             response.response.headers.get('x-fluiddb-type'))

            response = self.fluiddb.about['about'][path].head()
            self.assertEqual('null',
                             response.response.headers.get('x-fluiddb-type'))
        finally:
            self.fluiddb.about['about'][path].delete()

    def testTagValueTypeHeaderList(self):
        """
        When requesting a primitive tag value using a GET or HEAD request to
        /objects/id/namespace/tag, the response should put an X-FluidDB-Type
        header indicating the type of the response. This particular test
        checks header values for the set type.
        """
        # Create and object and add one tag.
        self.fluiddb.about.post('about').value['id']
        path = 'fluiddb/testing/test1'
        self.fluiddb.about['about'][path].put(['one', 'two'])

        try:
            response = self.fluiddb.about['about'][path].get()
            self.assertEqual('list-of-strings',
                             response.response.headers.get('x-fluiddb-type'))

            response = self.fluiddb.about['about'][path].head()
            self.assertEqual('list-of-strings',
                             response.response.headers.get('x-fluiddb-type'))
        finally:
            self.fluiddb.about['about'][path].delete()
