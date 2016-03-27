# -*- coding: utf-8 -*-

from twisted.web import http
from twisted.web.error import Error
from twisted.internet import defer

from fluiddb.common import defaults, error
from fluiddb.web.util import buildHeader

from integration.wsfe import base
import txbase


class ObjectTest(txbase.TxFluidDBTest, base.HTTPTest):
    """
    A base class for our FluidDB object tests.

    Note: for the time being this class still inherits from base.HTTPTest
    so that we can have tests that use both txFluidDB and the methods in
    base.HTTPTest. Once we have replaced everything from base.HTTPTest,
    this class will disappear entirely.
    """

    toplevel = defaults.httpObjectCategoryName

    def setUp(self):
        """
        Initialize both our superclasses.
        """
        txbase.TxFluidDBTest.setUp(self)
        base.HTTPTest.setUp(self)


class TestPOST(ObjectTest):

    verb = 'POST'

    @base.showFailures
    def testNotImplemented(self):
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage(base.randomObjectIdStr(), headers=headers)
        d.addErrback(self.checkErrorStatus, http.NOT_ALLOWED)
        self.failUnlessFailure(d, Error)
        return d


class TestGET(ObjectTest):

    verb = 'GET'

    @base.showFailures
    @defer.inlineCallbacks
    def testNonExistent(self):
        objectId = base.randomObjectIdStr()
        objectInfo = yield self.getObject(objectId, showAbout=True)
        self.assertEqual(objectInfo['about'], None)
        self.assertEqual(objectInfo['tagPaths'], [])

    @base.showFailures
    @defer.inlineCallbacks
    def testCreateRetrieve(self):
        objectId = yield self.createObject()
        objectInfo = yield self.getObject(str(objectId), showAbout=True)
        self.assertEqual(objectInfo['about'], None)
        self.assertEqual(objectInfo['tagPaths'], [])

    @base.showFailures
    @defer.inlineCallbacks
    def testShowAboutDefault(self):
        # Don't pass a showAbout in the URI
        objectId = yield self.createObject()
        objectInfo = yield self.getObject(str(objectId),
                                          omitShowAboutInURI=True)
        self.assertTrue('showAbout' not in objectInfo)

    @base.showFailures
    @defer.inlineCallbacks
    def testShowAboutWithNoneValue(self):
        objectId = yield self.createObject()
        objectInfo = yield self.getObject(str(objectId), showAbout=True)
        self.assertEqual(objectInfo['about'], None)

    @base.showFailures
    @defer.inlineCallbacks
    def testDontShowAbout(self):
        objectId = yield self.createObject()
        objectInfo = yield self.getObject(str(objectId), showAbout=False)
        self.assertTrue('about' not in objectInfo)

    @base.showFailures
    @defer.inlineCallbacks
    def testStarStarAccept(self):
        objectId = yield self.createObject()
        d = self.getObject(str(objectId), accept='*/*')
        objectInfo = yield d
        self.assertTrue('about' not in objectInfo)

    @base.showFailures
    @defer.inlineCallbacks
    def testNonsenseAccept(self):
        objectId = yield self.createObject()
        d = self.getObject(str(objectId), accept='x/y')
        d.addErrback(self.checkErrorStatus, http.NOT_ACCEPTABLE)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'): error.NotAcceptable.__name__})
        self.failUnlessFailure(d, Error)
        yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testMultipartAccept(self):
        objectId = yield self.createObject()
        yield self.getObject(str(objectId), accept='a/b, c/d; q=0.5, */*')

    @base.showFailures
    @defer.inlineCallbacks
    def testApplicationStarAccept(self):
        objectId = yield self.createObject()
        yield self.getObject(str(objectId), accept='application/*, c/d; q=0.5')

    @base.showFailures
    @defer.inlineCallbacks
    def testNoAccept(self):
        headers = {}
        self.addBasicAuthHeader(headers)
        objectId = yield self.createObject()
        d = self.getPage(str(objectId), headers=headers)
        d.addCallback(self.checkStatus, http.OK)
        d.addCallback(self.checkPayloadHasNot, ['about'])
        expectedFields = ['tagPaths']
        d.addCallback(self.checkPayloadHas, dict.fromkeys(expectedFields))
        yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testUnicodeAbout(self):
        aboutStr = u'\xf8'
        objectId = yield self.createObject(about=aboutStr)
        objectInfo = yield self.getObject(str(objectId), showAbout=True)
        self.assertEqual(objectInfo['about'], aboutStr)


class TestPUT(ObjectTest):

    verb = 'PUT'

    @base.showFailures
    def testNotImplemented(self):
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage(base.randomObjectIdStr(), headers=headers)
#         TODO: Nginx returns 411 in this case. See Bug #676947.
#        d.addErrback(self.checkErrorStatus, http.NOT_IMPLEMENTED)
        self.failUnlessFailure(d, Error)
        return d


class TestDELETE(ObjectTest):

    verb = 'DELETE'

    @base.showFailures
    def testNotImplemented(self):
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage(base.randomObjectIdStr(), headers=headers)
        d.addErrback(self.checkErrorStatus, http.NOT_IMPLEMENTED)
        self.failUnlessFailure(d, Error)
        return d
