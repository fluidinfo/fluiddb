from calendar import timegm
from datetime import datetime

from fluiddb.data.exceptions import UnknownUserError
from fluiddb.data.system import createSystemData
from fluiddb.model.exceptions import UnknownPathError
from fluiddb.model.user import UserAPI, getUser
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.security.object import SecureObjectAPI
from fluiddb.security.value import SecureTagValueAPI
from fluiddb.scripts.dataset import CommentImporter, DatasetImporter
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    ConfigResource, DatabaseResource, LoggingResource, CacheResource)


class DatasetImporterTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource(format='%(message)s')),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(DatasetImporterTest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'user', u'secret', u'User', u'user@example.com')])
        user = getUser(u'user')
        self.objects = SecureObjectAPI(user)
        self.values = SecureTagValueAPI(user)

    def testUpload(self):
        """
        Object data is converted into a format compatible with the
        L{TagValueAPI.set} method before being uploaded directly into
        Fluidinfo.
        """
        client = DatasetImporter(100)
        client.upload(u'user',
                      [{'about': u'hello world', 'values': {u'user/bar': 13}}])
        result = self.objects.get([u'hello world'])
        objectID = result[u'hello world']
        result = self.values.get([objectID], [u'user/bar'])
        value = result[objectID][u'user/bar']
        self.assertEqual(13, value.value)

    def testUploadMultipleObjects(self):
        """Multiple objects are inserted in batches."""
        client = DatasetImporter(100)
        client.upload(u'user',
                      [{'about': u'hello world', 'values': {u'user/bar': 13}},
                       {'about': u'wubble', 'values': {u'user/quux': 42}}])
        aboutValues = self.objects.get([u'hello world', u'wubble'])

        objectID = aboutValues[u'hello world']
        result = self.values.get([objectID], [u'user/bar'])
        value = result[objectID][u'user/bar']
        self.assertEqual(13, value.value)

        objectID = aboutValues[u'wubble']
        result = self.values.get([objectID], [u'user/quux'])
        value = result[objectID][u'user/quux']
        self.assertEqual(42, value.value)
        self.assertTrue(self.log.getvalue().startswith(
            'Importing 2 new objects.\nImported 2/2 new objects.\n'
            'Imported 2 objects in '))

    def testUploadUsesBatchSize(self):
        """
        Objects are uploaded in batches when possible, depending on the batch
        size.
        """
        client = DatasetImporter(1)
        client.upload(u'user',
                      [{'about': u'hello world', 'values': {u'user/bar': 13}},
                       {'about': u'wubble', 'values': {u'user/quux': 42}}])
        self.assertTrue(self.log.getvalue().startswith(
            'Importing 2 new objects.\nImported 1/2 new objects.\n'
            'Imported 2/2 new objects.\nImported 2 objects in '))

    def testUploadWithUncreatablePath(self):
        """
        L{DatasetImporter.upload} checks permissions when importing data.  An
        L{UnknownPathError} is raised if a specified tag doesn't exist and the
        L{User} doesn't have permissions to create it.
        """
        client = DatasetImporter(100)
        self.assertRaises(
            UnknownPathError, client.upload, u'user',
            [{'about': u'hello world', 'values': {u'foo/bar': 13}}])

    def testUploadWithPermissionViolation(self):
        """L{DatasetImporter.upload} checks permissions when importing data."""
        UserAPI().create([(u'user1', u'pwd', u'User 1', u'user1@example.com')])
        client = DatasetImporter(100)
        self.assertRaises(
            PermissionDeniedError, client.upload, u'user',
            [{'about': u'hello world', 'values': {u'user1/bar': 13}}])

    def testUploadWithUnknownUser(self):
        """
        L{DatasetImporter.upload} raises an L{UnknownUserError} if the
        specified L{User} doesn't exist.
        """
        client = DatasetImporter(100)
        self.assertRaises(
            UnknownUserError, client.upload, u'unknown',
            [{'about': u'hello world', 'values': {u'unknown/bar': 13}}])

    def testUploadLogsMessage(self):
        """
        Uploads must prefix log output with the passed message.
        """
        client = DatasetImporter(100)
        client.upload(u'user',
                      [{'about': u'hello world', 'values': {u'user/bar': 13}}],
                      'message-xxx')
        self.assertTrue(self.log.getvalue().startswith(
            'message-xxx: Importing 1 new objects.\n'
            'message-xxx: Imported 1/1 new objects.\n'
            'message-xxx: Imported 1 objects in '))


class CommentImporterTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource(format='%(message)s')),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(CommentImporterTest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([
            (u'fluidinfo.com', u'secret', u'User', u'user@example.com')])
        user = getUser(u'fluidinfo.com')
        self.objects = SecureObjectAPI(user)
        self.values = SecureTagValueAPI(user)

    def testUpload(self):
        """
        Comments are uploaded directly to Fluidinfo. After performing an
        upload, all the inserted values must be present in Fluidinfo.
        """
        when = datetime.utcnow()
        floatTime = timegm(when.utctimetuple()) + float(when.strftime('0.%f'))
        isoTime = when.isoformat()
        client = CommentImporter(100)
        client.upload([
            {'about': [u'one', u'two'],
             'importer': u'fluidinfo.com',
             'text': u'Here is my #wonderful comment',
             'timestamp': when,
             'url': u'http://twitter.com/status/9373973',
             'username': u'joe'}
        ])
        about = u'fluidinfo.com joe %s' % isoTime
        result = self.objects.get([about])
        objectID = result[about]
        result = self.values.get([objectID], [u'fluidinfo.com/info/about',
                                              u'fluidinfo.com/info/text',
                                              u'fluidinfo.com/info/timestamp',
                                              u'fluidinfo.com/info/url',
                                              u'fluidinfo.com/info/username',
                                              ])
        comment = result[objectID]
        self.assertEqual([u'one', u'two', u'#wonderful'],
                         comment[u'fluidinfo.com/info/about'].value)
        self.assertEqual(u'Here is my #wonderful comment',
                         comment[u'fluidinfo.com/info/text'].value)
        self.assertEqual(floatTime,
                         comment[u'fluidinfo.com/info/timestamp'].value)
        self.assertEqual(u'http://twitter.com/status/9373973',
                         comment[u'fluidinfo.com/info/url'].value)
        self.assertEqual(u'joe',
                         comment[u'fluidinfo.com/info/username'].value)

    def testUploadWithoutAboutValues(self):
        """
        When no explicit about values are in the uploaded comment, there
        must be no about values stored in Fluidinfo.
        """
        when = datetime.utcnow()
        isoTime = when.isoformat()
        client = CommentImporter(100)
        client.upload([
            {'importer': u'fluidinfo.com',
             'text': u'Here is my comment',
             'timestamp': when,
             'url': u'http://twitter.com/status/9373973',
             'username': u'joe'}
        ])
        about = u'fluidinfo.com joe %s' % isoTime
        result = self.objects.get([about])
        objectID = result[about]
        result = self.values.get([objectID], [u'fluidinfo.com/info/about'])
        comment = result[objectID]
        self.assertEqual([], comment[u'fluidinfo.com/info/about'].value)

    def testUploadMultipleComments(self):
        """Multiple comments are inserted in batches."""
        when = datetime.utcnow()
        isoTime = when.isoformat()
        client = CommentImporter(100)
        client.upload([
            {'importer': u'fluidinfo.com',
             'text': u'Here is my #wonderful comment',
             'timestamp': when,
             'url': u'http://twitter.com/status/9373973',
             'username': u'joe'},
            {'importer': u'fluidinfo.com',
             'text': u'A #crazy comment',
             'timestamp': when,
             'url': u'http://twitter.com/status/9279479379',
             'username': u'mike'}
        ])

        about1 = u'fluidinfo.com joe %s' % isoTime
        about2 = u'fluidinfo.com mike %s' % isoTime
        result = self.objects.get([about1, about2])

        objectID1 = result[about1]
        objectID2 = result[about2]
        comments = self.values.get([objectID1, objectID2],
                                   [u'fluidinfo.com/info/text'])

        comment1 = comments[objectID1]
        self.assertEqual(u'Here is my #wonderful comment',
                         comment1[u'fluidinfo.com/info/text'].value)

        comment2 = comments[objectID2]
        self.assertEqual(u'A #crazy comment',
                         comment2[u'fluidinfo.com/info/text'].value)

        self.assertTrue(self.log.getvalue().startswith(
            'Importing 2 new comments.\nImported 2/2 new comments.\n'
            'Imported 2 comments in '))

    def testUploadUsesBatchSize(self):
        """
        Comments are uploaded in batches when possible, depending on the batch
        size.
        """
        when = datetime.utcnow()
        client = CommentImporter(1)
        client.upload([
            {'importer': u'fluidinfo.com',
             'text': u'Here is my #wonderful comment',
             'timestamp': when,
             'url': u'http://twitter.com/status/9373973',
             'username': u'joe'},
            {'importer': u'fluidinfo.com',
             'text': u'A #crazy comment',
             'timestamp': when,
             'url': u'http://twitter.com/status/9279479379',
             'username': u'mike'}
        ])
        self.assertTrue(self.log.getvalue().startswith(
            'Importing 2 new comments.\nImported 1/2 new comments.\n'
            'Imported 2/2 new comments.\nImported 2 comments in '))

    def testUploadLogsMessage(self):
        """
        Uploads must prefix log output with the passed message.
        """
        when = datetime.utcnow()
        client = CommentImporter(100)
        client.upload([
            {'importer': u'fluidinfo.com',
             'text': u'Here is my #wonderful comment',
             'timestamp': when,
             'url': u'http://twitter.com/status/9373973',
             'username': u'joe'}], 'message-xxx')
        self.assertTrue(self.log.getvalue().startswith(
            'message-xxx: Importing 1 new comments.\n'
            'message-xxx: Imported 1/1 new comments.\n'
            'message-xxx: Imported 1 comments in '))
