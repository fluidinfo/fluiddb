import os
import unittest

from fom.session import Fluid
from fom.mapping import Namespace


class TestNamespaces(unittest.TestCase):

    def setUp(self):
        endpoint = os.environ.get('FLUIDDB_ENDPOINT', 'http://localhost:9000')
        username = os.environ.get('FLUIDDB_ADMIN_USERNAME', 'fluiddb')
        password = os.environ.get('FLUIDDB_ADMIN_PASSWORD', 'secret')
        self.fluiddb = Fluid(endpoint)
        self.fluiddb.login(username, password)
        self.fluiddb.bind()

    def testPOSTNewNamespaceUnderUnicodeNamespace(self):
        """
        There shouldn't be a problem creating a namespace under a parent whose
        name is expressed in non-ascii characters.

        See the following bug:
        https://bugs.edge.launchpad.net/fluiddb/+bug/762779
        """
        # Use the testuser1 root namespace.
        ns = Namespace('testuser1')
        # Create an interestingly named namespace
        quran = u'\ufe8e\ufee0\ufed7\ufead\ufe81'
        quranNS = ns.create_namespace(quran, 'For the purposes of testing')
        # Attempt to create a new namespace underneath
        newNS = False
        try:
            # just check it can be created
            newNS = quranNS.create_namespace('foo', 'This is a test')
            expectedPath = u'testuser1/' + quran + '/foo'
            self.assertEqual(expectedPath, newNS.path)
        finally:
            if newNS:
                newNS.delete()
            quranNS.delete()
