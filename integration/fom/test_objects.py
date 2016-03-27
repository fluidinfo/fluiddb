import os
import unittest

from fom.session import Fluid
from fom.mapping import Namespace, Object


class TestGET(unittest.TestCase):

    def setUp(self):
        endpoint = os.environ.get('FLUIDDB_ENDPOINT', 'http://localhost:9000')
        username = os.environ.get('FLUIDDB_ADMIN_USERNAME', 'fluiddb')
        password = os.environ.get('FLUIDDB_ADMIN_PASSWORD', 'secret')
        self.fluiddb = Fluid(endpoint)
        self.fluiddb.login(username, password)
        self.fluiddb.bind()

    def testQueryWithUnicodeTagName(self):
        """
        Make sure that a query using a tag whose name contains non-ASCII
        unicode characters works correctly.

        See https://bugs.edge.launchpad.net/fluiddb/+bug/681354 for the reason
        this is tested.
        """
        # Use the testuser1 root namespace.
        ns = Namespace('testuser1')
        # Umlauts FTW!
        tag_name = u'C\xfc\xe4h'
        # Create the tag.
        tag = ns.create_tag(tag_name, 'Used for testing purposes', False)
        try:
            # Run a query that uses the tag.  If we haven't fixed the bug,
            # FluidDB will hang at this point.
            result = Object.filter('has testuser1/%s' % tag_name)
            # Check the result is an empty list (i.e., no results found).
            self.assertEqual([], result)
        finally:
            # Clean up the tag.
            tag.delete()

    def testTagValueTypeHeaderInt(self):
        """
        When requesting a primitive tag value using a GET or HEAD request to
        /objects/id/namespace/tag, the response should put an X-FluidDB-Type
        header indicating the type of the response. This particular test
        checks header values for the int type.
        """
        # Create and object and add one tag.
        id = self.fluiddb.objects.post().value['id']
        self.fluiddb.objects[id]['fluiddb/testing/test1'].put(1)

        try:
            response = self.fluiddb.objects[id]['fluiddb/testing/test1'].get()
            self.assertEqual('int',
                             response.response.headers.get('x-fluiddb-type'))

            response = self.fluiddb.objects[id]['fluiddb/testing/test1'].head()
            self.assertEqual('int',
                             response.response.headers.get('x-fluiddb-type'))
        finally:
            self.fluiddb.objects[id]['fluiddb/testing/test1'].delete()

    def testTagValueTypeHeaderFloat(self):
        """
        When requesting a primitive tag value using a GET or HEAD request to
        /objects/id/namespace/tag, the response should put an X-FluidDB-Type
        header indicating the type of the response. This particular test
        checks header values for the float type.
        """
        # Create and object and add one tag.
        id = self.fluiddb.objects.post().value['id']
        self.fluiddb.objects[id]['fluiddb/testing/test1'].put(1.1)

        try:
            response = self.fluiddb.objects[id]['fluiddb/testing/test1'].get()
            self.assertEqual('float',
                             response.response.headers.get('x-fluiddb-type'))

            response = self.fluiddb.objects[id]['fluiddb/testing/test1'].head()
            self.assertEqual('float',
                             response.response.headers.get('x-fluiddb-type'))
        finally:
            self.fluiddb.objects[id]['fluiddb/testing/test1'].delete()

    def testTagValueTypeHeaderString(self):
        """
        When requesting a primitive tag value using a GET or HEAD request to
        /objects/id/namespace/tag, the response should put an X-FluidDB-Type
        header indicating the type of the response. This particular test
        checks header values for the string type.
        """
        # Create and object and add one tag.
        id = self.fluiddb.objects.post().value['id']
        self.fluiddb.objects[id]['fluiddb/testing/test1'].put('hello')

        try:
            response = self.fluiddb.objects[id]['fluiddb/testing/test1'].get()
            self.assertEqual('string',
                             response.response.headers.get('x-fluiddb-type'))

            response = self.fluiddb.objects[id]['fluiddb/testing/test1'].head()
            self.assertEqual('string',
                             response.response.headers.get('x-fluiddb-type'))
        finally:
            self.fluiddb.objects[id]['fluiddb/testing/test1'].delete()

    def testTagValueTypeHeaderBool(self):
        """
        When requesting a primitive tag value using a GET or HEAD request to
        /objects/id/namespace/tag, the response should put an X-FluidDB-Type
        header indicating the type of the response. This particular test
        checks header values for the bool type.
        """
        # Create and object and add one tag.
        id = self.fluiddb.objects.post().value['id']
        self.fluiddb.objects[id]['fluiddb/testing/test1'].put(True)

        try:
            response = self.fluiddb.objects[id]['fluiddb/testing/test1'].get()
            self.assertEqual('boolean',
                             response.response.headers.get('x-fluiddb-type'))

            response = self.fluiddb.objects[id]['fluiddb/testing/test1'].head()
            self.assertEqual('boolean',
                             response.response.headers.get('x-fluiddb-type'))
        finally:
            self.fluiddb.objects[id]['fluiddb/testing/test1'].delete()

    def testTagValueTypeHeaderNull(self):
        """
        When requesting a primitive tag value using a GET or HEAD request to
        /objects/id/namespace/tag, the response should put an X-FluidDB-Type
        header indicating the type of the response. This particular test
        checks header values for the none type.
        """
        # Create and object and add one tag.
        id = self.fluiddb.objects.post().value['id']
        self.fluiddb.objects[id]['fluiddb/testing/test1'].put(None)

        try:
            response = self.fluiddb.objects[id]['fluiddb/testing/test1'].get()
            self.assertEqual('null',
                             response.response.headers.get('x-fluiddb-type'))

            response = self.fluiddb.objects[id]['fluiddb/testing/test1'].head()
            self.assertEqual('null',
                             response.response.headers.get('x-fluiddb-type'))
        finally:
            self.fluiddb.objects[id]['fluiddb/testing/test1'].delete()

    def testTagValueTypeHeaderList(self):
        """
        When requesting a primitive tag value using a GET or HEAD request to
        /objects/id/namespace/tag, the response should put an X-FluidDB-Type
        header indicating the type of the response. This particular test
        checks header values for the set type.
        """
        # Create and object and add one tag.
        id = self.fluiddb.objects.post().value['id']
        self.fluiddb.objects[id]['fluiddb/testing/test1'].put(['one', 'two'])

        try:
            response = self.fluiddb.objects[id]['fluiddb/testing/test1'].get()
            self.assertEqual('list-of-strings',
                             response.response.headers.get('x-fluiddb-type'))

            response = self.fluiddb.objects[id]['fluiddb/testing/test1'].head()
            self.assertEqual('list-of-strings',
                             response.response.headers.get('x-fluiddb-type'))
        finally:
            self.fluiddb.objects[id]['fluiddb/testing/test1'].delete()
