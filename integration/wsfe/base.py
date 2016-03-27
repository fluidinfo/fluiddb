import functools
import json
import os
import urllib
import uuid
import types
from base64 import b64encode
from datetime import datetime

from twisted.internet import defer
from twisted.python import log
from twisted.web import error, http as txHttp

from fluiddb.common import defaults
from fluiddb.testing.basic import FluidinfoTestCase

from integration.wsfe import http
from integration import user

# This is the same dict that's used to get primitive types back to us in
# wsfe/service/web/objects.py. It's reproduced here to be independent of
# that code.
_primitiveTypeSerializer = {
    defaults.contentTypeForPrimitiveJSON: json.dumps,
}

_primitiveTypeDeserializer = {
    defaults.contentTypeForPrimitiveJSON: json.loads,
}

# The following produces object ids that can never be produced by FluidDB
# as they're not in version 4 format (they have a 0 instead of a 4 at the
# start of the third digit group). So we're guaranteed these object ids can
# never exist. See http://en.wikipedia.org/wiki/UUID#Version_4_.28random.29


def randomObjectIdStr():
    return str(uuid.uuid4())


def nonType4ObjectIdStr():
    ok = str(uuid.uuid4())
    return ok[:14] + '0' + ok[15:]


def showFailures(f):

    @functools.wraps(f)
    def wrapper(self):
        d = defer.maybeDeferred(f, self)
        d.addErrback(self.showFailure)
        return d
    return wrapper


def _addBasicAuthHeader(d, username, password):
    d['Authorization'] = 'Basic %s' % b64encode(
        '%s:%s' % (username.encode('utf-8'), password))


class HTTPTest(FluidinfoTestCase):
    """
    Support for making HTTP calls to FluidDB.

    NOTE: This class is scheduled to go away. Please do not add to it.
    """
    toplevel = None  # Must be set in subclasses.
    verb = None  # Must be set in subclasses.

    def setUp(self):
        self.endpoint = os.environ.get('FLUIDDB_ENDPOINT',
                                       'http://localhost:9000')
        self.adminUsername = os.environ.get('FLUIDDB_ADMIN_USERNAME',
                                            'fluiddb')
        self.adminPassword = os.environ.get('FLUIDDB_ADMIN_PASSWORD', 'secret')
        self.users = []
        self.persistentUsers = []

    def tearDown(self):
        return defer.gatherResults([u.delete()
                                    for u in self.users
                                    if u not in self.persistentUsers])

    def addBasicAuthHeader(self, d, username=None, password=None):
        if username is None:
            username = defaults.adminUsername
            password = self.adminPassword
        _addBasicAuthHeader(d, username, password)

    def checkStatus(self, result, expected):
        status = result[0]
        self.assertEqual(status, str(expected))
        return result

    def checkErrorStatus(self, failure, expected):
        if hasattr(failure.value, 'status'):
            if failure.value.status != str(expected):
                self.showFailure(failure)
                self.assertEqual(failure.value.status, str(expected))
        return failure

    def _checkHeadersDictHas(self, expected, headers):
        for key, value in expected.items():
            key = key.lower()
            self.assertTrue(key in headers,
                            '%r missing from headers %r' % (key, headers))
            if value is not None:
                self.assertEqual(
                    [value], headers[key],
                    'headers key %r value %r != expected value %r' %
                    (key, headers[key], value))

    def _checkDictHas(self, expected, dictionary):
        for key, value in expected.items():
            self.assertTrue(
                key in dictionary,
                '%r missing from dictionary %r' % (key, dictionary))
            if value is not None:
                self.assertEqual(
                    value, dictionary[key],
                    'dictionary key %r value %r != expected value %r' %
                    (key, dictionary[key], value))

    def _checkDictHasNot(self, unexpected, dictionary):
        for key in unexpected:
            self.assertFalse(
                key in dictionary,
                '%s unexpectedly found in dictionary %r' % (key, dictionary))

    def checkHeaders(self, result, expected):
        headers = result[1]
        for key, value in expected.items():
            self.assertTrue(key in headers,
                            '%s missing from headers %r' % (key, headers))
            if value is not None:
                self.assertEqual(value, headers[key][0])
        return result

    def checkLastModifiedHeader(self, result):
        headers = result[1]
        # this test should never fail, but it may error since
        # datetime.strptime raises a C{ValueError} if it can't parse
        # the string
        self.assertEqual(
            datetime, type(datetime.strptime(headers['last-modified'][0],
                                             '%a, %d %b %Y %H:%M:%S')))
        return result

    def checkPayloadHas(self, result, expected):
        headers, payload = result[1:3]
        self.assertTrue('content-type' in headers)
        self.assertEqual(headers['content-type'][0], 'application/json')
        self.assertTrue('content-length' in headers)
        self.assertEqual(int(headers['content-length'][0]), len(payload))
        dictionary = json.loads(payload)
        self._checkDictHas(expected, dictionary)
        return result

    def checkPayloadHasNot(self, result, unexpected):
        headers, payload = result[1:3]
        self.assertTrue('content-type' in headers)
        self.assertEqual(headers['content-type'][0], 'application/json')
        self.assertTrue('content-length' in headers)
        self.assertEqual(int(headers['content-length'][0]), len(payload))
        dictionary = json.loads(payload)
        self._checkDictHasNot(unexpected, dictionary)
        return result

    def checkNoPayload(self, result):
        headers, payload = result[1:3]
        self.assertTrue('content-length' not in headers)
        self.assertEqual(payload, '')
        return result

    def checkErrorHeaders(self, failure, expected):
        if not hasattr(failure.value, 'response'):
            log.msg('Failure with no response: %s' % failure)
            return failure
        self.assertTrue(failure.value.response is not None)

        # The following test that there's no content isn't needed any more
        # I don't think, and it prevents us from checking bad requests that
        # end up with Twisted.web sending some probably useful HTML (e.g.,
        # that a page is forbidden or a resource can't be found). Let's just
        # log it for now (log output appears in _trial_temp/test.log)
        # self.assertEquals(0, len(failure.value.response))
        if len(failure.value.response):
            log.msg('Response: %r.' % failure.value.response)

        headers = failure.value.response_headers
        self._checkHeadersDictHas(expected, headers)
        return failure

    def _checkFluidDBErrorHeaders(self, failure):
        # For now we don't put X-Fluiddb-Error-Class or
        # X-Fluiddb-Request-Id headers in response to auth failure (twisted
        # web doesn't make that easy). In all other cases, we add them.
        # Here we check they're present.
        if (failure.value.status == str(txHttp.UNAUTHORIZED)
                and 'www-authenticate' in failure.value.response_headers):
            return failure
        else:
            return self.checkErrorHeaders(
                failure, dict.fromkeys(['x-fluiddb-error-class',
                                        'x-fluiddb-request-id']))

    def showFailure(self, failure):
        failure.trap(http.HTTPError, error.Error)
        value = failure.value
        log.msg('FAILURE: Status=%r Response=%r' % (
            value.status, value.response))
        if hasattr(failure.value, 'response_headers'):
            headers = failure.value.response_headers
            for header in headers:
                if header.startswith('x-fluiddb'):
                    log.msg('Failure response header: %s: %s' % (
                        header, headers[header]))
        return failure

    def getPage(self, URISuffix='', queryDict=None, *args, **kw):
        if URISuffix and not URISuffix.startswith('/'):
            URISuffix = '/' + URISuffix
        if 'method' not in kw:
            kw['method'] = self.verb
        if queryDict is None:
            query = ''
        else:
            qlist = []
            for k, v in queryDict.items():
                kStr = urllib.quote_plus(str(k))
                if v is None:
                    qlist.append(kStr)
                elif isinstance(v, (types.ListType, types.TupleType)):
                    for val in v:
                        qlist.append(
                            '%s=%s' % (kStr, urllib.quote_plus(str(val))))
                else:
                    qlist.append('%s=%s' % (kStr, urllib.quote_plus(str(v))))
            query = '?' + '&'.join(qlist)

        uri = '%s/%s%s%s' % (self.endpoint, self.toplevel, URISuffix, query)
        d = http.getPage(uri, *args, **kw)

#       TODO: We're not checking error headers because nginx doesn't send them.
#       Uncomment this line as soon as we fix that. See bug #676940.
#       d.addErrback(self._checkFluidDBErrorHeaders)
        return d

    def createRandomUser(self, username=None, password=None,
                         name=None, email=None, persistent=False,
                         requesterUsername=None, requesterPassword=None):
        u = RandomUser(self.endpoint, self.adminUsername, self.adminPassword,
                       username, password, name, email)

        def _cb((status, headers, page)):
            self.users.append(u)
            if persistent:
                self.persistentUsers.append(u)
            return u

        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers, requesterUsername, requesterPassword)

        data = {
            'username': u.username,
            'name': u.name,
            'password': u.password,
            'email': u.email,
        }
        d = http.getPage(
            '%s/%s' % (self.endpoint,
                       defaults.httpUserCategoryName),
            headers=headers, method='POST', postdata=json.dumps(data))
        d.addCallback(self.checkStatus, txHttp.CREATED)
        d.addCallback(self.checkPayloadHas, dict.fromkeys(['id', 'URI']))
        d.addCallback(self.checkHeaders, dict.fromkeys(['content-length',
                                                        'location']))
        d.addCallback(_cb)

        # This is a nasty hack to always delete the <username>/private
        # namespace created for new users.  Not doing this causes (weird)
        # breakage that spreads through the integration tests.
        def removePrivateNamespace(user):

            def deleted(ignored):
                return user

            deferred = self.deleteNamespace('/'.join([u.username, 'private']))
            return deferred.addCallback(deleted)

        d.addCallback(removePrivateNamespace)
        return d

    def checkUserDetails(self, ign, username, name):
        """A callback that checks that doing a GET on username results in a
        payload with the passed values of name. This is used to (partly)
        check that a PUT or POST has done its job properly."""
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)

        d = http.getPage(
            '%s/%s/%s' % (self.endpoint,
                          defaults.httpUserCategoryName,
                          urllib.quote(username.encode('utf-8'))),
            headers=headers, method='GET')
        d.addCallback(self.checkStatus, txHttp.OK)
        d.addCallback(self.checkPayloadHas, {'name': name, 'id': None})
        return d

    def createNamespace(self, name, parentPath, description='',
                        requesterUsername=None, requesterPassword=None):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers, requesterUsername, requesterPassword)

        data = {
            'name': name,
            'description': description,
        }
        d = http.getPage(
            '%s/%s/%s' % (self.endpoint,
                          defaults.httpNamespaceCategoryName,
                          urllib.quote(parentPath.encode('utf-8'))),
            headers=headers, method='POST', postdata=json.dumps(data))
        d.addCallback(self.checkStatus, txHttp.CREATED)
        d.addCallback(self.checkPayloadHas, dict.fromkeys(['id', 'URI']))
        d.addCallback(self.checkHeaders, dict.fromkeys(['content-length',
                                                        'location']))
        return d

    def deleteNamespace(self, path,
                        requesterUsername=None, requesterPassword=None):
        headers = {}
        self.addBasicAuthHeader(headers, requesterUsername, requesterPassword)

        d = http.getPage(
            '%s/%s/%s' % (self.endpoint,
                          defaults.httpNamespaceCategoryName,
                          urllib.quote(path.encode('utf-8'))),
            headers=headers, method='DELETE')
        d.addCallback(self.checkStatus, txHttp.NO_CONTENT)
        d.addCallback(self.checkNoPayload)
        return d

    def createTag(self, name, parentPath, description='', indexed=False,
                  requesterUsername=None, requesterPassword=None):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers, requesterUsername, requesterPassword)

        data = {
            'name': name,
            'description': description,
            'indexed': indexed,
        }
        d = http.getPage(
            '%s/%s/%s' % (self.endpoint,
                          defaults.httpTagCategoryName,
                          urllib.quote(parentPath.encode('utf-8'))),
            headers=headers, method='POST', postdata=json.dumps(data))
        d.addCallback(self.checkStatus, txHttp.CREATED)
        d.addCallback(self.checkPayloadHas, dict.fromkeys(['id', 'URI']))
        d.addCallback(self.checkHeaders, dict.fromkeys(['content-length',
                                                        'location']))
        return d

    def deleteTag(self, path,
                  requesterUsername=None, requesterPassword=None):
        headers = {}
        self.addBasicAuthHeader(headers, requesterUsername, requesterPassword)

        d = http.getPage(
            '%s/%s/%s' % (self.endpoint,
                          defaults.httpTagCategoryName,
                          urllib.quote(path.encode('utf-8'))),
            headers=headers, method='DELETE')
        d.addCallback(self.checkStatus, txHttp.NO_CONTENT)
        d.addCallback(self.checkNoPayload)
        return d

    @defer.inlineCallbacks
    def getPermissions(self, path, action,
                       requesterUsername=None, requesterPassword=None):
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers, requesterUsername, requesterPassword)
        d = http.getPage(
            '%s/%s/%s?action=%s' % (self.endpoint,
                                    defaults.httpPermissionCategoryName,
                                    urllib.quote(path.encode('utf-8')),
                                    urllib.quote_plus(action)),
            headers=headers, method='GET')
        d.addCallback(self.checkStatus, txHttp.OK)
        d.addCallback(self.checkPayloadHas,
                      dict.fromkeys(['policy', 'exceptions']))
        result = yield d
        payload = result[2]
        dictionary = json.loads(payload)
        defer.returnValue((dictionary['policy'], dictionary['exceptions']))

    def updatePermissions(self, path, action, policy, exceptions,
                          requesterUsername=None, requesterPassword=None):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers, requesterUsername, requesterPassword)
        data = {
            'policy': policy,
            'exceptions': exceptions,
        }
        d = http.getPage(
            '%s/%s/%s?action=%s' % (self.endpoint,
                                    defaults.httpPermissionCategoryName,
                                    urllib.quote(path.encode('utf-8')),
                                    urllib.quote_plus(action)),
            headers=headers, postdata=json.dumps(data),
            method='PUT')
        d.addCallback(self.checkStatus, txHttp.NO_CONTENT)
        d.addCallback(self.checkNoPayload)
        return d

    @defer.inlineCallbacks
    def getPolicy(self, username, category, action,
                  requesterUsername=None, requesterPassword=None):
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers, requesterUsername, requesterPassword)

        path = '%s/%s/%s/%s/%s' % (
            self.endpoint,
            defaults.httpPolicyCategoryName,
            urllib.quote(username.encode('utf-8')),
            urllib.quote(category.encode('utf-8')),
            urllib.quote(action.encode('utf-8')))
        d = http.getPage(path, headers=headers, method='GET')
        d.addCallback(self.checkStatus, txHttp.OK)
        d.addCallback(self.checkPayloadHas, dict.fromkeys(['policy',
                                                           'exceptions']))
        result = yield d
        payload = result[2]
        dictionary = json.loads(payload)
        defer.returnValue((dictionary['policy'], dictionary['exceptions']))

    def updatePolicy(self, username, category, action, policy, exceptions,
                     requesterUsername=None, requesterPassword=None):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers, requesterUsername, requesterPassword)
        data = {
            'policy': policy,
            'exceptions': exceptions,
        }

        path = '%s/%s/%s/%s/%s' % (
            self.endpoint,
            defaults.httpPolicyCategoryName,
            urllib.quote(username.encode('utf-8')),
            urllib.quote(category.encode('utf-8')),
            urllib.quote(action.encode('utf-8')))
        d = http.getPage(path, headers=headers, method='PUT',
                         postdata=json.dumps(data))
        d.addCallback(self.checkStatus, txHttp.NO_CONTENT)
        d.addCallback(self.checkNoPayload)
        return d

    @defer.inlineCallbacks
    def getObject(self, objectId, showAbout=False,
                  requesterUsername=None, requesterPassword=None,
                  omitShowAboutInURI=False, accept=None):
        accept = accept or 'application/json'
        headers = {
            'accept': accept,
        }
        self.addBasicAuthHeader(headers, requesterUsername, requesterPassword)

        uri = '%s/%s/%s' % (self.endpoint,
                            defaults.httpObjectCategoryName, objectId)

        # omitShowAboutInURI can be used to have the request go with no
        # showAbout arg in the URI. That lets us test the default case.
        if not omitShowAboutInURI:
            uri += '?showAbout=%s' % showAbout

        d = http.getPage(uri, headers=headers)
        d.addCallback(self.checkStatus, txHttp.OK)
        expectedFields = ['tagPaths']
        if showAbout:
            expectedFields.append('about')
        else:
            d.addCallback(self.checkPayloadHasNot, ['about'])
        d.addCallback(self.checkPayloadHas, dict.fromkeys(expectedFields))
        result = yield d
        payload = result[2]
        dictionary = json.loads(payload)
        defer.returnValue(dictionary)

    @defer.inlineCallbacks
    def query(self, query, requesterUsername=None, requesterPassword=None):
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers, requesterUsername, requesterPassword)
        d = http.getPage(
            '%s/%s?query=%s' % (self.endpoint,
                                defaults.httpObjectCategoryName,
                                urllib.quote(query.encode('utf-8'))),
            headers=headers, method='GET')
        d.addCallback(self.checkStatus, txHttp.OK)
        d.addCallback(self.checkPayloadHas, dict.fromkeys(['ids']))
        result = yield d
        payload = result[2]
        dictionary = json.loads(payload)
        defer.returnValue(dictionary['ids'])

    def setTagValue(self, path, objectId, value,
                    contentType=defaults.contentTypeForPrimitiveJSON,
                    requesterUsername=None, requesterPassword=None):

        uri = '%s/%s/%s/%s' % (
            self.endpoint,
            defaults.httpObjectCategoryName, str(objectId),
            urllib.quote(path.encode('utf-8')))

        headers = {'content-type': contentType}
        self.addBasicAuthHeader(headers, requesterUsername, requesterPassword)

        try:
            serializer = _primitiveTypeSerializer[contentType]
        except KeyError:
            payload = value
        else:
            payload = serializer(value)

        d = http.getPage(uri, headers=headers, method='PUT', postdata=payload)
        d.addCallback(self.checkStatus, txHttp.NO_CONTENT)
        return d

    def getTagValueGeneral(self, path, objectId, accept='*/*',
                           requesterUsername=None, requesterPassword=None):
        headers = {}
        self.addBasicAuthHeader(headers, requesterUsername, requesterPassword)

        if accept is not None:
            headers['accept'] = accept

        uri = '%s/%s/%s/%s' % (
            self.endpoint,
            defaults.httpObjectCategoryName, str(objectId), path)

        d = http.getPage(uri, headers=headers)
        d.addCallback(self.checkStatus, txHttp.OK)
        d.addCallback(self.checkHeaders, {'content-type': None,
                                          'last-modified': None})
        d.addCallback(self.checkLastModifiedHeader)
        return d

    @defer.inlineCallbacks
    def getTagValue(self, path, objectId, accept='*/*',
                    requesterUsername=None, requesterPassword=None):
        d = self.getTagValueGeneral(path, objectId, accept,
                                    requesterUsername=requesterUsername,
                                    requesterPassword=requesterPassword)
        result = yield d
        headers, payload = result[1:3]
        contentType = headers['content-type'][0]
        defer.returnValue(_primitiveTypeDeserializer[contentType](payload))

    @defer.inlineCallbacks
    def getTagValueAndContentType(self, path, objectId, accept='*/*',
                                  requesterUsername=None,
                                  requesterPassword=None):
        d = self.getTagValueGeneral(path, objectId, accept,
                                    requesterUsername=requesterUsername,
                                    requesterPassword=requesterPassword)
        result = yield d
        headers, payload = result[1:3]
        contentType = headers['content-type'][0]
        defer.returnValue((payload, contentType))

    def hasTagValue(self, path, objectId,
                    requesterUsername=None, requesterPassword=None):
        headers = {}
        self.addBasicAuthHeader(headers, requesterUsername, requesterPassword)
        uri = '%s/%s/%s/%s' % (self.endpoint,
                               defaults.httpObjectCategoryName,
                               str(objectId), path)

        d = http.getPage(uri, headers=headers, method='HEAD')

        def checkPayloadEmpty(result):
            self.assertEqual(result[2], '')
            return result

        def has(result):
            self.checkHeaders(
                result,
                dict.fromkeys(['content-type', 'content-length']))
            status = result[0]
            self.assertEqual(status, str(txHttp.OK))
            return True

        def hasnot(failure):
            if failure.value.status == str(txHttp.NOT_FOUND):
                return False
            else:
                return failure

        d.addCallback(checkPayloadEmpty)
        d.addCallbacks(has, hasnot)
        return d

    def deleteTagValue(self, path, objectId,
                       requesterUsername=None, requesterPassword=None):
        headers = {}
        self.addBasicAuthHeader(headers, requesterUsername, requesterPassword)
        uri = '%s/%s/%s/%s' % (self.endpoint,
                               defaults.httpObjectCategoryName,
                               str(objectId), path)

        d = http.getPage(uri, headers=headers, method='DELETE')
        d.addCallback(self.checkStatus, txHttp.NO_CONTENT)
        return d


class RandomUser(user.RandomUser):

    def __init__(self, endpoint, adminUsername, adminPassword,
                 username=None, password=None, name=None, email=None):
        super(RandomUser, self).__init__(username, password, name, email)
        self.endpoint = endpoint
        self.adminUsername = adminUsername
        self.adminPassword = adminPassword
        self.deleted = False

    def delete(self, requesterUsername=None, requesterPassword=None):
        if self.deleted:
            return defer.succeed(None)
        else:
            self.deleted = True

            def _cb((status, headers, page)):
                assert status == str(txHttp.NO_CONTENT)

            requesterUsername = requesterUsername or self.adminUsername
            requesterPassword = requesterPassword or self.adminPassword

            headers = {}
            _addBasicAuthHeader(headers, requesterUsername, requesterPassword)

            d = http.getPage(
                '%s/%s/%s' % (self.endpoint,
                              defaults.httpUserCategoryName,
                              urllib.quote(self.username.encode('utf-8'))),
                headers=headers, method='DELETE')
            d.addCallback(_cb)
            return d
