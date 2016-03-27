from calendar import timegm
from datetime import datetime, timedelta
from json import dumps, loads
from time import time as get_time

from twisted.internet.defer import inlineCallbacks
from twisted.web.http import BAD_REQUEST, UNAUTHORIZED
from twisted.web.http_headers import Headers

from fluiddb.data.system import createSystemData
from fluiddb.model.user import UserAPI, getUser
from fluiddb.security.comment import SecureCommentAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.doubles import FakeRequest
from fluiddb.testing.resources import (
    CacheResource, ConfigResource, DatabaseResource, IndexResource,
    LoggingResource, ThreadPoolResource)
from fluiddb.testing.session import login
from fluiddb.web.comment import CommentResource
from fluiddb.util.transact import Transact
from fluiddb.model.value import TagValueAPI
from fluiddb.model.object import ObjectAPI


class CommentResourceTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('client', IndexResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(CommentResourceTest, self).setUp()
        createSystemData()
        UserAPI().create([
            (u'username', u'password', u'User', u'user@example.com'),
            (u'fluidinfo.com', u'password', u'User', u'user@example.com')])
        self.user = getUser(u'username')
        self.transact = Transact(self.threadPool)
        self.store.commit()

    def invoke(self, method, _username=None, **kwargs):
        """Invoke a JSON-RPC method and return the result."""
        username = _username or u'username'
        with login(username, self.user.objectID, self.transact) as session:
            body = dumps({'id': 100, 'jsonrpc': '2.0', 'method': method,
                          'params': kwargs})
            headers = Headers({'Content-Length': [str(len(body))],
                               'Content-Type': ['application/json']})
            request = FakeRequest(headers=headers, body=body)
            resource = CommentResource(None, session)
            return resource.deferred_render_POST(request)

    @inlineCallbacks
    def testAddComment(self):
        """
        The C{addComment} method creates a comment and returns a C{dict} with
        a mapping of tags to values that represent that comment.
        """
        result = yield self.invoke(
            'addComment', about=u'trout fishing in america',
            text='@joe @sam http://abc.com/def.html is #super #cool')
        result = loads(result)
        url = result['result']['fluidinfo.com/info/url']
        urlFragment = 'https://fluidinfo.com/comment/fluidinfo.com/username/'
        self.assertTrue(url.startswith(urlFragment))
        isoTime = url[len(urlFragment):]
        when = datetime.strptime(isoTime, '%Y-%m-%dT%H:%M:%S.%f')
        timestamp = result['result']['fluidinfo.com/info/timestamp']
        self.assertEqual(
            timegm(when.utctimetuple()) + float(when.strftime('0.%f')),
            timestamp)
        self.assertEqual(
            {'jsonrpc': u'2.0',
             'id': 100,
             'result': {
                 'fluidinfo.com/info/about': [
                     u'trout fishing in america', u'http://abc.com/def.html',
                     u'#super', u'#cool', u'@joe', u'@sam'],
                 'fluidinfo.com/info/text': (
                     u'@joe @sam http://abc.com/def.html is #super #cool'),
                 'fluidinfo.com/info/timestamp': timestamp,
                 'fluidinfo.com/info/url': url,
                 'fluidinfo.com/info/username': u'username'}},
            result)

    @inlineCallbacks
    def testAddCommentWithCreationTime(self):
        """
        The C{addComment} method optionally accepts a creation time to use
        when creating the comment.
        """
        result = yield self.invoke(
            'addComment', about=u'trout fishing in america',
            text='@joe @sam http://abc.com/def.html is #super #cool',
            creationTime='2012-05-16T12:13:14.16253')
        result = loads(result)
        self.assertEqual(
            {u'jsonrpc': u'2.0',
             u'id': 100,
             u'result': {
                 u'fluidinfo.com/info/about': [
                     u'trout fishing in america', u'http://abc.com/def.html',
                     u'#super', u'#cool', u'@joe', u'@sam'],
                 u'fluidinfo.com/info/text': (
                     u'@joe @sam http://abc.com/def.html is #super #cool'),
                 u'fluidinfo.com/info/timestamp': 1337170394.16253,
                 u'fluidinfo.com/info/url': (
                     u'https://fluidinfo.com/comment/'
                     'fluidinfo.com/username/2012-05-16T12:13:14.162530'),
                 u'fluidinfo.com/info/username': u'username'}},
            result)

    @inlineCallbacks
    def testExplicitAboutValueIsTheFirstThingInTheCreatedAboutTag(self):
        """
        When a comment is created with an explicit about value and about
        values in the comment text, the explicit value must be the first
        element in the resulting fluidinfo.com/info/about tag.
        """
        result = yield self.invoke(
            'addComment', about=u'explicit about',
            text='#Fishing is cool.')
        result = loads(result)
        abouts = result['result']['fluidinfo.com/info/about']
        self.assertEqual(abouts[0], u'explicit about')
        # Make sure the list has more than just the explicit about value in
        # it, so we know it's the first value among several (as opposed to
        # being the first value simply because no other values were present
        # in the comment text).
        self.assertTrue(len(abouts) > 1)

    @inlineCallbacks
    def testAddCommentWithMalformedCreationTime(self):
        """
        The C{addComment} method returns a C{BAD_REQUEST} error if the
        specified creation time is malformed.
        """
        result = yield self.invoke(
            'addComment', about=u'trout fishing in america',
            text='@joe @sam http://abc.com/def.html is #super #cool',
            creationTime='malformed')
        self.assertEqual(
            {u'jsonrpc': u'2.0', u'id': 100,
             u'error': {u'message': u'Creation time is malformed.',
                        u'code': BAD_REQUEST}},
            loads(result))

    @inlineCallbacks
    def testAddCommentWithoutCommentText(self):
        """
        The C{addComment} method returns a C{BAD_REQUEST} error if no comment
        text is provided.
        """
        result = yield self.invoke('addComment', about=u'about')
        self.assertEqual(
            {u'jsonrpc': u'2.0', u'id': 100,
             u'error': {
                 u'message': u'Comment text non-existent or just whitespace.',
                 u'code': BAD_REQUEST}},
            loads(result))

    @inlineCallbacks
    def testAddCommentWithEmptyCommentText(self):
        """
        The C{addComment} method returns a C{BAD_REQUEST} error if the comment
        text provided is empty.
        """
        result = yield self.invoke('addComment', about=u'about')
        self.assertEqual(
            {u'jsonrpc': u'2.0', u'id': 100,
             u'error': {
                 u'message': u'Comment text non-existent or just whitespace.',
                 u'code': BAD_REQUEST}},
            loads(result))

    @inlineCallbacks
    def testAddCommentWithAnonymousUser(self):
        """
        The C{addComment} method returns an C{UNAUTHORIZED} error if the
        anonymous user attempts to create a comment.
        """
        result = yield self.invoke('addComment', _username=u'anon',
                                   about=u'about', text=u'text')
        self.assertEqual({u'jsonrpc': u'2.0', u'id': 100,
                          u'error': {u'message': u'Access denied.',
                                     u'code': UNAUTHORIZED}},
                         loads(result))

    @inlineCallbacks
    def testGetForObjectWithoutComments(self):
        """
        The C{getForObject} method returns an empty C{list} if no comments are
        available for the specified about value.
        """
        result = yield self.invoke('getForObject', about=u'about')
        self.assertEqual({'id': 100, 'jsonrpc': '2.0',
                          'result': {'nextPageID': None,
                                     'currentPageID': None,
                                     'comments': []}},
                         loads(result))

    @inlineCallbacks
    def testGetForObject(self):
        """
        The C{getForObject} method returns the comments available for the
        specified object, sorted from newest to eldest.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username', about=[u'about'],
                        when=time - timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username', about=[u'about'],
                        when=time, url='http://example.com/2')
        self.store.commit()

        result = yield self.invoke('getForObject', about=u'about')
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336604400.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 2',
                  u'fluidinfo.com/info/timestamp': 1336604400.0,
                  u'fluidinfo.com/info/url': u'http://example.com/2',
                  u'fluidinfo.com/info/username': u'username'},
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336518000.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'username'}]},
            result)

    @inlineCallbacks
    def testGetForObjectWithUsername(self):
        """
        The C{getForObject} method returns the comments about the specified
        object made by the specified user, sorted from newest to eldest.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username1', about=[u'about'],
                        when=time - timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username2', about=[u'about'],
                        when=time, url='http://example.com/2')
        self.store.commit()

        result = yield self.invoke('getForObject', about=u'about',
                                   username=u'username1')
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336518000.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336518000.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'username1'}]},
            result)

    @inlineCallbacks
    def testGetForObjectWithFollowedByUsername(self):
        """
        The C{getForObject} method returns the comments about the specified
        object made by the specified user's friends, sorted from newest to
        eldest.
        """
        [(objectID, _)] = UserAPI().create([
            (u'friend', u'secret', u'Friend', u'friend@example.com')])
        TagValueAPI(self.user).set({objectID: {u'username/follows': None}})

        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'friend', about=[u'about'],
                        when=time - timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'foe', about=[u'about'],
                        when=time, url='http://example.com/2')
        self.store.commit()

        result = yield self.invoke('getForObject', about=u'about',
                                   followedByUsername=u'username')
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336518000.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336518000.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'friend'}]},
            result)

    @inlineCallbacks
    def testGetForObjectWithFilterTags(self):
        """
        The C{getForObject} method returns the comments about the specified
        object made having the specified tags, sorted from newest to
        eldest.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'friend', about=[u'about'],
                        when=time,
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'foe', about=[u'about'],
                        when=time + timedelta(days=1),
                        url='http://example.com/2')
        # Get the comment ID based on the expected about value
        commentAbout = u'fluidinfo.com friend %s' % time.isoformat()
        commentID = ObjectAPI(self.user).create(commentAbout)
        TagValueAPI(self.user).set({commentID: {u'username/tag': None}})
        self.store.commit()

        result = yield self.invoke('getForObject', about=u'about',
                                   filterTags=[u'username/tag'])
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336604400.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336604400.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'friend'}]},
            result)

    @inlineCallbacks
    def testGetForObjectWithfilterAbout(self):
        """
        The C{getForObject} method returns the comments about the specified
        object and also with the given object filter, sorted from newest to
        eldest.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'friend', about=[u'about', u'+filter'],
                        when=time,
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'foe', about=[u'about'],
                        when=time + timedelta(days=1),
                        url='http://example.com/2')
        self.store.commit()

        result = yield self.invoke('getForObject', about=u'about',
                                   filterAbout=u'+filter')
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336604400.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about', u'+filter'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336604400.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'friend'}]},
            result)

    @inlineCallbacks
    def testGetForObjectWithNextPageID(self):
        """
        The C{getForObject} method uses the C{nextPageID} to return the
        correct page of comments.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username', about=[u'about'],
                        when=time - timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username', about=[u'about'],
                        when=time, url='http://example.com/2')
        self.store.commit()

        result = yield self.invoke('getForObject', about=u'about',
                                   nextPageID=1336604400.0)
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336518000.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336518000.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'username'}]},
            result)

    @inlineCallbacks
    def testGetForObjectWithCurrentPageID(self):
        """
        The C{getForObject} method uses the C{currentPageID} to return the
        correct page of comments.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username', about=[u'about'],
                        when=time + timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username', about=[u'about'],
                        when=time, url='http://example.com/2')
        self.store.commit()

        result = yield self.invoke('getForObject', about=u'about',
                                   currentPageID=1336604400)
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336690800.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336690800.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'username'}]},
            result)

    @inlineCallbacks
    def testGetForObjectWithMalformedNextPageID(self):
        """
        The C{getForObject} method raises an error if the C{nextPageID}
        argument is not well formed.
        """
        result = yield self.invoke('getForObject', about=u'about',
                                   nextPageID='malformed')
        self.assertEqual({u'jsonrpc': u'2.0',
                          u'id': 100,
                          u'error': {
                              u'message': u"Couldn't parse nextPageID.",
                              u'code': BAD_REQUEST}},
                         loads(result))

    @inlineCallbacks
    def testGetForObjectWithMalformedCurrentPageID(self):
        """
        The C{getForObject} method raises an error if the C{currentPageID}
        argument is not well formed.
        """
        result = yield self.invoke('getForObject', about=u'about',
                                   currentPageID='malformed')
        self.assertEqual({u'jsonrpc': u'2.0',
                          u'id': 100,
                          u'error': {
                              u'message': u"Couldn't parse currentPageID.",
                              u'code': BAD_REQUEST}},
                         loads(result))

    @inlineCallbacks
    def testGetForObjectReturnsNextPageID(self):
        """
        The C{getForObject} method returns a C{nextPageID} value when another
        page of comments could be loaded.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        for i in range(26):
            comments.create(u'Comment', u'username', about=[u'about'],
                            when=time - timedelta(minutes=i),
                            url='http://example.com/comment')
        self.store.commit()

        result = yield self.invoke('getForObject', about=u'about')
        result = loads(result)['result']
        self.assertEqual(1336602960, result['nextPageID'])
        self.assertEqual(25, len(result['comments']))

    @inlineCallbacks
    def testGetForObjectWithAdditionalTags(self):
        """
        The C{getForObject} method invoked with a list of C{additionalTags}
        returns those in addition to the default ones.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username', about=[u'about'],
                        when=time - timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username', about=[u'about'],
                        when=time, url='http://example.com/2')

        # Get the comment ID based on the expected about value
        commentAbout = u'fluidinfo.com username %s' % time.isoformat()
        commentID = ObjectAPI(self.user).create(commentAbout)
        TagValueAPI(self.user).set({commentID: {u'username/custom': u'Honk'}})
        self.store.commit()

        result = yield self.invoke('getForObject', about=u'about',
                                   additionalTags=[u'username/custom'])
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336604400.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 2',
                  u'fluidinfo.com/info/timestamp': 1336604400.0,
                  u'fluidinfo.com/info/url': u'http://example.com/2',
                  u'fluidinfo.com/info/username': u'username',
                  u'username/custom': u'Honk'},
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336518000.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'username'}]},
            result)

    @inlineCallbacks
    def testGetForObjectWithAdditionalTagsEmptyList(self):
        """
        The C{getForObject} method, if invoked with an empty C{additionalTags}
        list acts the same as when none are specified.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username', about=[u'about'],
                        when=time - timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username', about=[u'about'],
                        when=time, url='http://example.com/2')
        self.store.commit()

        result = yield self.invoke('getForObject', about=u'about',
                                   additionalTags=[])
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336604400.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 2',
                  u'fluidinfo.com/info/timestamp': 1336604400.0,
                  u'fluidinfo.com/info/url': u'http://example.com/2',
                  u'fluidinfo.com/info/username': u'username'},
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336518000.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'username'}]},
            result)

    @inlineCallbacks
    def testGetForObjectWithAdditionalTagsInvalidPath(self):
        """
        The C{getForObject} method raises an error if the C{additionalTags}
        argument contains an invalid tag path.
        """
        result = yield self.invoke('getForObject', about=u'about',
                                   additionalTags=[u'///'])
        self.assertEqual({u'jsonrpc': u'2.0',
                          u'id': 100,
                          u'error': {
                              u'message': u"u'///' is not a valid path for "
                                          + "additionalTags.",
                              u'code': BAD_REQUEST}},
                         loads(result))

    @inlineCallbacks
    def testGetForObjectWithAdditionalTagsUnknownPath(self):
        """
        The C{getForObject} method raises an error if the C{additionalTags}
        argument contains an unknown tag path.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username', about=[u'about'],
                        when=time, url='http://example.com/1')
        self.store.commit()

        # Get the comment ID based on the expected about value
        commentAbout = u'fluidinfo.com username %s' % time.isoformat()
        commentID = ObjectAPI(self.user).create(commentAbout)
        TagValueAPI(self.user).set({commentID: {u'username/custom': u'Honk'}})
        self.store.commit()

        result = yield self.invoke('getForObject', about=u'about',
                                   additionalTags=[u'username/custom',
                                                   u'nosuchuser/unknowntag'])
        self.assertEqual({u'jsonrpc': u'2.0',
                          u'id': 100,
                          u'error': {
                              u'message': u"Unknown path in additionalTags: " +
                                          u"'nosuchuser/unknowntag'.",
                              u'code': BAD_REQUEST}},
                         loads(result))

    def testGetForObjectWithAdditionalTagsInvalidType(self):
        """
        The C{getForObject} method raises an error if the C{additionalTags}
        argument contains an invalid type in a tag path.
        """
        result = yield self.invoke('getForObject', about=u'about',
                                   additionalTags=[666])
        self.assertEqual({u'jsonrpc': u'2.0',
                          u'id': 100,
                          u'error': {
                              u'message': u"Invalid type in additionalTags.",
                              u'code': BAD_REQUEST}},
                         loads(result))

    @inlineCallbacks
    def testSummarizeObject(self):
        """
        The C{summarizeObject} method returns summary information for the
        comments about an object.
        """
        comments = SecureCommentAPI(self.user)
        comments.create(u'I drank #whisky with @ntoll and @terrycojones',
                        u'username', about=[u'about'])
        self.store.commit()

        result = yield self.invoke('summarizeObject', about=u'about')
        result = loads(result)['result']
        self.assertEqual({'commentCount': 1, 'followers': [],
                          'relatedObjects': {'#whisky': 1,
                                             u'@ntoll': 1,
                                             u'@terrycojones': 1}},
                         result)

    @inlineCallbacks
    def testSummarizeObjectWithEmptyAboutValue(self):
        """
        The C{summarizeObject} method returns a C{BAD_REQUEST} error if the
        specified about value is empty.
        """
        result = yield self.invoke('summarizeObject', about=u'')
        self.assertEqual({u'jsonrpc': u'2.0', u'id': 100,
                          u'error': {u'message': u'Need an about value.',
                                     u'code': BAD_REQUEST}},
                         loads(result))

    @inlineCallbacks
    def testSummarizeObjectWithWhitespaceAboutValue(self):
        """
        The C{summarizeObject} method returns a C{BAD_REQUEST} error if the
        specified about value only contains whitespace.
        """
        result = yield self.invoke('summarizeObject', about=u'  \n')
        self.assertEqual({u'jsonrpc': u'2.0', u'id': 100,
                          u'error': {u'message': u'Need an about value.',
                                     u'code': BAD_REQUEST}},
                         loads(result))

    @inlineCallbacks
    def testGetForUserWithoutComments(self):
        """
        The C{getForUser} method returns an empty C{list} if no comments are
        available for the specified about value.
        """
        result = yield self.invoke('getForUser', username=u'username')
        self.assertEqual({'id': 100, 'jsonrpc': '2.0',
                          'result': {'nextPageID': None,
                                     'currentPageID': None,
                                     'comments': []}},
                         loads(result))

    @inlineCallbacks
    def testGetForUser(self):
        """
        The C{getForUser} method returns the comments available from the
        specified user, sorted from newest to oldest.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username', about=[u'about'],
                        when=time - timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username', about=[u'about'],
                        when=time, url='http://example.com/2')
        self.store.commit()

        result = yield self.invoke('getForUser', username=u'username')
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336604400.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 2',
                  u'fluidinfo.com/info/timestamp': 1336604400.0,
                  u'fluidinfo.com/info/url': u'http://example.com/2',
                  u'fluidinfo.com/info/username': u'username'},
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336518000.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'username'}]},
            result)

    @inlineCallbacks
    def testGetForUserWithNextPageID(self):
        """
        The C{getForUser} method uses the C{nextPageID} to return the correct
        page of comments.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username', about=[u'about'],
                        when=time - timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username', about=[u'about'],
                        when=time, url='http://example.com/2')
        self.store.commit()

        result = yield self.invoke('getForUser', username='username',
                                   nextPageID=1336604400.0)
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336518000.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336518000.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'username'}]},
            result)

    @inlineCallbacks
    def testGetForUserWithCurrentPageID(self):
        """
        The C{getForUser} method uses the C{currentPageID} to return the
        correct page of comments.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username', about=[u'about'],
                        when=time + timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username', about=[u'about'],
                        when=time, url='http://example.com/2')
        self.store.commit()

        result = yield self.invoke('getForUser', username='username',
                                   currentPageID=1336604400.0)
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336690800.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336690800.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'username'}]},
            result)

    @inlineCallbacks
    def testGetForUserWithFilterTags(self):
        """
        The C{getForUser} method invoked with a list of C{filterTags}
        returns only comments with the filtered tags present.
        """

        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username', about=[u'about'],
                        when=time - timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username', about=[u'about'],
                        when=time, url='http://example.com/2')
        comments.create(u'Comment 3', u'username', about=[u'about'],
                        when=time + timedelta(days=1),
                        url='http://example.com/3')

        # Comment 1 gets only username/tag1
        commentAbout1 = u'fluidinfo.com username %s' \
            % (time - timedelta(days=1)).isoformat()
        commentID1 = ObjectAPI(self.user).create(commentAbout1)
        TagValueAPI(self.user).set({commentID1: {u'username/tag1': u'Monkey'}})

        # Comment 2 gets both username/tag1 and username/tag2
        commentAbout2 = u'fluidinfo.com username %s' % time.isoformat()
        commentID2 = ObjectAPI(self.user).create(commentAbout2)
        TagValueAPI(self.user).set({commentID2: {u'username/tag1': u'Monkey',
                                                 u'username/tag2': u'Ape'}})
        self.store.commit()

        # Comment 3 has no tags at all.

        result = yield self.invoke('getForUser', username=u'username',
                                   filterTags=[u'username/tag1',
                                               u'username/tag2'])
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336604400.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 2',
                  u'fluidinfo.com/info/timestamp': 1336604400.0,
                  u'fluidinfo.com/info/url': u'http://example.com/2',
                  u'fluidinfo.com/info/username': u'username'}]},
            result)

    @inlineCallbacks
    def testGetForUserWithFilterTagsAndAdditionalTags(self):
        """
        The C{getForUser} method invoked with a list of C{filterTags}
        returns only comments with the filtered tags present and the values of
        any tags specified in C{additionalTags}.
        """

        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username', about=[u'about'],
                        when=time - timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username', about=[u'about'],
                        when=time, url='http://example.com/2')

        # Get the comment ID based on the expected about value
        commentAbout = u'fluidinfo.com username %s' % time.isoformat()
        commentID = ObjectAPI(self.user).create(commentAbout)
        TagValueAPI(self.user).set({commentID: {u'username/tag': u'Monkey'}})
        self.store.commit()

        result = yield self.invoke('getForUser', username=u'username',
                                   filterTags=[u'username/tag'],
                                   additionalTags=[u'username/tag'])
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336604400.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 2',
                  u'fluidinfo.com/info/timestamp': 1336604400.0,
                  u'fluidinfo.com/info/url': u'http://example.com/2',
                  u'fluidinfo.com/info/username': u'username',
                  u'username/tag': u'Monkey'}]},
            result)

    @inlineCallbacks
    def testGetForUserWithfilterAbout(self):
        """
        The C{getForUser} method returns the comments for the specified
        user and also with the given object filter, sorted from newest to
        eldest.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username',
                        about=[u'about', u'+filter'],
                        when=time,
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username', about=[u'about'],
                        when=time + timedelta(days=1),
                        url='http://example.com/2')
        self.store.commit()

        result = yield self.invoke('getForUser', username='username',
                                   filterAbout='+filter')
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336604400.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about', u'+filter'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336604400.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'username'}]},
            result)

    @inlineCallbacks
    def testGetForUserWithMalformedNextPageID(self):
        """
        The C{getForUser} method raises an error if the C{nextPageID} argument
        is not well formed.
        """
        result = yield self.invoke('getForUser', username='username',
                                   nextPageID='malformed')
        self.assertEqual({u'jsonrpc': u'2.0',
                          u'id': 100,
                          u'error': {
                              u'message': u"Couldn't parse nextPageID.",
                              u'code': BAD_REQUEST}},
                         loads(result))

    @inlineCallbacks
    def testGetForUserWithMalformedCurrentPageID(self):
        """
        The C{getForUser} method raises an error if the C{currentPageID}
        argument is not well formed.
        """
        result = yield self.invoke('getForUser', username='username',
                                   currentPageID='malformed')
        self.assertEqual({u'jsonrpc': u'2.0',
                          u'id': 100,
                          u'error': {
                              u'message': u"Couldn't parse currentPageID.",
                              u'code': BAD_REQUEST}},
                         loads(result))

    @inlineCallbacks
    def testGetForUserReturnsNextPageID(self):
        """
        The C{getForUser} method returns a C{nextPageID} value when another
        page of comments could be loaded.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        for i in range(26):
            comments.create(u'Comment', u'username', about=[u'about'],
                            when=time - timedelta(minutes=i),
                            url='http://example.com/comment')
        self.store.commit()

        result = yield self.invoke('getForUser', username='username')
        result = loads(result)['result']
        self.assertEqual(1336602960, result['nextPageID'])
        self.assertEqual(25, len(result['comments']))

    @inlineCallbacks
    def testGetForUserWithAdditionalTags(self):
        """
        The C{getForUser} method invoked with a list of C{additionalTags}
        returns those in addition to the default ones.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username', about=[u'about'],
                        when=time - timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username', about=[u'about'],
                        when=time, url='http://example.com/2')

        # Get the comment ID based on the expected about value
        commentAbout = u'fluidinfo.com username %s' % time.isoformat()
        commentID = ObjectAPI(self.user).create(commentAbout)
        TagValueAPI(self.user).set({commentID: {u'username/custom': u'Honk'}})
        self.store.commit()

        result = yield self.invoke('getForUser', username=u'username',
                                   additionalTags=[u'username/custom'])
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336604400.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 2',
                  u'fluidinfo.com/info/timestamp': 1336604400.0,
                  u'fluidinfo.com/info/url': u'http://example.com/2',
                  u'fluidinfo.com/info/username': u'username',
                  u'username/custom': u'Honk'},
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336518000.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'username'}]},
            result)

    @inlineCallbacks
    def testGetForUserWithAdditionalTagsEmptyList(self):
        """
        The C{getForUser} method, if invoked with an empty C{additionalTags}
        list acts the same as when none are specified.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username', about=[u'about'],
                        when=time - timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username', about=[u'about'],
                        when=time, url='http://example.com/2')
        self.store.commit()

        result = yield self.invoke('getForUser', username=u'username',
                                   additionalTags=[])
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336604400.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 2',
                  u'fluidinfo.com/info/timestamp': 1336604400.0,
                  u'fluidinfo.com/info/url': u'http://example.com/2',
                  u'fluidinfo.com/info/username': u'username'},
                 {u'fluidinfo.com/info/about': [u'about'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336518000.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'username'}]},
            result)

    @inlineCallbacks
    def testGetForUserWithAdditionalTagsInvalidPath(self):
        """
        The C{getForUser} method raises an error if the C{additionalTags}
        argument contains an invalid tag path.
        """
        result = yield self.invoke('getForUser', username=u'username',
                                   additionalTags=[u'///'])
        self.assertEqual({u'jsonrpc': u'2.0',
                          u'id': 100,
                          u'error': {
                              u'message': u"u'///' is not a valid path for "
                                          + "additionalTags.",
                              u'code': BAD_REQUEST}},
                         loads(result))

    def testGetForUserWithAdditionalTagsInvalidType(self):
        """
        The C{getForUser} method raises an error if the C{additionalTags}
        argument contains an invalid type in a tag path.
        """
        result = yield self.invoke('getForUser', username=u'username',
                                   additionalTags=[666])
        self.assertEqual({u'jsonrpc': u'2.0',
                          u'id': 100,
                          u'error': {
                              u'message': u"Invalid type in additionalTags.",
                              u'code': BAD_REQUEST}},
                         loads(result))

    @inlineCallbacks
    def testGetAllFollowedWithoutComments(self):
        """
        The C{getAllFollowed} method returns an empty C{list} if no comments
        are available for the specified about value.
        """
        result = yield self.invoke('getAllFollowed', username=u'username')
        self.assertEqual({'id': 100, 'jsonrpc': '2.0',
                          'result': {'nextPageID': None,
                                     'currentPageID': None,
                                     'comments': []}},
                         loads(result))

    @inlineCallbacks
    def testGetRecent(self):
        """The C{getRecent} method returns recent comments."""
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username', about=[u'about 1'],
                        when=time - timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username', about=[u'about 2'],
                        when=time, url='http://example.com/2')
        self.store.commit()

        result = yield self.invoke('getRecent')
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336604400.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about 2'],
                  u'fluidinfo.com/info/text': u'Comment 2',
                  u'fluidinfo.com/info/timestamp': 1336604400.0,
                  u'fluidinfo.com/info/url': u'http://example.com/2',
                  u'fluidinfo.com/info/username': u'username'},
                 {u'fluidinfo.com/info/about': [u'about 1'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336518000.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'username'}]},
            result)

    @inlineCallbacks
    def testGetRecentWithNextPageID(self):
        """
        The C{getRecent} method uses the C{nextPageID} to return the
        correct page of comments.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username', about=[u'about 1'],
                        when=time - timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username', about=[u'about 2'],
                        when=time, url='http://example.com/2')
        self.store.commit()

        result = yield self.invoke('getRecent', nextPageID=1336604400.0)
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336518000.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about 1'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336518000.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'username'}]},
            result)

    @inlineCallbacks
    def testGetRecentWithCurrentPageID(self):
        """
        The C{getRecent} method uses the C{currentPageID} to return the
        correct page of comments.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username', about=[u'about 1'],
                        when=time + timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username', about=[u'about 2'],
                        when=time, url='http://example.com/2')
        self.store.commit()

        result = yield self.invoke('getRecent', currentPageID=1336604400.0)
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336690800.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about 1'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336690800.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'username'}]},
            result)

    @inlineCallbacks
    def testGetRecentWithMalformedNextPageID(self):
        """The C{getRecent} method raises an error if the C{nextPageID}."""
        result = yield self.invoke('getRecent', nextPageID='malformed')
        self.assertEqual({u'jsonrpc': u'2.0',
                          u'id': 100,
                          u'error': {
                              u'message': u"Couldn't parse nextPageID.",
                              u'code': BAD_REQUEST}},
                         loads(result))

    @inlineCallbacks
    def testGetRecentWithMalformedCurrentPageID(self):
        """The C{getRecent} method raises an error if the C{currentPageID}."""
        result = yield self.invoke('getRecent', currentPageID='malformed')
        self.assertEqual({u'jsonrpc': u'2.0',
                          u'id': 100,
                          u'error': {
                              u'message': u"Couldn't parse currentPageID.",
                              u'code': BAD_REQUEST}},
                         loads(result))

    @inlineCallbacks
    def testGetRecentReturnsNextPageID(self):
        """
        The C{getRecent} method returns a C{nextPageID} value when another page
        of comments could be loaded.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        for i in range(26):
            comments.create(u'Comment', u'username', about=[u'about'],
                            when=time - timedelta(minutes=i),
                            url='http://example.com/comment')
        self.store.commit()

        result = yield self.invoke('getRecent')
        result = loads(result)['result']
        self.assertEqual(1336602960, result['nextPageID'])
        self.assertEqual(25, len(result['comments']))

    @inlineCallbacks
    def testGetRecentWithFilterTagsAndAdditionalTags(self):
        """
        The C{getRecent} method returns all comments with C{filterTags} present
        and all values of the tags in C{additionalTags}.
        """
        time = datetime.utcfromtimestamp(1336604400)
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username', about=[u'about 1'],
                        when=time - timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username', about=[u'about 2'],
                        when=time, url='http://example.com/2')
        self.store.commit()

        # Get the comment ID based on the expected about value
        commentAbout = u'fluidinfo.com username %s' % time.isoformat()
        commentID = ObjectAPI(self.user).create(commentAbout)
        TagValueAPI(self.user).set({commentID: {u'username/tag1': u'Monkey'}})
        self.store.commit()

        result = yield self.invoke('getRecent',
                                   filterTags=[u'username/tag1'],
                                   additionalTags=[u'username/tag1'])
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336604400.0,
             'comments': [{u'fluidinfo.com/info/about': [u'about 2'],
                           u'fluidinfo.com/info/text': u'Comment 2',
                           u'fluidinfo.com/info/timestamp': 1336604400.0,
                           u'fluidinfo.com/info/url': u'http://example.com/2',
                           u'fluidinfo.com/info/username': u'username',
                           u'username/tag1': u'Monkey'}]},
            result)

    @inlineCallbacks
    def testGetAllFollowed(self):
        """
        The C{getAllFollowed} method returns the comments on the followed
        objects and users.
        """
        time = datetime.utcfromtimestamp(1336604400)
        objectID1 = ObjectAPI(self.user).create(u'about 1')
        objectID2 = ObjectAPI(self.user).create(u'about 2')
        TagValueAPI(self.user).set({objectID1: {u'username/follows': None},
                                    objectID2: {u'username/follows': None}})
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username', about=[u'about 1'],
                        when=time - timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username', about=[u'about 2'],
                        when=time, url='http://example.com/2')
        self.store.commit()

        result = yield self.invoke('getAllFollowed', username=u'username')
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336604400.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about 2'],
                  u'fluidinfo.com/info/text': u'Comment 2',
                  u'fluidinfo.com/info/timestamp': 1336604400.0,
                  u'fluidinfo.com/info/url': u'http://example.com/2',
                  u'fluidinfo.com/info/username': u'username'},
                 {u'fluidinfo.com/info/about': [u'about 1'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336518000.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'username'}]},
            result)

    @inlineCallbacks
    def testGetAllFollowedWithNextPageID(self):
        """
        The C{getAllFollowed} method uses the C{nextPageID} to return the
        correct page of comments.
        """
        time = datetime.utcfromtimestamp(1336604400)
        objectID1 = ObjectAPI(self.user).create(u'about 1')
        objectID2 = ObjectAPI(self.user).create(u'about 2')
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username', about=[u'about 1'],
                        when=time - timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username', about=[u'about 2'],
                        when=time, url='http://example.com/2')
        TagValueAPI(self.user).set({objectID1: {u'username/follows': None},
                                    objectID2: {u'username/follows': None}})
        self.store.commit()

        result = yield self.invoke('getAllFollowed', username=u'username',
                                   nextPageID=1336604400.0)
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336518000.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about 1'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336518000.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'username'}]},
            result)

    @inlineCallbacks
    def testGetAllFollowedWithCurrentPageID(self):
        """
        The C{getAllFollowed} method uses the C{currentPageID} to return the
        correct page of comments.
        """
        time = datetime.utcfromtimestamp(1336604400)
        objectID1 = ObjectAPI(self.user).create(u'about 1')
        objectID2 = ObjectAPI(self.user).create(u'about 2')
        comments = SecureCommentAPI(self.user)
        comments.create(u'Comment 1', u'username', about=[u'about 1'],
                        when=time + timedelta(days=1),
                        url='http://example.com/1')
        comments.create(u'Comment 2', u'username', about=[u'about 2'],
                        when=time, url='http://example.com/2')
        TagValueAPI(self.user).set({objectID1: {u'username/follows': None},
                                    objectID2: {u'username/follows': None}})
        self.store.commit()

        result = yield self.invoke('getAllFollowed', username=u'username',
                                   currentPageID=1336604400.0)
        result = loads(result)['result']
        self.assertEqual(
            {'nextPageID': None,
             'currentPageID': 1336690800.0,
             'comments': [
                 {u'fluidinfo.com/info/about': [u'about 1'],
                  u'fluidinfo.com/info/text': u'Comment 1',
                  u'fluidinfo.com/info/timestamp': 1336690800.0,
                  u'fluidinfo.com/info/url': u'http://example.com/1',
                  u'fluidinfo.com/info/username': u'username'}]},
            result)

    @inlineCallbacks
    def testGetAllFollowedWithMalformedNextPageID(self):
        """
        The C{getAllFollowed} method raises an error if the C{nextPageID}.
        """
        result = yield self.invoke('getAllFollowed', username=u'username',
                                   nextPageID='malformed')
        self.assertEqual({u'jsonrpc': u'2.0',
                          u'id': 100,
                          u'error': {
                              u'message': u"Couldn't parse nextPageID.",
                              u'code': BAD_REQUEST}},
                         loads(result))

    @inlineCallbacks
    def testGetAllFollowedWithMalformedCurrentPageID(self):
        """
        The C{getAllFollowed} method raises an error if the C{currentPageID}.
        """
        result = yield self.invoke('getAllFollowed', username=u'username',
                                   currentPageID='malformed')
        self.assertEqual({u'jsonrpc': u'2.0',
                          u'id': 100,
                          u'error': {
                              u'message': u"Couldn't parse currentPageID.",
                              u'code': BAD_REQUEST}},
                         loads(result))

    @inlineCallbacks
    def testGetAllFollowedReturnsNextPageID(self):
        """
        The C{getAllFollowed} method returns a C{nextPageID} value when
        another page of comments could be loaded.
        """
        time = datetime.utcfromtimestamp(1336604400)
        objectID = ObjectAPI(self.user).create(u'about')
        TagValueAPI(self.user).set({objectID: {u'username/follows': None}})
        comments = SecureCommentAPI(self.user)
        for i in range(26):
            comments.create(u'Comment', u'username', about=[u'about'],
                            when=time - timedelta(minutes=i),
                            url='http://example.com/comment')
        self.store.commit()

        result = yield self.invoke('getAllFollowed', username='username')
        result = loads(result)['result']
        self.assertEqual(1336602960, result['nextPageID'])
        self.assertEqual(25, len(result['comments']))

    @inlineCallbacks
    def testGetFollowedObjectsWithoutFollows(self):
        """
        The C{getFollowedObjects} method returns an empty C{list} if no
        objects are being followed by the specified user.
        """
        result = yield self.invoke('getFollowedObjects', username=u'username')
        self.assertEqual({u'id': 100, u'jsonrpc': u'2.0',
                          u'result': {u'nextPageID': None, u'objects': []}},
                         loads(result))

    @inlineCallbacks
    def testGetFollowedObjects(self):
        """
        The C{getFollowedObjects} method returns a list of objects followed by
        the specified user along with an indication if the currently logged in
        user follows those objects too.
        """
        objectID1 = ObjectAPI(self.user).create(u'about 1')
        objectID2 = ObjectAPI(self.user).create(u'about 2')
        TagValueAPI(self.user).set({objectID1: {u'username/follows': None},
                                    objectID2: {u'username/follows': None}})
        self.store.commit()
        result = yield self.invoke('getFollowedObjects', username=u'username')
        result = loads(result)['result']
        self.assertEqual(None, result['nextPageID'])
        aboutValues = [u'about 1', u'about 2']
        self.assertTrue(2, len(result['objects']))
        # Can't be certain of the order the objects will be returned given that
        # they'll have the same creationTime value in the database.
        for obj in result['objects']:
            self.assertTrue(obj['about'] in aboutValues)
            self.assertEqual(True, obj['following'])

    @inlineCallbacks
    def testGetFollowedObjectsWithNextPageID(self):
        """
        The C{getFollowedObjects} method uses the C{nextPageID} to return the
        correct page of objects.
        """
        objectID1 = ObjectAPI(self.user).create(u'about 1')
        objectID2 = ObjectAPI(self.user).create(u'about 2')
        TagValueAPI(self.user).set({objectID1: {u'username/follows': None}})
        self.store.commit()
        timestamp = get_time()
        TagValueAPI(self.user).set({objectID2: {u'username/follows': None}})
        self.store.commit()

        result = yield self.invoke('getFollowedObjects', username=u'username',
                                   nextPageID=timestamp)
        result = loads(result)['result']
        self.assertEqual(None, result['nextPageID'])
        self.assertEqual(1, len(result['objects']))
        self.assertEqual(u'about 1', result['objects'][0]['about'])

    @inlineCallbacks
    def testGetFollowsWithMalformedNextPageID(self):
        """
        The C{getFollowedObjects} method raises an error if the C{nextPageID}
        is malformed.
        """
        result = yield self.invoke('getFollowedObjects', username=u'username',
                                   nextPageID='malformed')
        self.assertEqual({u'jsonrpc': u'2.0',
                          u'id': 100,
                          u'error': {
                              u'message': u"Couldn't parse nextPageID.",
                              u'code': BAD_REQUEST}},
                         loads(result))

    @inlineCallbacks
    def testGetFollowedObjectsWithURLObjectType(self):
        """
        The C{getFollowedObjects} method returns a list of URL objects with
        the C{objectType} is a URL.
        """
        objectID1 = ObjectAPI(self.user).create(u'about 1')
        objectID2 = ObjectAPI(self.user).create(u'http://www.google.com')
        TagValueAPI(self.user).set({objectID1: {u'username/follows': None},
                                    objectID2: {u'username/follows': None}})
        self.store.commit()

        result = yield self.invoke('getFollowedObjects', username=u'username',
                                   objectType='url')
        result = loads(result)['result']
        self.assertEqual(1, len(result['objects']))
        self.assertEqual(u'http://www.google.com',
                         result['objects'][0]['about'])

    @inlineCallbacks
    def testGetFollowedObjectsWithUserObjectType(self):
        """
        The C{getFollowedObjects} method returns a list of user objects with
        the C{objectType} is a user.
        """
        objectID1 = ObjectAPI(self.user).create(u'about 1')
        objectID2 = ObjectAPI(self.user).create(u'@paparent')
        TagValueAPI(self.user).set({objectID1: {u'username/follows': None},
                                    objectID2: {u'username/follows': None}})
        self.store.commit()

        result = yield self.invoke('getFollowedObjects', username=u'username',
                                   objectType='user')
        result = loads(result)['result']
        self.assertEqual(1, len(result['objects']))
        self.assertEqual(u'@paparent',
                         result['objects'][0]['about'])

    @inlineCallbacks
    def testGetFollowedObjectsWithHashtagObjectType(self):
        """
        The C{getFollowedObjects} method returns a list of hashtag objects
        with the C{objectType} is a hashtag.
        """
        objectID1 = ObjectAPI(self.user).create(u'about 1')
        objectID2 = ObjectAPI(self.user).create(u'#like')
        TagValueAPI(self.user).set({objectID1: {u'username/follows': None},
                                    objectID2: {u'username/follows': None}})
        self.store.commit()

        result = yield self.invoke('getFollowedObjects', username=u'username',
                                   objectType='hashtag')
        result = loads(result)['result']
        self.assertEqual(1, len(result['objects']))
        self.assertEqual(u'#like',
                         result['objects'][0]['about'])

    @inlineCallbacks
    def testGetFollowedObjectsWithoutURLObjectType(self):
        """
        The C{getFollowedObjects} method returns an empty list if there is no
        object of C{objectType} url.
        """
        objectID1 = ObjectAPI(self.user).create(u'#like')
        objectID2 = ObjectAPI(self.user).create(u'@paparent')
        TagValueAPI(self.user).set({objectID1: {u'username/follows': None},
                                    objectID2: {u'username/follows': None}})
        self.store.commit()

        result = yield self.invoke('getFollowedObjects', username=u'username',
                                   objectType='url')
        result = loads(result)['result']
        self.assertEqual(0, len(result['objects']))

    @inlineCallbacks
    def testGetFollowedObjectsWithoutUserObjectType(self):
        """
        The C{getFollowedObjects} method returns an empty list if there is no
        object of C{objectType} user.
        """
        objectID1 = ObjectAPI(self.user).create(u'#like')
        objectID2 = ObjectAPI(self.user).create(u'http://google.com')
        TagValueAPI(self.user).set({objectID1: {u'username/follows': None},
                                    objectID2: {u'username/follows': None}})
        self.store.commit()

        result = yield self.invoke('getFollowedObjects', username=u'username',
                                   objectType='user')
        result = loads(result)['result']
        self.assertEqual(0, len(result['objects']))

    @inlineCallbacks
    def testGetFollowedObjectsWithoutHashtagObjectType(self):
        """
        The C{getFollowedObjects} method returns an empty list if there is no
        object of C{objectType} hashtag.
        """
        objectID1 = ObjectAPI(self.user).create(u'http://google.com')
        objectID2 = ObjectAPI(self.user).create(u'@paparent')
        TagValueAPI(self.user).set({objectID1: {u'username/follows': None},
                                    objectID2: {u'username/follows': None}})
        self.store.commit()

        result = yield self.invoke('getFollowedObjects', username=u'username',
                                   objectType='hashtag')
        result = loads(result)['result']
        self.assertEqual(0, len(result['objects']))

    @inlineCallbacks
    def testGetFollowsWithMalformedObjectType(self):
        """
        The C{getFollowedObjects} method raises an error if the C{objectType}
        is unknown.
        """
        result = yield self.invoke('getFollowedObjects', username=u'username',
                                   objectType='malformed')
        self.assertEqual({u'jsonrpc': u'2.0',
                          u'id': 100,
                          u'error': {
                              u'message': (u"Unknown object type: %r."
                                           % u'malformed'),
                              u'code': BAD_REQUEST}},
                         loads(result))

    @inlineCallbacks
    def testGetFollowedObjectsReturnsNextPageID(self):
        """
        The C{getFollowedObjects} method returns a C{nextPageID} value when
        another page of objects could be loaded.
        """
        for i in range(26):
            objectID = ObjectAPI(self.user).create(u'about%d' % i)
            TagValueAPI(self.user).set({objectID: {u'username/follows': None}})
            # Moving the commit here so (I suspect) the tags will each have a
            # different timestamp.
            self.store.commit()

        result = yield self.invoke('getFollowedObjects', username='username')
        result = loads(result)['result']
        self.assertNotEqual(None, result['nextPageID'])
        self.assertEqual(20, len(result['objects']))

    @inlineCallbacks
    def testDeleteExistingComment(self):
        """
        The C{delete} method attempts to remove a comment and returns a count
        of the number of comments that were successfully deleted.
        """
        when = datetime.utcnow()
        comments = SecureCommentAPI(self.user)
        values = comments.create(
            u'comment', u'username', when=when, about=[u'chickens'],
            importer=u'digg.com')
        self.store.commit()

        self.assertNotEqual([], comments.getForObject(u'chickens'))
        result = yield self.invoke('delete',
                                   url=values['fluidinfo.com/info/url'])
        result = loads(result)['result']
        self.assertEqual({'deletedComments': 1}, result)
        self.store.commit()

        self.assertEqual([], comments.getForObject(u'chickens'))

    def testDeleteNonexistentComment(self):
        """
        The C{delete} method returns 0 deleted comments when a non-existent
        comment is deleted.
        """
        result = yield self.invoke('delete',
                                   'http://fluidinfo.com/comment/'
                                   'importer/username/2012-08-03T22:04:13')
        result = loads(result)['result']
        self.assertEqual({'deletedComments': 0}, result)

    @inlineCallbacks
    def testUpdateExistingComment(self):
        """The C{update} method updates the text of a comment."""
        when = datetime.utcnow()
        floatTime = timegm(when.utctimetuple()) + float(when.strftime('0.%f'))
        comments = SecureCommentAPI(self.user)
        values = comments.create(
            u'comment', u'username', when=when, about=[u'chickens'],
            importer=u'digg.com')
        url = values['fluidinfo.com/info/url']
        self.store.commit()

        result = yield self.invoke('update',
                                   url=url,
                                   newText=u'new text')
        result = loads(result)['result']
        expected = {
            u'fluidinfo.com/info/about': [u'chickens'],
            u'fluidinfo.com/info/text': u'new text',
            u'fluidinfo.com/info/timestamp': floatTime,
            u'fluidinfo.com/info/url': url,
            u'fluidinfo.com/info/username': u'username'
        }
        self.assertEqual(expected, result)

        self.store.commit()
        [comment] = comments.getForObject(u'chickens')
        self.assertEqual(expected, comment)

    @inlineCallbacks
    def testUpdateWithEmptyURL(self):
        """The C{update} method raises an error if the url is empty."""
        result = yield self.invoke('update', url='', newText=u'new text')
        result = loads(result)
        self.assertEqual({
            u'error': {
                u'code': 400,
                u'message': u'URL is missing or just contains whitespace.'
            },
            u'id': 100,
            u'jsonrpc': u'2.0'}, result)

    @inlineCallbacks
    def testUpdateWithBadURL(self):
        """
        The C{update} method raises an error if the url is not well formed.
        """
        result = yield self.invoke('update', url='http://something',
                                   newText=u'new text')
        result = loads(result)
        self.assertIn(u'error', result)

    @inlineCallbacks
    def testUpdateWithEmptyText(self):
        """
        The C{update} method raises an error if the text is empty.
        """
        result = yield self.invoke('update',
                                   url='http://fluidinfo.com/comment/'
                                   'importer/username/2012-08-03T22:04:13',
                                   newText=u'')
        result = loads(result)
        self.assertIn(u'error', result)
