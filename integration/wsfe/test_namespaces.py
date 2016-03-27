# -*- coding: utf-8 -*-

import json

from twisted.internet import defer, reactor
from twisted.web import http
from twisted.web.error import Error
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from twisted.internet.protocol import Protocol

from fluiddb.common import error, defaults
from fluiddb.common import paths
from fluiddb.common.types_thrift.ttypes import TInvalidPath
from fluiddb.web.util import buildHeader

from integration.wsfe import base


class ResponseGetter(Protocol):
    __buffer = ''

    def __init__(self, finished):
        self._finished = finished

    def dataReceived(self, bytes):
        self.__buffer += bytes

    def connectionLost(self, reason):
        self._finished.callback(self.__buffer)


class NamespacesTest(base.HTTPTest):
    toplevel = defaults.httpNamespaceCategoryName


class TestPOST(NamespacesTest):

    verb = 'POST'

    @base.showFailures
    @defer.inlineCallbacks
    def testAsAdmin(self):
        name = 'test'
        parentPath = defaults.adminUsername
        yield self.createNamespace(name, parentPath)
        yield self.deleteNamespace(defaults.sep.join([parentPath, name]))

    @base.showFailures
    @defer.inlineCallbacks
    def testAsAdminDepthTwo(self):
        name = 'test'
        parentPath1 = defaults.adminUsername
        parentPath2 = defaults.sep.join([parentPath1, name])
        yield self.createNamespace(name, parentPath1)
        try:
            yield self.createNamespace(name, parentPath2)
            yield self.deleteNamespace(defaults.sep.join([parentPath2, name]))
        finally:
            yield self.deleteNamespace(parentPath2)

    @base.showFailures
    @defer.inlineCallbacks
    def testAlreadyExists(self):
        name = 'test'
        parentPath = defaults.adminUsername
        path = defaults.sep.join([parentPath, name])
        yield self.createNamespace(name, parentPath)
        try:
            d = self.createNamespace(name, parentPath)
            d.addErrback(self.checkErrorStatus, http.PRECONDITION_FAILED)
            self.failUnlessFailure(d, Error)
            yield d
        finally:
            yield self.deleteNamespace(path)

    @base.showFailures
    @defer.inlineCallbacks
    def testCaseSensitive(self):
        # Create the same namespace in lower, upper and title case.
        name = 'test'
        parentPath = defaults.adminUsername
        join = defaults.sep.join
        yield self.createNamespace(name, parentPath)
        try:
            yield self.createNamespace(name.upper(), parentPath)
            try:
                yield self.createNamespace(name.title(), parentPath)
                yield self.deleteNamespace(join([parentPath, name.title()]))
            finally:
                yield self.deleteNamespace(join([parentPath, name.upper()]))
        finally:
            yield self.deleteNamespace(join([parentPath, name]))

    @base.showFailures
    def testNoParent(self):
        name = '_mummy_'
        parentPath = defaults.sep.join([defaults.adminUsername, '_dummy_'])
        d = self.createNamespace(name, parentPath)
        d.addErrback(self.checkErrorStatus, http.NOT_FOUND)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testRandomUserInAdminNamespace(self):
        d = self.createNamespace('newname', 'fluiddb/testing',
                                 requesterUsername='testuser1',
                                 requesterPassword='secret')
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testRandomUserInOtherRandomUserNamespace(self):
        d = self.createNamespace('newname', 'testuser1/testing',
                                 requesterUsername='testuser2',
                                 requesterPassword='secret')
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    @defer.inlineCallbacks
    def testRandomUserInOwnNamespace(self):
        yield self.createNamespace('new', 'testuser1',
                                   requesterUsername='testuser1',
                                   requesterPassword='secret')
        yield self.deleteNamespace('testuser1/new')

    @base.showFailures
    def testAnonUserInOwnNamespace(self):
        d = self.createNamespace('name', defaults.anonUsername,
                                 requesterUsername=defaults.anonUsername,
                                 requesterPassword=defaults.anonPassword)
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    @defer.inlineCallbacks
    def testLongestPossiblePath(self):
        n = paths.maxPathLength - (len(defaults.adminUsername) + 1)
        name = 'X' * n
        yield self.createNamespace(name, defaults.adminUsername)
        yield self.deleteNamespace(
            defaults.sep.join([defaults.adminUsername, name]))

    @base.showFailures
    def testPathTooLong(self):
        n = paths.maxPathLength - len(defaults.adminUsername)
        name = 'X' * n
        d = self.createNamespace(name, defaults.adminUsername)
        d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'): TInvalidPath.__name__})
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    @defer.inlineCallbacks
    def testBadNameTypes(self):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        for field in ('name',):
            data = {
                'name': 'name',
                'description': 'description',
            }
            for value in (None, 3, 6.7, True, False, ['a', 'list'], {'x': 3}):
                data[field] = value
                d = self.getPage('%s' % defaults.adminUsername,
                                 headers=headers, postdata=json.dumps(data))
                d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
                d.addErrback(
                    self.checkErrorHeaders,
                    {buildHeader('Error-Class'):
                     error.InvalidPayloadField.__name__})
                self.failUnlessFailure(d, Error)
                yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testBadDescriptionTypes(self):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        for field in ('description',):
            data = {
                'name': 'name',
                'description': 'description',
            }
            for value in (3, 6.7, True, False, ['a', 'list'], {'x': 3}):
                data[field] = value
                d = self.getPage('%s' % defaults.adminUsername,
                                 headers=headers, postdata=json.dumps(data))
                d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
                d.addErrback(
                    self.checkErrorHeaders,
                    {buildHeader('Error-Class'):
                     error.InvalidPayloadField.__name__})
                self.failUnlessFailure(d, Error)
                yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testWithNoneDescription(self):
        name = 'test'
        parentPath = defaults.adminUsername
        yield self.createNamespace(name, parentPath, description=None)
        yield self.deleteNamespace(defaults.sep.join([parentPath, name]))

    @base.showFailures
    @defer.inlineCallbacks
    def testWithUnicodeDescription(self):
        name = 'test'
        parentPath = defaults.adminUsername
        yield self.createNamespace(name, parentPath, description=u'\xf8')
        yield self.deleteNamespace(defaults.sep.join([parentPath, name]))


class TestGET(NamespacesTest):

    verb = 'GET'

    @base.showFailures
    def testNonExistent(self):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage('blah', headers=headers)
        d.addErrback(self.checkErrorStatus, http.NOT_FOUND)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testReturnNamespaces(self):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage('fluiddb/testing', headers=headers,
                         queryDict={'returnNamespaces': True})
        d.addCallback(self.checkStatus, http.OK)
        d.addCallback(self.checkPayloadHas,
                      {'id': None, 'namespaceNames': ['testing']})
        d.addCallback(self.checkPayloadHasNot,
                      ('description', 'tagNames'))
        return d

    @defer.inlineCallbacks
    def testReturnTags(self):
        """
        Do a GET on the testing namespace and make sure we get the two
        testing tags back when we pass returnTags=True.
        """
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage('fluiddb/testing', headers=headers,
                         queryDict={'returnTags': True})
        d.addCallback(self.checkStatus, http.OK)
        d.addCallback(self.checkPayloadHas,
                      {'id': None,
                       'tagNames': ['test1', 'test2']})
        d.addCallback(self.checkPayloadHasNot,
                      ('description', 'namespaceNames'))
        yield d

    @base.showFailures
    def testReturnDescription(self):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage('fluiddb/testing', headers=headers,
                         queryDict={'returnDescription': True})
        d.addCallback(self.checkStatus, http.OK)
        d.addCallback(self.checkPayloadHas,
                      {'id': None,
                       'description': 'Used for testing purposes.'})
        d.addCallback(self.checkPayloadHasNot,
                      ('namespaceNames', 'tagNames'))
        return d

    @base.showFailures
    @defer.inlineCallbacks
    def testReturnNoneDescription(self):
        description = None
        name = 'test'
        parentPath1 = defaults.adminUsername
        parentPath2 = defaults.sep.join([parentPath1, name])
        yield self.createNamespace(name, parentPath1, description=description)
        try:
            headers = {
                'accept': 'application/json',
                'content-type': 'application/json',
            }
            self.addBasicAuthHeader(headers)
            d = self.getPage(parentPath2, headers=headers,
                             queryDict={'returnDescription': True})
            d.addCallback(self.checkStatus, http.OK)
            d.addCallback(self.checkPayloadHas,
                          {'id': None, 'description': description})
            yield d
        finally:
            yield self.deleteNamespace(parentPath2)

    @base.showFailures
    @defer.inlineCallbacks
    def testReturnUnicodeDescription(self):
        description = u'My \xf8 namespace.'
        name = 'test'
        parentPath1 = defaults.adminUsername
        parentPath2 = defaults.sep.join([parentPath1, name])
        yield self.createNamespace(name, parentPath1, description=description)
        try:
            headers = {
                'accept': 'application/json',
                'content-type': 'application/json',
            }
            self.addBasicAuthHeader(headers)
            d = self.getPage(parentPath2, headers=headers,
                             queryDict={'returnDescription': True})
            d.addCallback(self.checkStatus, http.OK)
            d.addCallback(self.checkPayloadHas,
                          {'id': None, 'description': description})
            yield d
        finally:
            yield self.deleteNamespace(parentPath2)

    @base.showFailures
    @defer.inlineCallbacks
    def testReturnNothing(self):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage(defaults.adminUsername, headers=headers)
        d.addCallback(self.checkStatus, http.OK)
        d.addCallback(self.checkPayloadHas, {'id': None})
        d.addCallback(self.checkPayloadHasNot,
                      ('description', 'namespaceNames', 'tagNames'))
        yield d

    @base.showFailures
    def testUnknownArgument(self):
        badArgument = 'blah'
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        return self.getPage(defaults.adminUsername, headers=headers,
                            queryDict={badArgument: True})

    @base.showFailures
    @defer.inlineCallbacks
    def testRepeatedArgument(self):
        argument = 'returnDescription'
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage('%s?%s=True&%s=True' %
                         (defaults.adminUsername, argument, argument),
                         headers=headers)
        d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'):
             error.MultipleArgumentValues.__name__,
             buildHeader('argument'): argument})
        self.failUnlessFailure(d, Error)
        yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testNoArgumentValue(self):
        # Put the argument into the URI, but without a value. It should
        # get its default value (False in this case).
        argument = 'returnDescription'
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage(defaults.adminUsername, headers=headers,
                         queryDict={argument: None})
        d.addCallback(self.checkStatus, http.OK)
        d.addCallback(self.checkPayloadHas, {'id': None})
        d.addCallback(self.checkPayloadHasNot,
                      ('description', 'namespaceNames', 'tagNames'))
        yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testVersionGets404(self):
        """
        Version numbers used to be able to be given in API calls, but are
        no longer supported.
        """
        version = 20100808

        URI = '%s/%d/%s/%s' % (
            self.endpoint,
            version,
            defaults.httpNamespaceCategoryName,
            defaults.adminUsername)

        headers = Headers({'accept': ['application/json']})

        agent = Agent(reactor)
        response = yield agent.request('GET', URI, headers)
        self.assertEqual(http.NOT_FOUND, response.code)


    # TODO: Add a test for a namespace that we don't have LIST perm on.
    # although that might be done in permissions.py when that finally gets
    # added.


class TestPUT(NamespacesTest):

    verb = 'PUT'

    @base.showFailures
    @defer.inlineCallbacks
    def testAsAdmin(self):
        name = 'test'
        parentPath = defaults.adminUsername
        path = defaults.sep.join([parentPath, name])
        yield self.createNamespace(name, parentPath)
        try:
            headers = {
                'content-type': 'application/json',
            }
            self.addBasicAuthHeader(headers)
            data = {
                'description': 'A totally new description.',
            }
            d = self.getPage(path, headers=headers, postdata=json.dumps(data))
            d.addCallback(self.checkStatus, http.NO_CONTENT)
            d.addCallback(self.checkNoPayload)
            yield d
        finally:
            yield self.deleteNamespace(path)

    @base.showFailures
    @defer.inlineCallbacks
    def testNoPayload(self):
        headers = {
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage(defaults.adminUsername, headers=headers)
        d.addErrback(self.checkErrorStatus, http.LENGTH_REQUIRED)

#       TODO: We're not checking error headers because nginx doesn't send them.
#       Uncomment this line as soon as we fix that. See bug #676940.
#        d.addErrback(
#            self.checkErrorHeaders,
#            {buildHeader('Error-Class'):
#             error.NoContentLengthHeader.__name__})

        self.failUnlessFailure(d, Error)
        yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testNoContentType(self):
        headers = {}
        self.addBasicAuthHeader(headers)
        data = {
            'description': 'A totally new description.',
        }
        d = self.getPage(defaults.adminUsername, headers=headers,
                         postdata=json.dumps(data))
        d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'):
             error.NoContentTypeHeader.__name__})
        self.failUnlessFailure(d, Error)
        yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testNonExistent(self):
        headers = {
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        data = {
            'description': 'A succinct description.',
        }
        d = self.getPage('blah', headers=headers, postdata=json.dumps(data))
        d.addErrback(self.checkErrorStatus, http.NOT_FOUND)
        self.failUnlessFailure(d, Error)
        yield d

    @base.showFailures
    def testRandomUserUpdatesAdminTopLevel(self):
        headers = {
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers, 'testuser1', 'secret')
        data = {
            'description': 'A wacky, but concise description.',
        }
        d = self.getPage(defaults.adminUsername, headers=headers,
                         postdata=json.dumps(data))
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testRandomUserUpdatesAdminNew(self):
        headers = {
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers, 'testuser1', 'secret')
        data = {
            'description': 'A totally new description.',
        }
        d = self.getPage('fluiddb/testing', headers=headers,
                         postdata=json.dumps(data))
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testAnonUserUpdatesTopLevel(self):
        headers = {
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers,
                                defaults.anonUsername, defaults.anonPassword)
        data = {
            'description': 'A description doomed to failure.',
        }
        d = self.getPage(defaults.anonUsername, headers=headers,
                         postdata=json.dumps(data))
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    @defer.inlineCallbacks
    def testBadTypes(self):
        headers = {
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)

        for field in ('description',):
            data = {
                'description': 'description',
            }
            for value in (3, 6.7, True, False, ['a', 'list'], {'x': 3}):
                data[field] = value
                d = self.getPage(defaults.adminUsername,
                                 headers=headers,
                                 postdata=json.dumps(data))
                d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
                d.addErrback(
                    self.checkErrorHeaders,
                    {buildHeader('Error-Class'):
                     error.InvalidPayloadField.__name__})
                self.failUnlessFailure(d, Error)
                yield d


class TestDELETE(NamespacesTest):

    verb = 'DELETE'

    @base.showFailures
    def testNonExistent(self):
        d = self.deleteNamespace(
            defaults.sep.join([defaults.adminUsername, '_dummy_']))
        d.addErrback(self.checkErrorStatus, http.NOT_FOUND)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testRandomUserDeletesAdminTopLevel(self):
        d = self.deleteNamespace(defaults.adminUsername,
                                 requesterUsername='testuser1',
                                 requesterPassword='secret')
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testRandomUserDeletesAdminNew(self):
        d = self.deleteNamespace('fluiddb/testing',
                                 requesterUsername='testuser1',
                                 requesterPassword='secret')
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testRandomUserDeletesRandomUser(self):
        d = self.deleteNamespace('testuser2',
                                 requesterUsername='testuser1',
                                 requesterPassword='secret')
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testAsAdminNonEmptyWithNamespace(self):
        d = self.deleteNamespace('fluiddb/testing')
        d.addErrback(self.checkErrorStatus, http.PRECONDITION_FAILED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testAsAdminNonEmptyWithTag(self):
        d = self.deleteNamespace('fluiddb/testing')
        d.addErrback(self.checkErrorStatus, http.PRECONDITION_FAILED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testAnonUserDeleteOwnNamespace(self):
        d = self.deleteNamespace(defaults.anonUsername,
                                 requesterUsername=defaults.anonUsername,
                                 requesterPassword=defaults.anonPassword)
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        return d
