from storm.store import Store

from fluiddb.data.store import getMainStore
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import DatabaseResource


class GetMainStoreTest(FluidinfoTestCase):

    resources = [('store', DatabaseResource())]

    def testGetMainStore(self):
        """
        L{getMainStore} returns a C{Store} instance for the main store, when
        one has been properly configured.
        """
        store = getMainStore()
        self.assertTrue(isinstance(store, Store))
        self.assertIdentical(self.store, store)
