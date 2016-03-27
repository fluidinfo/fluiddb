"""
NOTE:

We're aiming to have a test suite that depends only on txfluiddb, Twisted,
and the Python standard library. If you think you need some functionality
from the FluidDB code base, please ask others whether they think that makes
sense.

For now we conditionally import requireEnvironmentVariables. That may go
away, or be replaced with code that manually does the same check, or we may
one day release a standalone fluiddb.common module that we ask people to
install.
"""

import os
import txfluiddb
from twisted.trial import unittest

_endpointURI = os.environ.get('FLUIDDB_ENDPOINT', 'http://localhost:9000')


class TxFluidDBTest(unittest.TestCase):
    """
    A thin base class for integration tests of FluidDB. FluidDB integration
    tests that are doing routine operations against FluidDB should subclass
    this class. By 'routine' we mean calls to FluidDB that do things in
    order to prepare for a call that has to be tested in detail. The call
    that has to be tested in detail (e.g., for response headers) can then
    be done with L{twisted.web.client.Agent}.
    """

    def setUp(self):
        """
        Create an endpoint for txFluidDB to use for routine calls into
        FluidDB.

        NOTE: self.txEndpoint will be renamed to self.endpoint when we get
        rid of the HTTPTest class in base.py.
        """
        username = os.environ.get('FLUIDDB_ADMIN_USERNAME', 'fluiddb')
        password = os.environ.get('FLUIDDB_ADMIN_PASSWORD', 'secret')
        creds = txfluiddb.client.BasicCreds(username, password)
        self.txEndpoint = txfluiddb.client.Endpoint(baseURL=_endpointURI,
                                                    creds=creds)

    def createObject(self, about=None):
        """
        Use txFluidDB to create a new FluidDB object, with the given
        C{about} value.

        @param about: A C{unicode} about value.
        @return: A C{Deferred} that fires with the new object id.
        """
        d = txfluiddb.client.Object.create(self.txEndpoint, about)
        return d.addCallback(lambda obj: obj.uuid)
