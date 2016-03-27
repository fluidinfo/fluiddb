from calendar import timegm
from datetime import datetime, timedelta
from json import loads

from fluiddb.data.system import createSystemData
from fluiddb.model.comment import CommentAPI
from fluiddb.model.object import ObjectAPI
from fluiddb.model.user import UserAPI, getUser
from fluiddb.model.value import TagValueAPI
from fluiddb.schema.scripts.trending_hashtags import extractTrendingHashtags
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import ConfigResource, DatabaseResource


class FluidinfoGlobalTrendingHashtagTest(FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(FluidinfoGlobalTrendingHashtagTest, self).setUp()
        createSystemData()
        UserAPI().create([
            (u'username', u'password', u'User', u'user@example.com'),
            (u'fluidinfo.com', u'secret', u'Fluidinfo', u'info@example.com')])
        self.user = getUser(u'username')
        self.comments = CommentAPI(self.user)
        objectAPI = ObjectAPI(self.user)
        self.fluidinfObjectID = objectAPI.create(u'fluidinfo.com')
        self.tag = u'fluidinfo.com/trending-hashtags'

    def _getResult(self):
        """Get the result of the trending hashtag function.

        return: The value stored by the trending hashtag function, converted
            from JSON.
        """
        result = TagValueAPI(self.user).get(
            [self.fluidinfObjectID], paths=[self.tag])
        return loads(result[self.fluidinfObjectID][self.tag].value)

    def testWithNoComments(self):
        """
        The trending hashtag extracter will store the empty list when there
        are no comments at all.
        """
        extractTrendingHashtags(self.store)
        result = self._getResult()
        self.assertEqual([], result)

    def testWithNoHashtags(self):
        """
        The trending hashtag extracter will store the empty list when there
        are no comments with hashtags.
        """
        self.comments.create(u'I am a comment', u'username')
        self.comments.create(u'I am a comment too', u'username')
        extractTrendingHashtags(self.store)
        result = self._getResult()
        self.assertEqual([], result)

    def testDefaultLimit(self):
        """
        The trending hashtag function must use its default (10) limit argument.
        """
        for index in range(12):
            self.comments.create(u'comment1 #hash%s' % index, u'username')
        extractTrendingHashtags(self.store)
        result = self._getResult()
        self.assertEqual(10, len(result))

    def testLimit(self):
        """The trending hashtag function must respect its limit argument."""
        self.comments.create(u'comment1 #hash1', u'username')
        self.comments.create(u'comment2 #hash2', u'username')
        self.comments.create(u'comment3 #hash3', u'username')
        for limit in range(4):
            extractTrendingHashtags(self.store, limit=limit)
            result = self._getResult()
            self.assertEqual(limit, len(result))

    def testDefaultDuration(self):
        """
        The trending hashtag function must use its default (28 day) duration.
        """
        now = datetime.utcnow()
        first = now - timedelta(days=30)
        second = now - timedelta(days=3)
        self.comments.create(u'#hash1', u'username', when=first)
        self.comments.create(u'#hash2', u'username', when=second)
        extractTrendingHashtags(self.store)
        floatWhen = (timegm(second.utctimetuple()) +
                     float(second.strftime('0.%f')))
        result = self._getResult()
        self.assertEqual(
            [{u'count': 1,
              u'usernames': [[u'username', floatWhen]],
              u'value': u'#hash2'}],
            result)

    def testDuration(self):
        """The trending hashtag function must respect a passed duration."""
        now = datetime.utcnow()
        first = now - timedelta(days=8)
        second = now - timedelta(days=3)
        self.comments.create(u'#hash1', u'username', when=first)
        self.comments.create(u'#hash2', u'username', when=second)
        extractTrendingHashtags(self.store, duration=timedelta(days=4))
        floatWhen = (timegm(second.utctimetuple()) +
                     float(second.strftime('0.%f')))
        result = self._getResult()
        self.assertEqual(
            [{u'count': 1,
              u'usernames': [[u'username', floatWhen]],
              u'value': u'#hash2'}],
            result)

    def testManyComments(self):
        """
        When many users are commenting on many hashtags, the trending hashtag
        function must return a result that contains the correct hashtags, in
        the correct order (for the hashtags and users), respecting its default
        hashtag limit (10).
        """
        start = datetime.utcnow()

        for hashtagIndex in range(12):
            hashtag = u'#hashtag-%d' % hashtagIndex
            for userIndex in range(hashtagIndex):
                username = u'username-%d' % userIndex
                when = start - timedelta(hours=hashtagIndex, minutes=userIndex)
                self.comments.create(hashtag, username, when=when)

        # Create an expected stored value in the way that we created the
        # comments.  Note that we should only receive 10 results.
        expected = []
        for offset in range(10):
            hashtagIndex = 11 - offset
            hashtag = u'#hashtag-%d' % hashtagIndex
            usernames = []
            for userIndex in range(hashtagIndex):
                username = u'username-%d' % userIndex
                when = start - timedelta(hours=hashtagIndex, minutes=userIndex)
                floatWhen = (timegm(when.utctimetuple()) +
                             float(when.strftime('0.%f')))
                usernames.append([username, floatWhen])
            expected.append({
                'count': hashtagIndex,
                'usernames': usernames,
                'value': hashtag
            })

        # Check the stored result.
        extractTrendingHashtags(self.store)
        result = self._getResult()
        self.assertEqual(expected, result)
