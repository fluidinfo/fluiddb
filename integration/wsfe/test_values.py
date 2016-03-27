# -*- coding: utf-8 -*-

import json

from twisted.web import http
from twisted.web.error import Error
from twisted.internet import defer

from fluiddb.common import error
from fluiddb.common.defaults import sep, httpValueCategoryName
from fluiddb.common import paths
from fluiddb.web.util import buildHeader
from fluiddb.web.values import tagArg, queryArg, resultsKey, idKey
from integration.wsfe import base, http as wsfe_http
import txbase

_usernamePath = sep.join(paths.usernamePath())
_namePath = sep.join(paths.namePath())
_emailPath = sep.join(paths.emailPath())
_aboutPath = sep.join(paths.aboutPath())


class ValuesTest(txbase.TxFluidDBTest, base.HTTPTest):
    """
    A base class for our FluidDB values tests.

    Note: for the time being this class still inherits from base.HTTPTest
    so that we can have tests that use both txFluidDB and the methods in
    base.HTTPTest. Once we have replaced everything from base.HTTPTest,
    this class will disappear entirely.
    """
    toplevel = httpValueCategoryName

    def setUp(self):
        """
        Initialize both our superclasses.
        """
        txbase.TxFluidDBTest.setUp(self)
        base.HTTPTest.setUp(self)


class TestPOST(ValuesTest):

    @base.showFailures
    @defer.inlineCallbacks
    def testNotAllowed(self):
        """
        POST to /values is not allowed. Confirm that's the case.
        """
        headers = {}
        self.addBasicAuthHeader(headers)
        uri = '%s/%s' % (self.endpoint, httpValueCategoryName)
        d = wsfe_http.getPage(uri, headers=headers, method='POST')
        d.addErrback(self.checkErrorStatus, http.NOT_ALLOWED)
        self.failUnlessFailure(d, Error)
        yield d


class TestGET(ValuesTest):

    verb = 'GET'

    @defer.inlineCallbacks
    def testMissingQuery(self):
        """
        If no query= argument is given in the URI, we should get a
        BAD_REQUEST error, with appropriately set error headers.
        """
        d = self.getPage(queryDict={tagArg: _usernamePath})
        d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'): error.MissingArgument.__name__,
             buildHeader('argument'): queryArg})
        self.failUnlessFailure(d, Error)
        yield d

    @defer.inlineCallbacks
    def testRequestForTagWithNoInstances(self):
        """
        Create a new tag and send a query that asks for some tag values on
        objects with the new tag.  Because there are no objects with an
        instance of the tag, we should get no results.
        """
        path = 'fluiddb/testing/test1'
        headers = {}
        self.addBasicAuthHeader(headers)
        d = self.getPage(
            queryDict={
                queryArg: 'has %s' % path,
                tagArg: [path, _aboutPath, _usernamePath]},
            headers=headers)
        status, headers, payload = yield d
        self.assertEqual(int(status), http.OK)
        self.assertEqual(headers['content-type'][0], 'application/json')
        self.assertEqual(int(headers['content-length'][0]), len(payload))
        j = json.loads(payload)
        results = j[resultsKey][idKey]
        # There should be no results.
        self.assertEqual(results, {})


class TestPUT(ValuesTest):

    verb = 'PUT'

    @defer.inlineCallbacks
    def testMissingQuery(self):
        """
        If no query= argument is given in the URI, we should get a
        BAD_REQUEST error, with appropriately set error headers.
        """
        d = self.getPage()

#        TODO: Nginx returns 411 in this case. See Bug #676947.
#        d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)

#       TODO: We're not checking error headers because nginx doesn't send them.
#       Uncomment this line as soon as we fix that. See bug #676940.
#        d.addErrback(
#            self.checkErrorHeaders,
#            {buildHeader('Error-Class'): error.MissingArgument.__name__,
#             buildHeader('argument'): queryArg, })
        self.failUnlessFailure(d, Error)
        yield d


class TestDELETE(ValuesTest):

    verb = 'DELETE'

    @defer.inlineCallbacks
    def testMissingQuery(self):
        """
        If no query= argument is given in the URI, we should get a
        BAD_REQUEST error, with appropriately set error headers.
        """
        d = self.getPage(queryDict={tagArg: _usernamePath})
        d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'): error.MissingArgument.__name__,
             buildHeader('argument'): queryArg, })
        self.failUnlessFailure(d, Error)
        yield d
