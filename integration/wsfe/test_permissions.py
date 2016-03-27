# -*- coding: utf-8 -*-

import json

from twisted.web import http
from twisted.web.error import Error
from twisted.internet import defer

from fluiddb.common import error, defaults, permissions
from fluiddb.common import paths
from integration.wsfe import base
from fluiddb.common.types_thrift.ttypes import TInvalidPolicy
from fluiddb.web.util import buildHeader


def _printActionPolicyExceptions(result, action):
    # This function is currently unused. It's useful as a callback to see
    # what's returned from a GET.
    payload = result[2]
    d = json.loads(payload)
    print 'action %s, policy %s, exceptions %r' % (
        action, d['policy'], d['exceptions'])
    return result


class PermissionsTest(base.HTTPTest):
    toplevel = defaults.httpPermissionCategoryName


class TestPOST(PermissionsTest):

    verb = 'POST'

    @base.showFailures
    def testNotFound(self):
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage('dummy', headers=headers)
        d.addErrback(self.checkErrorStatus, http.NOT_FOUND)
        self.failUnlessFailure(d, Error)
        return d


class TestGET(PermissionsTest):

    verb = 'GET'

    @base.showFailures
    @defer.inlineCallbacks
    def testTopLevelAdminNamespace(self):
        path = defaults.sep.join([defaults.namespaceCategoryName,
                                  defaults.adminUsername])
        for action in permissions.actionsByCategory[
                defaults.namespaceCategoryName]:
            policy, exceptions = yield self.getPermissions(path, action)
            self.assertEqual(policy, permissions.CLOSED)
            self.assertEqual(exceptions, [])

    @base.showFailures
    @defer.inlineCallbacks
    def testMissingAction(self):
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        path = defaults.sep.join([defaults.namespaceCategoryName,
                                  defaults.adminUsername])
        d = self.getPage(path, headers=headers)
        d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
        self.failUnlessFailure(d, Error)
        yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testAboutTag(self):
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        path = defaults.sep.join([defaults.tagCategoryName] +
                                 paths.aboutPath())
        for action in permissions.actionsByCategory[
                defaults.tagCategoryName]:
            d = self.getPage(path, headers=headers,
                             queryDict={'action': action})
            d.addCallback(self.checkStatus, http.OK)
            d.addCallback(self.checkPayloadHas, {
                'policy': permissions.CLOSED,
                'exceptions': []})
            yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testAboutTagInstances(self):
        # The about tag has an open policy for READ, and closed policies
        # for all else.
        openPolicyActions = (permissions.READ,)
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        path = defaults.sep.join([defaults.tagInstanceSetCategoryName] +
                                 paths.aboutPath())
        for action in permissions.actionsByCategory[
                defaults.tagInstanceSetCategoryName]:
            d = self.getPage(path, headers=headers,
                             queryDict={'action': action})
            d.addCallback(self.checkStatus, http.OK)
            d.addCallback(self.checkPayloadHas, {
                'policy': (permissions.OPEN if action in openPolicyActions
                           else permissions.CLOSED),
                'exceptions': []})
            yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testAllBadActions(self):
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        for category, path in (
            (defaults.namespaceCategoryName,
             [defaults.namespaceCategoryName, defaults.adminUsername]),

            (defaults.tagCategoryName,
             [defaults.tagCategoryName] + paths.aboutPath()),

            (defaults.tagInstanceSetCategoryName,
             [defaults.tagInstanceSetCategoryName] + paths.aboutPath())):

            path = defaults.sep.join(path)
            allowedActions = permissions.actionsByCategory[category]

            for action in list(permissions.allActions) + ['unknown-action']:
                if action not in allowedActions:
                    # We provide 'create' to maintain backwards compatibility.
                    # In order to make it work here we break lots of other
                    # things.  This is the path of least resistance. -jkakar
                    if (path == 'tag-values/fluiddb/about'
                            and action == 'create'):
                        continue
                    d = self.getPage(path, headers=headers,
                                     queryDict={'action': action})
                    d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
                    self.failUnlessFailure(d, Error)
                    yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testRandomUserCannotGETAdminTopLevel(self):
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers, 'testuser1', 'secret')
        path = defaults.sep.join([defaults.namespaceCategoryName,
                                  defaults.adminUsername])
        for action in \
                permissions.actionsByCategory[defaults.namespaceCategoryName]:
            d = self.getPage(path, headers=headers,
                             queryDict={'action': action})
            d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
            self.failUnlessFailure(d, Error)
            yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testRandomUserCanGETTheirTopLevelNamespace(self):
        openPolicyActions = (permissions.LIST,)
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers, 'testuser1', 'secret')
        path = defaults.sep.join([defaults.namespaceCategoryName,
                                  'testuser1'])
        for action in permissions.actionsByCategory[
                defaults.namespaceCategoryName]:
            d = self.getPage(path, headers=headers,
                             queryDict={'action': action})
            d.addCallback(self.checkStatus, http.OK)
            if action in openPolicyActions:
                d.addCallback(self.checkPayloadHas, {
                    'policy': permissions.OPEN,
                    'exceptions': []})
            else:
                d.addCallback(self.checkPayloadHas, {
                    'policy': permissions.CLOSED,
                    'exceptions': ['testuser1']})
            yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testRandomUserCanGETSubNamespace(self):
        openPolicyActions = (permissions.LIST,)
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers, 'testuser1', 'secret')
        path = defaults.sep.join([defaults.namespaceCategoryName,
                                  'testuser1', 'testing'])
        for action in permissions.actionsByCategory[
                defaults.namespaceCategoryName]:
            d = self.getPage(path, headers=headers,
                             queryDict={'action': action})
            d.addCallback(self.checkStatus, http.OK)
            if action in openPolicyActions:
                d.addCallback(self.checkPayloadHas, {
                    'policy': permissions.OPEN,
                    'exceptions': []})
            else:
                d.addCallback(self.checkPayloadHas, {
                    'policy': permissions.CLOSED,
                    'exceptions': ['testuser1']})
            yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testRandomUserCannotGETRandomUserTopLevelNamespace(self):
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers, 'testuser2', 'secret')
        path = defaults.sep.join([defaults.namespaceCategoryName,
                                  'testuser1'])
        for action in permissions.actionsByCategory[
                defaults.namespaceCategoryName]:
            d = self.getPage(path, headers=headers,
                             queryDict={'action': action})
            d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
            self.failUnlessFailure(d, Error)
            yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testRandomUserCannotGETRandomUserSubNamespace(self):
        """
        testuser1 has a 'testing' sub-namespace, testuser2 tries to see its
        permissions but fails.
        """
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers, 'testuser2', 'secret')
        path = defaults.sep.join([defaults.namespaceCategoryName,
                                  'testuser1', 'testing'])
        for action in permissions.actionsByCategory[
                defaults.namespaceCategoryName]:
            d = self.getPage(path, headers=headers,
                             queryDict={'action': action})
            d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
            self.failUnlessFailure(d, Error)
            yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testRandomUserCanGETTag(self):
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers, 'testuser1', 'secret')
        path = defaults.sep.join(
            [defaults.tagCategoryName, 'testuser1', 'testing', 'test1'])
        for action in permissions.actionsByCategory[
                defaults.tagCategoryName]:
            d = self.getPage(path, headers=headers,
                             queryDict={'action': action})
            d.addCallback(self.checkStatus, http.OK)
            d.addCallback(self.checkPayloadHas, {
                'policy': permissions.CLOSED,
                'exceptions': ['testuser1']})
            yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testRandomUserCanGETTagInstances(self):
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers, 'testuser1', 'secret')
        openPolicyActions = (permissions.READ,)
        path = defaults.sep.join(
            [defaults.tagInstanceSetCategoryName,
             'testuser1', 'testing', 'test1'])
        for action in permissions.actionsByCategory[
                defaults.tagInstanceSetCategoryName]:
            d = self.getPage(path, headers=headers,
                             queryDict={'action': action})
            d.addCallback(self.checkStatus, http.OK)
            if action in openPolicyActions:
                d.addCallback(self.checkPayloadHas, {
                    'policy': permissions.OPEN,
                    'exceptions': []})
            else:
                d.addCallback(self.checkPayloadHas, {
                    'policy': permissions.CLOSED,
                    'exceptions': ['testuser1']})
            yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testRandomUserCannotGETRandomUserTag(self):
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers, 'testuser2', 'secret')
        path = defaults.sep.join(
            [defaults.tagCategoryName, 'testuser1', 'testing', 'test1'])
        for action in permissions.actionsByCategory[
                defaults.tagCategoryName]:
            d = self.getPage(path, headers=headers,
                             queryDict={'action': action})
            d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
            self.failUnlessFailure(d, Error)
            yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testRandomUserCannotGETRandomUserTagInstances(self):
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers, 'testuser2', 'secret')
        path = defaults.sep.join(
            [defaults.tagInstanceSetCategoryName,
             'testuser1', 'testing', 'test1'])
        for action in permissions.actionsByCategory[
                defaults.tagInstanceSetCategoryName]:
            d = self.getPage(path, headers=headers,
                             queryDict={'action': action})
            d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
            self.failUnlessFailure(d, Error)
            yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testAnonUserCannotGETSelf(self):
        headers = {
            'accept': 'application/json',
        }
        path = defaults.sep.join([defaults.namespaceCategoryName,
                                  defaults.anonUsername])
        for action in \
                permissions.actionsByCategory[defaults.namespaceCategoryName]:
            d = self.getPage(path, headers=headers,
                             queryDict={'action': action})
            d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
            self.failUnlessFailure(d, Error)
            yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testAnonUserCannotGETAdminNamespaceOrAbout(self):
        headers = {
            'accept': 'application/json',
        }
        # Test the admin namespace
        path = defaults.sep.join([defaults.namespaceCategoryName,
                                  defaults.adminUsername])
        for action in \
                permissions.actionsByCategory[defaults.namespaceCategoryName]:
            d = self.getPage(path, headers=headers,
                             queryDict={'action': action})
            d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
            self.failUnlessFailure(d, Error)
            yield d

        # Test the about tag.
        path = defaults.sep.join([defaults.tagCategoryName] +
                                 paths.aboutPath())
        for action in permissions.actionsByCategory[
                defaults.tagCategoryName]:
            d = self.getPage(path, headers=headers,
                             queryDict={'action': action})
            d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
            self.failUnlessFailure(d, Error)
            yield d

        # Test the about tag instances.
        path = defaults.sep.join([defaults.tagInstanceSetCategoryName] +
                                 paths.aboutPath())
        for action in (permissions.actionsByCategory[
                defaults.tagInstanceSetCategoryName]):
            d = self.getPage(path, headers=headers,
                             queryDict={'action': action})
            d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
            self.failUnlessFailure(d, Error)
            yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testAnonUserCannotGETAdminTopLevel(self):
        headers = {
            'accept': 'application/json',
        }
        path = defaults.sep.join([defaults.namespaceCategoryName,
                                  defaults.adminUsername])
        for action in \
                permissions.actionsByCategory[defaults.namespaceCategoryName]:
            d = self.getPage(path, headers=headers,
                             queryDict={'action': action})
            d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
            self.failUnlessFailure(d, Error)
            yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testAnonUserCannotGETRandomUserTopLevelNamespace(self):
        headers = {
            'accept': 'application/json',
        }
        path = defaults.sep.join([defaults.namespaceCategoryName,
                                  'testuser1'])
        for action in permissions.actionsByCategory[
                defaults.namespaceCategoryName]:
            d = self.getPage(path, headers=headers,
                             queryDict={'action': action})
            d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
            self.failUnlessFailure(d, Error)
            yield d


class TestPUT(PermissionsTest):

    verb = 'PUT'

    @base.showFailures
    @defer.inlineCallbacks
    def testAdminChangesTopLevelNamespace(self):
        path = defaults.sep.join([
            defaults.namespaceCategoryName, defaults.adminUsername])
        for action in permissions.actionsByCategory[
                defaults.namespaceCategoryName]:
            yield self.updatePermissions(path, action, permissions.CLOSED, [])

    @base.showFailures
    @defer.inlineCallbacks
    def testAdminChangesTopLevelNamespaceInDetail(self):
        exceptions = ['testuser1', 'testuser2']
        policy = permissions.CLOSED
        path = defaults.sep.join([
            defaults.namespaceCategoryName, defaults.adminUsername])
        for action in permissions.actionsByCategory[
                defaults.namespaceCategoryName]:
            # Save originals.
            origPolicy, origExceptions = \
                yield self.getPermissions(path, action)
            # Set new.
            yield self.updatePermissions(path, action, policy, exceptions)
            # Get & test.
            newPolicy, newExceptions = \
                yield self.getPermissions(path, action)
            self.assertEqual(policy, newPolicy)
            self.assertEqual(sorted(exceptions), sorted(newExceptions))
            # Restore.
            yield self.updatePermissions(path, action,
                                         origPolicy, origExceptions)

    @base.showFailures
    @defer.inlineCallbacks
    def testAnonCannotChangeTopLevelNamespace(self):
        path = defaults.sep.join([
            defaults.namespaceCategoryName, defaults.anonUsername])
        for action in permissions.actionsByCategory[
                defaults.namespaceCategoryName]:
            d = self.updatePermissions(path, action, permissions.CLOSED, [],
                                       requesterUsername=defaults.anonUsername,
                                       requesterPassword=defaults.anonPassword)
            d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
            self.failUnlessFailure(d, Error)
            yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testTwoRandomUsersDancing(self):
        path = defaults.sep.join([defaults.namespaceCategoryName,
                                  'testuser1'])

        # Check u2 cannot retrieve u1's namespace permissions.
        d = self.getPermissions(path, permissions.CREATE,
                                requesterUsername='testuser2',
                                requesterPassword='secret')
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        yield d

        # Give u2 permission to create things in the namespace.
        yield self.updatePermissions(
            path, permissions.CREATE,
            permissions.CLOSED, ('testuser1', 'testuser2'),
            requesterUsername='testuser1', requesterPassword='secret')

        # u2 makes and deletes a new tag in u1's namespace.
        name = 'test'
        parentPath1 = 'testuser1'
        parentPath2 = defaults.sep.join([parentPath1, name])
        yield self.createTag(name, parentPath1,
                             requesterUsername='testuser2',
                             requesterPassword='secret')
        yield self.deleteTag(parentPath2,
                             requesterUsername='testuser2',
                             requesterPassword='secret')

        # Check u2 can still not retrieve u1's namespace permissions.
        d = self.getPermissions(path, permissions.CREATE,
                                requesterUsername='testuser2',
                                requesterPassword='secret')
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        yield d

        # Give u2 CONTROL permission on u1's namespace.
        yield self.updatePermissions(
            path, permissions.CONTROL,
            permissions.CLOSED, ('testuser1', 'testuser2'),
            requesterUsername='testuser1', requesterPassword='secret')

        # Check u2 can now retrieve u1's namespace permissions.
        d = self.getPermissions(path, permissions.CREATE,
                                requesterUsername='testuser2',
                                requesterPassword='secret')
        policy, exceptions = yield d
        self.assertEqual(policy, permissions.CLOSED)
        self.assertEqual(sorted(exceptions),
                         sorted(['testuser1', 'testuser2']))

        # u2 takes away CONTROL permission for u1 on u1's namespace.
        yield self.updatePermissions(
            path, permissions.CONTROL,
            permissions.CLOSED, ('testuser2',),
            requesterUsername='testuser2', requesterPassword='secret')

        # Check u1 can now not retrieve u1's namespace permissions.
        d = self.getPermissions(path, permissions.CREATE,
                                requesterUsername='testuser1',
                                requesterPassword='secret')
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        yield d

        # u2 takes away CONTROL permission for themself on u1's namespace.
        yield self.updatePermissions(
            path, permissions.CONTROL,
            permissions.CLOSED, (),
            requesterUsername='testuser2', requesterPassword='secret')

        # Check u2 can no longer retrieve u1's namespace permissions.
        d = self.getPermissions(path, permissions.CREATE,
                                requesterUsername='testuser2',
                                requesterPassword='secret')
        d.addErrback(self.checkErrorStatus, http.UNAUTHORIZED)
        self.failUnlessFailure(d, Error)
        yield d

        # Admin confirms the CONTROL policy is closed and the exceptions
        # are empty.
        d = self.getPermissions(path, permissions.CONTROL)
        policy, exceptions = yield d
        self.assertEqual(policy, permissions.CLOSED)
        self.assertEqual(exceptions, [])

        # Admin gives back u1 CREATE and CONTROL permissions on u1's
        # namespace.  We do this to restore the original perms on the
        # namespace or we can't run this test again.
        yield self.updatePermissions(path, permissions.CONTROL,
                                     permissions.CLOSED, ('testuser1',))
        yield self.updatePermissions(path, permissions.CREATE,
                                     permissions.CLOSED, ('testuser1',))

    @base.showFailures
    def testInvalidPolicy(self):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        data = {
            'policy': 'ajar',
            'exceptions': [],
        }
        path = defaults.sep.join([
            defaults.namespaceCategoryName, defaults.adminUsername])
        d = self.getPage(path, headers=headers, postdata=json.dumps(data),
                         queryDict={'action': 'LIST'})
        d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'): TInvalidPolicy.__name__})
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    def testMissingAction(self):
        headers = {
            'accept': 'application/json',
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        data = {
            'policy': 'closed',
            'exceptions': [],
        }
        path = defaults.sep.join([
            defaults.namespaceCategoryName, defaults.adminUsername])
        d = self.getPage(path, headers=headers, postdata=json.dumps(data))
        d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
        d.addErrback(
            self.checkErrorHeaders,
            {buildHeader('Error-Class'): error.MissingArgument.__name__})
        self.failUnlessFailure(d, Error)
        return d

    @base.showFailures
    @defer.inlineCallbacks
    def testBadPolicyTypes(self):
        headers = {
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        path = defaults.sep.join([
            defaults.namespaceCategoryName, defaults.adminUsername])

        for field in ('policy',):
            data = {
                'policy': 'open',
                'exceptions': [],
            }
            for value in (None, 3, 6.7, True, False, ['a', 'list'], {'x': 3}):
                data[field] = value
                d = self.getPage(path, headers=headers,
                                 postdata=json.dumps(data))
                d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
                d.addErrback(
                    self.checkErrorHeaders,
                    {buildHeader('Error-Class'):
                     error.InvalidPayloadField.__name__})
                self.failUnlessFailure(d, Error)
                yield d

    @base.showFailures
    @defer.inlineCallbacks
    def testBadExceptionTypes(self):
        headers = {
            'content-type': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        path = defaults.sep.join([
            defaults.namespaceCategoryName, defaults.adminUsername])

        for field in ('exceptions',):
            data = {
                'policy': 'open',
                'exceptions': [],
            }
            for value in ('x', None, 3, 6.7, True, False, [6, 'y'], {'x': 3}):
                data[field] = value
                d = self.getPage(path, headers=headers,
                                 postdata=json.dumps(data))
                d.addErrback(self.checkErrorStatus, http.BAD_REQUEST)
                d.addErrback(
                    self.checkErrorHeaders,
                    {buildHeader('Error-Class'):
                     error.InvalidPayloadField.__name__})
                self.failUnlessFailure(d, Error)
                yield d


class TestDELETE(PermissionsTest):

    verb = 'DELETE'

    @base.showFailures
    def testNotFound(self):
        headers = {
            'accept': 'application/json',
        }
        self.addBasicAuthHeader(headers)
        d = self.getPage('dummy', headers=headers)
        d.addErrback(self.checkErrorStatus, http.NOT_FOUND)
        self.failUnlessFailure(d, Error)
        return d
