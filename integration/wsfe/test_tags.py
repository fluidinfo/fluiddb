# -*- coding: utf-8 -*-

from urllib import urlencode
import json

from twisted.web import http
from twisted.web.error import Error
from twisted.internet import defer

from fluiddb.common import error, defaults
from fluiddb.common import paths
from fluiddb.common.types_thrift.ttypes import TInvalidPath
from fluiddb.web.util import buildHeader

from integration.wsfe import base, http as wsfe_http


class TagsTest(base.HTTPTest):
    toplevel = defaults.httpTagCategoryName


class TestPOST(TagsTest):

    verb = 'POST'

    @base.showFailures
    @defer.inlineCallbacks
    def testAsAdmin(self):
        name = 'test'
        parentPath = defaults.adminUsername
        yield self.createTag(name, parentPath)
        yield self.deleteTag(defaults.sep.join([parentPath, name]))

    @base.showFailures
    @defer.inlineCallbacks
    def testAsAdminJSONP(self):
        name = 'test'
        parentPath = defaults.adminUsername
        headers = {}
        self.addBasicAuthHeader(headers)
        uri = '%s/%s/%s' % (self.endpoint,
                            defaults.httpTagCategoryName,
                            parentPath)

        data = {
            'description': 'some description',
            'indexed': False,
            'name': name,
        }

        payload = json.dumps(data)

        params = {
            'verb': 'POST',
            'payload': payload,
            'payload-type': 'application/json',
            'payload-length': len(payload),
        }

        uriTag = uri + '?' + urlencode(params)
        yield wsfe_http.getPage(uriTag, headers=headers)
        yield self.deleteTag(defaults.sep.join([parentPath, name]))

    @base.showFailures
    @defer.inlineCallbacks
    def testAsAdminNoPayloadLengthJSONP(self):
        name = 'test'
        parentPath = defaults.adminUsername
        headers = {}
        self.addBasicAuthHeader(headers)
        uri = '%s/%s/%s' % (self.endpoint,
                            defaults.httpTagCategoryName,
                            parentPath)

        data = {
            'description': 'some description',
            'indexed': False,
            'name': name,
        }

        payload = json.dumps(data)

        params = {
            'verb': 'POST',
            'payload': payload,
            'payload-type': 'application/json',
        }

        uriTag = uri + '?' + urlencode(params)
        try:
            yield wsfe_http.getPage(uriTag, headers=headers)
        except Exception, e:
            self.assertEqual(http.BAD_REQUEST, int(e.status))
            self.assertEqual('ContentLengthMismatch',
                             e.response_headers['x-fluiddb-error-class'][0])

    @base.showFailures
    @defer.inlineCallbacks
    def testAsAdminJSONPBase64(self):
        import base64
        name = 'test'
        parentPath = defaults.adminUsername
        headers = {}
        self.addBasicAuthHeader(headers)
        uri = '%s/%s/%s' % (self.endpoint,
                            defaults.httpTagCategoryName,
                            parentPath)

        data = {
            'description': 'some description',
            'indexed': False,
            'name': name,
        }

        payload = base64.standard_b64encode(json.dumps(data))

        params = {
            'verb': 'POST',
            'payload': payload,
            'payload-type': 'application/json',
            'payload-encoding': 'base64',
            'payload-length': len(payload),
        }

        uriTag = uri + '?' + urlencode(params)
        yield wsfe_http.getPage(uriTag, headers=headers)
        yield self.deleteTag(defaults.sep.join([parentPath, name]))

    @base.showFailures
    @defer.inlineCallbacks
    def testAsAdminNoPayloadJSONP(self):
        parentPath = defaults.adminUsername
        headers = {}
        self.addBasicAuthHeader(headers)
        uri = '%s/%s/%s' % (self.endpoint,
                            defaults.httpTagCategoryName,
                            parentPath)

        params = {
            'verb': 'POST',
            'payload-length': 0,
            'payload-type': 'application/json',
        }

        uriTag = uri + '?' + urlencode(params)

        try:
            yield wsfe_http.getPage(uriTag, headers=headers)
        except Exception, e:
            self.assertEqual(http.BAD_REQUEST, int(e.status))
            self.assertEqual('MissingPayload',
                             e.response_headers['x-fluiddb-error-class'][0])

    @base.showFailures
    @defer.inlineCallbacks
    def testAsAdminNoPayloadTypeJSONP(self):
        name = 'test'
        parentPath = defaults.adminUsername
        headers = {}
        self.addBasicAuthHeader(headers)
        uri = '%s/%s/%s' % (self.endpoint,
                            defaults.httpTagCategoryName,
                            parentPath)

        data = {
            'description': 'some description',
            'indexed': False,
            'name': name,
        }

        payload = json.dumps(data)

        params = {
            'verb': 'POST',
            'payload': payload,
            'payload-length': len(payload),
        }

        uriTag = uri + '?' + urlencode(params)

        try:
            yield wsfe_http.getPage(uriTag, headers=headers)
        except Exception, e:
            self.assertEqual(http.BAD_REQUEST, int(e.status))
            self.assertEqual('NoContentTypeHeader',
                             e.response_headers['x-fluiddb-error-class'][0])

    @base.showFailures
    @defer.inlineCallbacks
    def testAsAdminMissingRequiredPayloadFieldJSONP(self):
        """
        Send a POST request to create a tag, but omit the 'indexed' key
        from the payload. Test that we get a Bad Request response, with the
        X-FluidDB-Error-Class header set to PayloadFieldMissing and
        X-FluidDB-Fieldname with containing 'indexed'.
        """
        name = 'test'
        parentPath = defaults.adminUsername
        headers = {}
        self.addBasicAuthHeader(headers)
        uri = '%s/%s/%s' % (self.endpoint,
                            defaults.httpTagCategoryName,
                            parentPath)

        data = {
            'description': 'some description',
            'name': name,
        }

        payload = json.dumps(data)

        params = {
            'verb': 'POST',
            'payload': payload,
            'payload-type': 'application/json',
            'payload-length': len(payload),
        }

        uriTag = uri + '?' + urlencode(params)

        try:
            yield wsfe_http.getPage(uriTag, headers=headers)
        except Exception, e:
            self.assertEqual(http.BAD_REQUEST, int(e.status))
            self.assertEqual('PayloadFieldMissing',
                             e.response_headers['x-fluiddb-error-class'][0])
            self.assertEqual('indexed',
                             e.response_headers['x-fluiddb-fieldname'][0])

    @base.showFailures
    @defer.inlineCallbacks
    def testAsAdminDepthTwo(self):
        name = 'test'
        parentPath1 = defaults.adminUsername
        parentPath2 = defaults.sep.join([parentPath1, name])
        yield self.createNamespace(name, parentPath1)
        try:
            yield self.createTag(name, parentPath2)
            yield self.deleteTag(defaults.sep.join([parentPath2, name]))
        finally:
            yield self.deleteNamespace(parentPath2)

    @base.showFailures
    def testAlreadyExists(self):
        d = self.createTag('test1', 'fluiddb/testing')
        d.addErrback(self.checkErrorStatus, http.PRECONDITION_FAILED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    @defer.inlineCallbacks
    def testCaseSensitive(self):
        """
        Try recreating one of the built-in test tags in uppercase. This
        should not raise any error.
        """
        yield self.createTag('TEST1', 'fluiddb/testing')
        yield self.deleteTag('fluiddb/testing/TEST1')

    @base.showFailures
    def testNonexistentParentNamespace(self):
        d = self.createTag('xxx', 'fluiddb/non-existent')
        d.addErrback(self.checkErrorStatus, http.NOT_FOUND)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testRandomUserInAdminNamespace(self):
        d = self.createTag('newname', 'fluiddb',
                           requesterUsername='testuser1',
                           requesterPassword='secret')
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testRandomUserInOtherRandomUserNamespace(self):
        d = self.createTag('newname', 'testuser1/testing',
                           requesterUsername='testuser2',
                           requesterPassword='secret')
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        yield d

    @base.showFailures
    def testAnonUserInOwnNamespace(self):
        d = self.createTag('name', defaults.anonUsername,
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
        yield self.createTag(name, defaults.adminUsername)
        yield self.deleteTag(
            defaults.sep.join([defaults.adminUsername, name]))

    @base.showFailures
    def testPathTooLong(self):
        n = paths.maxPathLength - len(defaults.adminUsername)
        name = 'X' * n
        d = self.createTag(name, defaults.adminUsername)
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
                'indexed': True,
            }
            for value in (None, 3, 6.7, True, False, ['a', 'list'], {'x': 3}):
                data[field] = value
                d = self.getPage(defaults.adminUsername,
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
                'indexed': True,
            }
            for value in (3, 6.7, True, False, ['a', 'list'], {'x': 3}):
                data[field] = value
                d = self.getPage(defaults.adminUsername,
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
    def testBadIndexedTypes(self):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        for field in ('indexed',):
            data = {
                'name': 'name',
                'description': 'description',
                'indexed': True,
            }
            for value in (None, 3, 6.7, ['a', 'list'], {'x': 3}):
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
        yield self.createTag(name, parentPath, description=None)
        yield self.deleteTag(defaults.sep.join([parentPath, name]))

    @base.showFailures
    @defer.inlineCallbacks
    def testWithUnicodeDescription(self):
        name = 'test'
        parentPath = defaults.adminUsername
        yield self.createTag(name, parentPath, description=u'\xf8')
        yield self.deleteTag(defaults.sep.join([parentPath, name]))


class TestGET(TagsTest):

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
    def testReturnDescription(self):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage('fluiddb/testing/test1', headers=headers,
                         queryDict={'returnDescription': True})
        d.addCallback(self.checkStatus, http.OK)
        d.addCallback(self.checkPayloadHas,
                      {'id': None,
                       'description': 'Used for testing purposes.',
                       'indexed': True,
                       })
        return d

    @base.showFailures
    @defer.inlineCallbacks
    def testReturnNoneDescription(self):
        description = None
        name = 'test'
        parentPath1 = defaults.adminUsername
        parentPath2 = defaults.sep.join([parentPath1, name])
        indexed = True
        yield self.createTag(name, parentPath1, description=description,
                             indexed=indexed)
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
                          {'id': None,
                           'description': description,
                           'indexed': indexed,
                           })
            yield d
        finally:
            yield self.deleteTag(parentPath2)

    @base.showFailures
    @defer.inlineCallbacks
    def testReturnUnicodeDescription(self):
        description = u'A \xf8 unicode description!'
        name = 'test'
        parentPath1 = defaults.adminUsername
        parentPath2 = defaults.sep.join([parentPath1, name])
        yield self.createTag(name, parentPath1, description=description,
                             indexed=False)
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
                          {'id': None,
                           'description': description,
                           })
            yield d
        finally:
            yield self.deleteTag(parentPath2)

    @base.showFailures
    def testReturnNothing(self):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage('fluiddb/testing/test1', headers=headers)
        d.addCallback(self.checkStatus, http.OK)
        d.addCallback(self.checkPayloadHas,
                      {'id': None,
                       'indexed': True,
                       })
        d.addCallback(self.checkPayloadHasNot, ('description',))
        return d

    @base.showFailures
    @defer.inlineCallbacks
    def testUnknownArgument(self):
        badArgument = 'blah'
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        try:
            yield self.getPage(defaults.adminUsername, headers=headers,
                               queryDict={badArgument: True})
            self.assertFail("Should have returned a NOT FOUND (404) error")
        except wsfe_http.HTTPError, e:  # TODO: Use Twisted.web's own exception
            self.assertEquals(http.NOT_FOUND, int(e.status))

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
    def testNoArgumentValue(self):
        # Put returnDescription into the request payload, with a None
        # value. It should get its default value (False in this case).
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage('fluiddb/testing/test1', headers=headers,
                         queryDict={'returnDescription': None})
        d.addCallback(self.checkStatus, http.OK)
        d.addCallback(self.checkPayloadHas,
                      dict.fromkeys(['id', 'indexed']))
        d.addCallback(self.checkPayloadHasNot, ('description',))
        return d


class TestPUT(TagsTest):

    verb = 'PUT'

    @base.showFailures
    @defer.inlineCallbacks
    def testAsAdmin(self):
        name = 'test'
        parentPath = defaults.adminUsername
        path = defaults.sep.join([parentPath, name])
        yield self.createTag(name, parentPath)
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
            yield self.deleteTag(path)

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
#              error.NoContentLengthHeader.__name__})
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
            {buildHeader('Error-Class'): error.NoContentTypeHeader.__name__})
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
    def testRandomUserUpdatesAdmin(self):
        headers = {
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers, 'testuser1', 'secret')
        data = {
            'description': 'A totally new description.',
        }
        d = self.getPage('fluiddb/testing/test1', headers=headers,
                         postdata=json.dumps(data))
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testAnonUserUpdatesAdmin(self):
        headers = {
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(
            headers, defaults.anonUsername, defaults.anonPassword)
        data = {
            'description': 'Not a chance...',
        }
        d = self.getPage('fluiddb/testing/test1', headers=headers,
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
                d = self.getPage('whatever', headers=headers,
                                 postdata=json.dumps(data))
                d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
                d.addErrback(
                    self.checkErrorHeaders,
                    {buildHeader('Error-Class'):
                     error.InvalidPayloadField.__name__, })
                self.failUnlessFailure(d, Error)
                yield d


class TestDELETE(TagsTest):

    verb = 'DELETE'

    @base.showFailures
    def testNonExistent(self):
        d = self.deleteTag(
            defaults.sep.join([defaults.adminUsername, '_dummy_']))
        d.addErrback(self.checkErrorStatus, http.NOT_FOUND)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testRandomUserDeletesAdmin(self):
        d = self.deleteTag('fluiddb/testing/test1',
                           requesterUsername='testuser1',
                           requesterPassword='secret')
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testRandomUserDeletesRandomUser(self):
        d = self.deleteTag('testuser1/testing/test1',
                           requesterUsername='testuser2',
                           requesterPassword='secret')
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testAnonUserDeletesAbout(self):
        path = defaults.sep.join(paths.aboutPath())
        d = self.deleteTag(path,
                           requesterUsername=defaults.anonUsername,
                           requesterPassword=defaults.anonPassword)
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        return d
