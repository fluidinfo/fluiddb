from calendar import timegm
from datetime import datetime
from uuid import uuid4

from fluiddb.cache.permission import CachingPermissionAPI
from fluiddb.data.permission import Operation, Policy
from fluiddb.data.system import createSystemData
from fluiddb.model.exceptions import UnknownPathError
from fluiddb.model.test.test_comment import CommentAPITestMixin
from fluiddb.model.user import UserAPI, getUser
from fluiddb.security.comment import SecureCommentAPI
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.security.value import SecureTagValueAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    CacheResource, ConfigResource, DatabaseResource, IndexResource,
    ThreadPoolResource)


class SecureCommentAPIWithAnonymousRoleTest(FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('client', IndexResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureCommentAPIWithAnonymousRoleTest, self).setUp()
        system = createSystemData()
        self.anon = system.users[u'anon']

    def testCreateIsDenied(self):
        """
        L{SecureObjectAPI.create} raises a L{PermissionDeniedError} if it's
        invoked by a L{User} with the L{Role.ANONYMOUS}.
        """
        commentAPI = SecureCommentAPI(self.anon)
        error = self.assertRaises(PermissionDeniedError, commentAPI.create,
                                  'text...', 'joe')
        self.assertEqual(self.anon.username, error.username)
        self.assertEqual(
            [(u'fluidinfo.com/info/username', Operation.WRITE_TAG_VALUE)],
            error.pathsAndOperations)

    def testDeleteIsDenied(self):
        """
        L{SecureObjectAPI.delete} raises a L{PermissionDeniedError} if it's
        invoked by a L{User} with the L{Role.ANONYMOUS}.
        """
        commentAPI = SecureCommentAPI(self.anon)
        error = self.assertRaises(PermissionDeniedError, commentAPI.delete,
                                  'digg.com', 'joe', datetime.utcnow())
        self.assertEqual(self.anon.username, error.username)
        self.assertEqual(
            [(u'fluidinfo.com/info/username', Operation.DELETE_TAG_VALUE)],
            error.pathsAndOperations)

    def testUpdateWithAnonymous(self):
        """
        L{SecureObjectAPI.update} raises a L{PermissionDeniedError} if it's
        invoked by a L{User} with the L{Role.ANONYMOUS}.
        """
        commentAPI = SecureCommentAPI(self.anon)
        error = self.assertRaises(PermissionDeniedError, commentAPI.update,
                                  'digg.com', 'joe', datetime.utcnow(), u'new')
        self.assertEqual(self.anon.username, error.username)
        self.assertEqual(
            [(u'fluidinfo.com/info/username', Operation.WRITE_TAG_VALUE)],
            error.pathsAndOperations)


class SecureCommentAPIWithUserRoleTest(CommentAPITestMixin, FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(SecureCommentAPIWithUserRoleTest, self).setUp()
        createSystemData()
        UserAPI().create([
            (u'username', u'password', u'User', u'user@example.com'),
            (u'fluidinfo.com', u'secret', u'Fluidinfo', u'info@example.com')])
        self.user = getUser(u'username')
        self.comments = SecureCommentAPI(self.user)

    def testCreateSucceeds(self):
        """
        L{SecureCommentAPI.create} returns a C{dict} with the expected
        keys and values.
        """
        when = datetime.utcnow()
        floatTime = timegm(when.utctimetuple()) + float(when.strftime('0.%f'))
        isoTime = when.isoformat()
        result = self.comments.create(u'Comment text', u'username', when=when)
        expected = {
            'fluidinfo.com/info/about': [],
            'fluidinfo.com/info/text': u'Comment text',
            'fluidinfo.com/info/timestamp': floatTime,
            'fluidinfo.com/info/url': (
                'https://fluidinfo.com/comment/fluidinfo.com/username/' +
                isoTime),
            'fluidinfo.com/info/username': u'username',
        }
        self.assertEqual(expected, result)

    def testDeleteAnotherUsersComment(self):
        """
        L{SecureObjectAPI.delete} raises a L{PermissionDeniedError} if a
        L{User} tries to delete a comment made by someone else.
        """
        error = self.assertRaises(PermissionDeniedError, self.comments.delete,
                                  'digg.com', 'joe', datetime.utcnow())
        self.assertEqual(u'username', error.username)
        self.assertEqual(
            [(u'fluidinfo.com/info/username', Operation.DELETE_TAG_VALUE)],
            error.pathsAndOperations)

    def testUpdateAnotherUsersComment(self):
        """
        L{SecureObjectAPI.update} raises a L{PermissionDeniedError} if a
        L{User} tries to update a comment made by someone else.
        """
        error = self.assertRaises(PermissionDeniedError, self.comments.update,
                                  'digg.com', 'joe', datetime.utcnow(), u'new')
        self.assertEqual(u'username', error.username)
        self.assertEqual(
            [(u'fluidinfo.com/info/username', Operation.WRITE_TAG_VALUE)],
            error.pathsAndOperations)

    def testGetForObjectWithAdditionalTagsUnreadable(self):
        """
        L{SecureCommentAPI.getForObject} raises a L{PermissionDeniedError} if a
        L{User} tries to retrieve C{additionalTags} which are unreadable to
        them.
        """
        objectID = uuid4()
        values = {objectID: {u'username/tag': 16}}
        SecureTagValueAPI(self.user).set(values)
        CachingPermissionAPI(self.user).set([(u'username/tag',
                                              Operation.READ_TAG_VALUE,
                                              Policy.CLOSED, [])])

        error = self.assertRaises(PermissionDeniedError,
                                  self.comments.getForObject, u'about',
                                  additionalTags=[u'username/tag'])
        self.assertEqual(u'username', error.username)
        self.assertEqual(
            [(u'username/tag', Operation.READ_TAG_VALUE)],
            error.pathsAndOperations)

    def testGetForObjectWithAdditionalTagsNonexistent(self):
        """
        L{SecureCommentAPI.getForObject} raises a L{PermissionDeniedError} if a
        L{User} tries to retrieve C{additionalTags} which are unreadable to
        them.
        """
        self.assertRaises(UnknownPathError,
                          self.comments.getForObject, u'about',
                          additionalTags=[u'user/nonexistent'])

    def testGetForUserWithAdditionalTagsUnreadable(self):
        """
        L{SecureCommentAPI.getForUser} raises a L{PermissionDeniedError} if a
        L{User} tries to retrieve C{additionalTags} which are unreadable to
        them.
        """
        objectID = uuid4()
        values = {objectID: {u'username/tag': 16}}
        SecureTagValueAPI(self.user).set(values)
        CachingPermissionAPI(self.user).set([(u'username/tag',
                                              Operation.READ_TAG_VALUE,
                                              Policy.CLOSED, [])])

        error = self.assertRaises(PermissionDeniedError,
                                  self.comments.getForUser, u'username',
                                  additionalTags=[u'username/tag'])
        self.assertEqual(u'username', error.username)
        self.assertEqual(
            [(u'username/tag', Operation.READ_TAG_VALUE)],
            error.pathsAndOperations)

    def testGetForUserWithAdditionalTagsNonexistent(self):
        """
        L{SecureCommentAPI.getForUser} raises a L{PermissionDeniedError} if a
        L{User} tries to retrieve C{additionalTags} which are unreadable to
        them.
        """
        self.assertRaises(UnknownPathError,
                          self.comments.getForUser, u'username',
                          additionalTags=[u'user/nonexistent'])
