# -*- coding: utf-8 -*-

import json
import urllib

from twisted.web import http
from twisted.web.error import Error
from twisted.internet import defer

from fluiddb.common import error, defaults, users
from fluiddb.common.types_thrift.ttypes import (
    TUsernameTooLong, TInvalidUsername)
from fluiddb.web.util import buildHeader

from integration.wsfe import base
from integration.wsfe.http import getPage, HTTPError
from integration import user


class UsersTest(base.HTTPTest):
    toplevel = defaults.httpUserCategoryName


class TestPOST(UsersTest):

    verb = 'POST'

    @base.showFailures
    def testUnicodeNames(self):
        return self.createRandomUser(username=u'\xf8', name=u'\xf8')

    @base.showFailures
    def testAsRandomUser(self):
        # Make sure a random user cannot create other users.
        d = self.createRandomUser(requesterUsername='testuser1',
                                  requesterPassword='secret')
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testDuplicateUser(self):
        d = self.createRandomUser(username='testuser1')
        d.addErrback(self.checkErrorStatus, http.PRECONDITION_FAILED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    @defer.inlineCallbacks
    def testUsernameCaseSensitive(self):
        d = self.createRandomUser(username='TESTUSER1')
        d.addErrback(self.checkErrorStatus, http.PRECONDITION_FAILED)
        self.failUnlessFailure(d, Error)
        yield d
        d = self.createRandomUser(username='Testuser1')
        d.addErrback(self.checkErrorStatus, http.PRECONDITION_FAILED)
        self.failUnlessFailure(d, Error)
        yield d

    @base.showFailures
    def testNameEmpty(self):
        name = ''
        d = self.createRandomUser(username=name)
        d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'): TInvalidUsername.__name__})
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testNameTooLong(self):
        name = (users.maxUsernameLength + 1) * 'x'
        d = self.createRandomUser(username=name)
        d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'): TUsernameTooLong.__name__})
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    @defer.inlineCallbacks
    def testStartWithPunc(self):
        for punc in '.-':
            for suffix in '', 'blah':
                username = punc + suffix
                u = yield self.createRandomUser(username=username)
                self.assertEquals(username, u.username)

    @base.showFailures
    @defer.inlineCallbacks
    def testBadTypes(self):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)

        for field in ('username', 'name', 'password', 'email'):
            data = {
                'username': 'new',
                'name': 'new',
                'password': 'pass',
                'email': 'email',
            }
            for value in (None, 3, 6.7, True, False, ['a', 'list'], {'x': 3}):
                data[field] = value
                d = self.getPage('', headers=headers,
                                 postdata=json.dumps(data))
                d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
                d.addErrback(
                    self.checkErrorHeaders,
                    {buildHeader('Error-Class'):
                     error.InvalidPayloadField.__name__})
                self.failUnlessFailure(d, Error)
                yield d


class TestGET(UsersTest):

    verb = 'GET'

    @base.showFailures
    def testNonexistentUser(self):
        u = user.RandomUser()
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage(u.username, headers=headers)
        d.addErrback(self.checkErrorStatus, http.NOT_FOUND)
        self.failUnlessFailure(d, Error)
        return d

    @defer.inlineCallbacks
    def testUnknownUser(self):
        import uuid
        username = str(uuid.uuid4())
        password = str(uuid.uuid4())
        uri = '%s/%s/%s' % (self.endpoint,
                            defaults.httpUserCategoryName,
                            defaults.adminUsername)

        headers = {}
        self.addBasicAuthHeader(headers, username=username, password=password)
        try:
            yield getPage(uri, headers=headers)
        except HTTPError, e:
            self.assertEqual(http.UNAUTHORIZED, int(e.status))
        else:
            self.fail("This shouldn't succeed, we passed "
                      "credentials for an unknown user")

    @base.showFailures
    def testAnonAuthorized(self):
        headers = {
            'accept': 'application/json',
        }
        d = self.getPage(defaults.adminUsername, headers=headers)
        d.addCallback(self.checkStatus, http.OK)
        d.addCallback(self.checkPayloadHas, {
            'name': defaults.adminName, 'id': None})
        return d

    @base.showFailures
    def testNoAcceptHeader(self):
        headers = {}
        self.addBasicAuthHeader(headers)
        d = self.getPage(defaults.adminUsername, headers=headers)
        d.addCallback(self.checkHeaders, {'content-type': 'application/json'})
        return d

    @base.showFailures
    def testBadPassword(self):
        # TODO: This raises an unhandled auth error in the wsfe. See its
        # log file for details. The test works, but I'd rather be catching
        # the exception in the wsfe to have a bit more control (and
        # understanding).
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers, defaults.adminUsername,
                                self.adminPassword + 'x')
        d = self.getPage(defaults.adminUsername, headers=headers)
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testAuthorized(self):
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage(defaults.adminUsername, headers=headers)
        d.addCallback(self.checkStatus, http.OK)
        d.addCallback(self.checkPayloadHas, {
            'name': defaults.adminName, 'id': None})
        return d

    @base.showFailures
    def testUnexpectedPayload(self):
        # Put rubbish into the payload to trigger an error.
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage(defaults.adminUsername, headers=headers, postdata='x')
        d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'):
             error.UnexpectedContentLengthHeader.__name__})
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testRandomUserGetsAdmin(self):
        # Make sure a random user can do a GET on the admin user.
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers, 'testuser1', 'secret')
        d = self.getPage(defaults.adminUsername, headers=headers)
        d.addCallback(self.checkStatus, http.OK)
        d.addCallback(self.checkPayloadHas,
                      {'name': defaults.adminName, 'id': None})
        return d

    @base.showFailures
    def testRandomUserGetsRandomUser(self):
        # Make sure a random user can do a GET on another random user.
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers, 'testuser1', 'secret')
        d = self.getPage('testuser2', headers=headers)
        d.addCallback(self.checkStatus, http.OK)
        d.addCallback(self.checkPayloadHas, {'name': 'Test user',
                                             'id': None})
        return d

    @base.showFailures
    @defer.inlineCallbacks
    def testGetUserWithUnicodeUsername(self):
        username = u'fernández'
        u = yield self.createRandomUser(username=username)
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers, u.username, u.password)
        d = self.getPage(urllib.quote(u.username.encode('utf-8')),
                         headers=headers)
        d.addCallback(self.checkStatus, http.OK)
        yield d

    @base.showFailures
    def testGetUserWithUnknownUnicodeUsername(self):
        """
        Getting a user that doesn't exist, with a unicode username, correctly
        returns an C{HTTP 400 Not Found} status and a C{X-FluidDB-Error-Class}
        header with a C{TNoSuchUser} value.
        """
        username = u'\N{HIRAGANA LETTER A}'
        headers = {'accept': 'application/json'}
        self.addBasicAuthHeader(headers)
        deferred = self.getPage(urllib.quote(username.encode('utf-8')),
                                headers=headers)
        deferred.addErrback(self.checkErrorStatus, http.NOT_FOUND)
        deferred.addErrback(self.checkErrorHeaders,
                            {buildHeader('Error-Class'): 'TNoSuchUser',
                             buildHeader('Name'): username.encode('utf-8')})
        return self.assertFailure(deferred, Error)

    @base.showFailures
    @defer.inlineCallbacks
    def testGetUserWithUnicodeName(self):
        u = yield self.createRandomUser(name=u'Dr. Unicode \xf8 !')
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers, u.username, u.password)
        d = self.getPage(u.username, headers=headers)
        d.addCallback(self.checkStatus, http.OK)
        d.addCallback(self.checkPayloadHas,
                      {'name': u.name, 'id': None})
        yield d


class TestPUT(UsersTest):

    verb = 'PUT'

    @base.showFailures
    def testNonexistentUser(self):
        u = user.RandomUser()
        headers = {
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        data = {
            'name': 'Totally Bogus',
            'email': 'bogus@bogus.org',
        }
        d = self.getPage(u.username, headers=headers,
                         postdata=json.dumps(data))
        d.addErrback(self.checkErrorStatus, http.NOT_FOUND)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    @defer.inlineCallbacks
    def testAdminChangesSelf(self):
        newName = 'Joe the plumber'
        headers = {
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        data = {
            'name': newName,
            'email': 'joe@mccain.org',
        }
        d = self.getPage(defaults.adminUsername, headers=headers,
                         postdata=json.dumps(data))
        d.addCallback(self.checkStatus, http.NO_CONTENT)
        d.addCallback(self.checkUserDetails, defaults.adminUsername, newName)
        yield d

        # Change them back (other tests also examine these tags/values on
        # the admin user).
        data = {
            'name': defaults.adminName,
            'email': defaults.adminEmail,
        }
        d = self.getPage(defaults.adminUsername, headers=headers,
                         postdata=json.dumps(data))
        d.addCallback(self.checkStatus, http.NO_CONTENT)
        d.addCallback(self.checkUserDetails, defaults.adminUsername,
                      defaults.adminName)
        yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testAdminChangesRandomUser(self):
        newName = 'Heffalump'
        headers = {
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        data = {
            'name': newName,
            'email': 'heff@address.org',
        }
        d = self.getPage('testuser1', headers=headers,
                         postdata=json.dumps(data))
        d.addCallback(self.checkStatus, http.NO_CONTENT)
        d.addCallback(self.checkUserDetails, 'testuser1', newName)
        yield d
        # Restore the values used by prepare-for-testing.py
        data = {
            'name': 'Test user',
            'email': 'testuser@example.com',
        }
        d = self.getPage('testuser1', headers=headers,
                         postdata=json.dumps(data))
        yield d

    @base.showFailures
    def testRandomUserChangesAdmin(self):
        headers = {
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers, 'testuser1', 'secret')
        data = {
            'name': 'Evil new name',
            'email': 'new@email.org',
        }
        d = self.getPage(defaults.adminUsername, headers=headers,
                         postdata=json.dumps(data))
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testNoContentType(self):
        headers = {}
        self.addBasicAuthHeader(headers)
        data = {
            'name': 'Joe the plumber',
            'email': 'joe@mccain.org',
        }
        d = self.getPage(defaults.adminUsername, headers=headers,
                         postdata=json.dumps(data))
        d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'): error.NoContentTypeHeader.__name__})
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testUnknownPayloadType(self):
        headers = {
            'content-type': 'application/WTF',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage(defaults.adminUsername, headers=headers, postdata='x')
        d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'): error.UnknownContentType.__name__})
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testUnknownPayloadField(self):
        headers = {
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        data = {
            'dummy': 'A dummy value',
            'name': 'Joe the plumber',
            'email': 'joe@mccain.org',
        }
        d = self.getPage(defaults.adminUsername, headers=headers,
                         postdata=json.dumps(data))
        d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'): error.UnknownPayloadField.__name__,
             buildHeader('fieldName'): 'dummy'})
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    @defer.inlineCallbacks
    def testEmptyOrNoPayload(self):
        # All args are optional in a PUT /users/USERID, so a missing
        # payload is just fine. Nothing will be done.
        headers = {}
        self.addBasicAuthHeader(headers)
        for data in ('', None):
            d = self.getPage(defaults.adminUsername, headers=headers,
                             postdata=data)
            d.addCallback(self.checkStatus, http.NO_CONTENT)
            yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testBadTypes(self):
        headers = {
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)

        for field in ('name', 'password', 'email'):
            data = {
                'name': 'new',
                'password': 'pass',
                'email': 'email',
            }
            for value in (None, 3, 6.7, True, False, ['a', 'list'], {'x': 3}):
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


class TestDELETE(UsersTest):

    verb = 'DELETE'

    @base.showFailures
    def testNonexistentUser(self):
        u = user.RandomUser()
        headers = {}
        self.addBasicAuthHeader(headers)
        d = self.getPage(u.username, headers=headers)
        d.addErrback(self.checkErrorStatus, http.NOT_FOUND)
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    @defer.inlineCallbacks
    def testRandomUserDeletesRandomUser(self):
        # Make sure a random user cannot delete other users.
        headers = {}
        self.addBasicAuthHeader(headers, 'testuser1', 'secret')

        # Check that the first cannot delete themself.
        d = self.getPage('testuser1', headers=headers)
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        yield d

        # Check that the first cannot delete the second.
        d = self.getPage('testuser2', headers=headers)
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        yield d
