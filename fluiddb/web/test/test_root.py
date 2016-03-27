from twisted.cred.error import UnauthorizedLogin
from twisted.internet.defer import inlineCallbacks

from fluiddb.api.facade import Facade
from fluiddb.application import FluidinfoSessionFactory, getConfig
from fluiddb.data.system import createSystemData
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.doubles import FakeRequest
from fluiddb.testing.resources import (
    ConfigResource, DatabaseResource, LoggingResource, ThreadPoolResource)
from fluiddb.util.transact import Transact
from fluiddb.web.checkers import AnonymousChecker
from fluiddb.web.root import RootResource


class RootResourceTest(FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(RootResourceTest, self).setUp()
        factory = FluidinfoSessionFactory('API-9000')
        transact = Transact(self.threadPool)
        createSystemData()
        self.checker = AnonymousChecker()
        self.checker.facadeClient = Facade(transact, factory)
        getConfig().set('service', 'allow-anonymous-access', 'False')

    @inlineCallbacks
    def testAnonymousAccessDenied(self):
        """
        L{FacadeAnonymousCheckerTest.requestAvatarId} returns
        an C{UnauthorizedLogin} for access by the C{anon} user if the
        C{allow-anonymous-access} configuration option is C{False}. The
        C{UnauthorizedLogin} is the C{session} attribute in L{RootResource} and
        must result in the C{getChild} method returning a
        L{WSFEUnauthorizedResource} instance.
        """
        self.store.commit()
        session = yield self.checker.requestAvatarId(credentials=None)
        self.assertTrue(isinstance(session, UnauthorizedLogin))
        root = RootResource(self.checker.facadeClient, session)
        request = FakeRequest()
        root.getChild('/', request)
