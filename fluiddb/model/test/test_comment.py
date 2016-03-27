from calendar import timegm
from datetime import datetime, timedelta
from uuid import uuid4

from fluiddb.data.tag import getTags
from fluiddb.data.system import createSystemData
from fluiddb.data.value import getTagValues
from fluiddb.exceptions import FeatureError
from fluiddb.model.comment import (
    CommentAPI, extractAtnames, extractFiles, extractPlustags, extractURLs,
    parseCommentURL, extractHashtags)
from fluiddb.model.object import ObjectAPI
from fluiddb.model.value import TagValueAPI
from fluiddb.model.user import UserAPI, getUser
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    ConfigResource, DatabaseResource, ThreadPoolResource)


class ExtractAtnamesTest(FluidinfoTestCase):
    """Test the extraction of @names from strings."""

    def testEmpty(self):
        """When passed the empty string, no about values should be returned."""
        result = extractAtnames('')
        self.assertEqual([], result)

    def testPlaintext(self):
        """Given a string that's regular text, no about values are found."""
        result = extractAtnames('hey')
        self.assertEqual([], result)

    def testAtname(self):
        """Given a string that's a single @name, identify it."""
        result = extractAtnames('@name')
        self.assertEqual(['@name'], result)

    def testCaseIsPreserved(self):
        """The case of an @name should be preserved."""
        result = extractAtnames('@MyName')
        self.assertEqual(['@MyName'], result)

    def testAtnameThenPunc(self):
        """Given an @name followed by punctuation, identify the atname."""
        result = extractAtnames('@name,!?')
        self.assertEqual(['@name'], result)

    def testAtPunc(self):
        """An @ followed by punctuation should not be identified."""
        result = extractAtnames('@,.!')
        self.assertEqual([], result)

    def testEmail(self):
        """Given a string that's an email address, don't identify it."""
        result = extractAtnames('name@domain.com')
        self.assertEqual([], result)

    def testParenThenAtname(self):
        """Given (@name), identify the atname."""
        result = extractAtnames('My (@name) is Cthulhu')
        self.assertEqual(['@name'], result)


class ExtractHashtagsTest(FluidinfoTestCase):
    """Test the extraction of #hashtags from strings."""

    def testEmpty(self):
        """When passed the empty string, no about values should be returned."""
        result = extractHashtags('')
        self.assertEqual([], result)

    def testPlaintext(self):
        """Given a string that's regular text, no about values are found."""
        result = extractHashtags('hey')
        self.assertEqual([], result)

    def testHashtag(self):
        """Given a string that's a single hashtag, identify the hashtag."""
        result = extractHashtags('#hey')
        self.assertEqual(['#hey'], result)

    def testHashtagWithDash(self):
        """L{extractHashtags} correctly identifies hashtags with dashes."""
        self.assertEqual(['#hash-tag'], extractHashtags('#hash-tag'))

    def testCaseIsPreserved(self):
        """hashtag case should be preserved."""
        result = extractHashtags('#OccupyWallStreet')
        self.assertEqual(['#OccupyWallStreet'], result)

    def testParenThenHashtag(self):
        """Given (#hashtag), identify the hashtag."""
        result = extractHashtags('My (#hashtag) is Cthulhu')
        self.assertEqual(['#hashtag'], result)


class ExtractPlustagsTest(FluidinfoTestCase):
    """Test the extraction of +plustags from strings."""

    def testEmpty(self):
        """When passed the empty string, no about values should be returned."""
        result = extractPlustags('')
        self.assertEqual([], result)

    def testPlaintext(self):
        """Given a string that's regular text, no about values are found."""
        result = extractPlustags('hey')
        self.assertEqual([], result)

    def testPlustag(self):
        """Given a string that's a single plustag, identify the plustag."""
        result = extractPlustags('+hey')
        self.assertEqual(['+hey'], result)

    def testMultiplePlustags(self):
        """Given a string with multiple plustags, identify them all."""
        result = extractPlustags('+hey +you +there')
        self.assertEqual(['+hey', '+you', '+there'], result)

    def testPlustagWithDash(self):
        """L{extractPlustags} correctly identifies plustags with dashes."""
        self.assertEqual(['+plus-tag'], extractPlustags('+plus-tag'))

    def testCaseIsPreserved(self):
        """plustag case should be preserved."""
        result = extractPlustags('+OccupyWallStreet')
        self.assertEqual(['+OccupyWallStreet'], result)

    def testParenThenCase(self):
        """Given (+case), identify the case."""
        result = extractPlustags('My (+plustag) is Cthulhu')
        self.assertEqual(['+plustag'], result)


class ExtractURLsTest(FluidinfoTestCase):
    """Test the extraction of URLs from strings."""

    def testEmpty(self):
        """When passed the empty string, no about values should be returned."""
        result = extractURLs('')
        self.assertEqual([], result)

    def testPlaintext(self):
        """Given a string that's regular text, no about values are found."""
        result = extractURLs('hey')
        self.assertEqual([], result)

    def testLocalhost(self):
        """A URL with a domain of 'localhost' should be identified."""
        result = extractURLs('http://localhost')
        self.assertEqual(['http://localhost'], result)

    def testURL(self):
        """A single URL should be identified."""
        result = extractURLs('http://games.com')
        self.assertEqual(['http://games.com'], result)

    def testURLAfterNewline(self):
        """A URL that appears after a newline should be identified."""
        result = extractURLs('Hey\nhttp://games.com')
        self.assertEqual(['http://games.com'], result)

    def testURLSpaceWord(self):
        """
        A single URL followed by a space and then plain word should result
        in just the URL being extracted.
        """
        result = extractURLs('http://abc.com text')
        self.assertEqual(['http://abc.com'], result)

    def testHTTPSURL(self):
        """A single HTTPS URL should be identified."""
        result = extractURLs('https://games.com')
        self.assertEqual(['https://games.com'], result)

    def testCaseIsPreserved(self):
        """A URL should be returned in its original case."""
        result = extractURLs('http://GAMES.com')
        self.assertEqual(['http://GAMES.com'], result)

    def testTwoURLs(self):
        """Two URLs should both be identified."""
        result = extractURLs('http://games.com http://blah.com')
        self.assertEqual(['http://games.com', 'http://blah.com'], result)

    def testTwoIdenticalURLs(self):
        """Two identical URLs should be collapsed into one."""
        result = extractURLs('http://blah.com http://blah.com')
        self.assertEqual(['http://blah.com'], result)

    def testJustURLWithLeadingWhitespace(self):
        """A single URL with leading spaces should be identified."""
        result = extractURLs('  http://games.com')
        self.assertEqual(['http://games.com'], result)

    def testJustURLWithTrailingWhitespace(self):
        """A single URL with trailing spaces should be identified."""
        result = extractURLs('http://games.com  ')
        self.assertEqual(['http://games.com'], result)

    def testJustURLWithWhitespaceBeforeAndAfter(self):
        """A single URL with leading & trailing spaces should be identified."""
        result = extractURLs('  http://games.com   ')
        self.assertEqual(['http://games.com'], result)

    def testURLWithOneArg(self):
        """A URL with a single name=value arg should be identified."""
        result = extractURLs('http://games.com?dog=cat')
        self.assertEqual(['http://games.com?dog=cat'], result)

    def testURLWithArgs(self):
        """A URL with multiple name=value args should be identified."""
        result = extractURLs('http://games.com?dog=cat&hot=cold')
        self.assertEqual(['http://games.com?dog=cat&hot=cold'], result)

    def testURLWithHash(self):
        """A URL with a #hash should be identified."""
        result = extractURLs('http://games.com#here')
        self.assertEqual(['http://games.com#here'], result)

    def testURLWithArgAndHash(self):
        """A URL with a argument and a #hash should be identified."""
        result = extractURLs('http://games.com?boy=girl#here')
        self.assertEqual(['http://games.com?boy=girl#here'], result)

    def testEmail(self):
        """Given a string that's an email address, don't identify it."""
        result = extractURLs('name@domain.com')
        self.assertEqual([], result)

    def testURLWithParentheses(self):
        """A URL that contains parentheses must be identified."""
        result = extractURLs('http://en.wikipedia.org/wiki/Set_(psychology)')
        self.assertEqual(['http://en.wikipedia.org/wiki/Set_(psychology)'],
                         result)


class ExtractFilesTest(FluidinfoTestCase):
    """Test the extraction of files from strings."""

    def testEmpty(self):
        """When passed the empty string, no about values should be returned."""
        result = extractFiles('')
        self.assertEqual([], result)

    def testPlaintext(self):
        """Given a string that's regular text, no about values are found."""
        result = extractFiles('hey')
        self.assertEqual([], result)

    def testFile(self):
        """A simple file should be identified."""
        result = extractFiles('file:doc:eec4f5eeddcfdf229acdbdfa05fd5f25f625e'
                              '9bca661a8393a4e465e00075be0')
        self.assertEqual(['file:doc:eec4f5eeddcfdf229acdbdfa05fd5f25f625e'
                          '9bca661a8393a4e465e00075be0'], result)

    def testFileWithNoType(self):
        """A simple file with no type should be identified."""
        result = extractFiles('file:eec4f5eeddcfdf229acdbdfa05fd5f25f625e'
                              '9bca661a8393a4e465e00075be0')
        self.assertEqual(['file:eec4f5eeddcfdf229acdbdfa05fd5f25f625e'
                          '9bca661a8393a4e465e00075be0'], result)

    def testFileWithShortHash(self):
        """A simple file with a short hash is not idenfiyed."""
        result = extractFiles('file:doc:abab')
        self.assertEqual([], result)

    def testFileWithBadHash(self):
        """A simple file with a bad hash is not idenfiyed."""
        result = extractFiles('file:doc:eec4f5eeddcfdf229acdbdfa05fd5f25f625e'
                              '9bca661a8393a4e465e000z5be0')
        self.assertEqual([], result)

    def testFileAfterNewline(self):
        """A file that appears after a newline should be identified."""
        result = extractFiles('Hey\nfile:doc:eec4f5eeddcfdf229acdbdfa05fd5f25'
                              'f625e9bca661a8393a4e465e00075be0')
        self.assertEqual(['file:doc:eec4f5eeddcfdf229acdbdfa05fd5f25f625e'
                          '9bca661a8393a4e465e00075be0'], result)

    def testFileSpaceWord(self):
        """
        A single file followed by a space and then plain word should result
        in just the file being extracted.
        """
        result = extractFiles('file:doc:eec4f5eeddcfdf229acdbdfa05fd5f25f625e'
                              '9bca661a8393a4e465e00075be0 text')
        self.assertEqual(['file:doc:eec4f5eeddcfdf229acdbdfa05fd5f25f625e'
                          '9bca661a8393a4e465e00075be0'], result)

    def testTwoFiles(self):
        """Two files should both be identified."""
        result = extractFiles('file:doc:eec4f5eeddcfdf229acdbdfa05fd5f25f625e'
                              '9bca661a8393a4e465e00075be0 file:pdf:'
                              '2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa742'
                              '5e73043362938b9824')
        self.assertEqual(['file:doc:eec4f5eeddcfdf229acdbdfa05fd5f25f625e'
                          '9bca661a8393a4e465e00075be0',
                          'file:pdf:2cf24dba5fb0a30e26e83b2ac5b9e29e1b161'
                          'e5c1fa7425e73043362938b9824'], result)

    def testTwoIdenticalFiles(self):
        """Two identical files should be collapsed into one."""
        result = extractFiles('file:doc:eec4f5eeddcfdf229acdbdfa05fd5f25f625e'
                              '9bca661a8393a4e465e00075be0 '
                              'file:doc:eec4f5eeddcfdf229acdbdfa05fd5f25f625e'
                              '9bca661a8393a4e465e00075be0')
        self.assertEqual(['file:doc:eec4f5eeddcfdf229acdbdfa05fd5f25f625e'
                          '9bca661a8393a4e465e00075be0'], result)

    def testJustFileWithLeadingWhitespace(self):
        """A single file with leading spaces should be identified."""
        result = extractFiles(' file:doc:eec4f5eeddcfdf229acdbdfa05fd5f25f625e'
                              '9bca661a8393a4e465e00075be0')
        self.assertEqual(['file:doc:eec4f5eeddcfdf229acdbdfa05fd5f25f625e'
                          '9bca661a8393a4e465e00075be0'], result)

    def testJustFileWithTrailingWhitespace(self):
        """A single file with trailing spaces should be identified."""
        result = extractFiles('file:doc:eec4f5eeddcfdf229acdbdfa05fd5f25f625e'
                              '9bca661a8393a4e465e00075be0  ')
        self.assertEqual(['file:doc:eec4f5eeddcfdf229acdbdfa05fd5f25f625e'
                          '9bca661a8393a4e465e00075be0'], result)

    def testJustFileWithWhitespaceBeforeAndAfter(self):
        """
        A single file with leading and trailing spaces should be identified.
        """
        result = extractFiles(' file:doc:eec4f5eeddcfdf229acdbdfa05fd5f25f625e'
                              '9bca661a8393a4e465e00075be0  ')
        self.assertEqual(['file:doc:eec4f5eeddcfdf229acdbdfa05fd5f25f625e'
                          '9bca661a8393a4e465e00075be0'], result)


class CommentAPITestMixin(object):

    def testResultAndTagStorage(self):
        """
        When all possible options are specified, the returned C{dict} must be
        exactly as expected and the tag values must exist in FluidDB on the
        comment object.
        """
        when = datetime.utcnow()
        floatTime = timegm(when.utctimetuple()) + float(when.strftime('0.%f'))
        isoTime = when.isoformat()
        objectAPI = ObjectAPI(self.user)
        objectID = objectAPI.create(u'tumblr joe %s' % isoTime)
        result = self.comments.create(
            u'#h1 @a1 http://abc.com #H2 @A2 http://DEF.com text', u'joe',
            when=when, about=[u'chickens', u'http://ABC.com'],
            importer=u'tumblr', url=u'http://tumblr.com/post123')
        expected = {
            'fluidinfo.com/info/about': [
                u'chickens', u'http://ABC.com', u'http://abc.com',
                u'http://DEF.com', u'#h1', u'#h2', u'@a1', u'@a2'],
            'fluidinfo.com/info/text': (u'#h1 @a1 http://abc.com #H2 @A2 '
                                        u'http://DEF.com text'),
            'fluidinfo.com/info/timestamp': floatTime,
            'fluidinfo.com/info/url': u'http://tumblr.com/post123',
            'fluidinfo.com/info/username': u'joe',
        }
        self.assertEqual(expected, result)

        # Test the values are actually present in FluidDB
        tagValueAPI = TagValueAPI(self.user)
        values = tagValueAPI.get([objectID])[objectID]
        self.assertEqual(result['fluidinfo.com/info/about'],
                         values[u'fluidinfo.com/info/about'].value)
        self.assertEqual(result['fluidinfo.com/info/username'],
                         values[u'fluidinfo.com/info/username'].value)
        self.assertEqual(result['fluidinfo.com/info/url'],
                         values[u'fluidinfo.com/info/url'].value)
        self.assertEqual(result['fluidinfo.com/info/text'],
                         values[u'fluidinfo.com/info/text'].value)
        self.assertEqual(result['fluidinfo.com/info/timestamp'],
                         values[u'fluidinfo.com/info/timestamp'].value)

    def testCommentWithNoAboutValues(self):
        """
        when the comment contains no about values (i.e., no URLs, no
        atnames, and no hashtags), the result C{dict} must have empty
        values in the corresponding keys.
        """
        result = self.comments.create(u'plain text', u'joe')
        self.assertEqual([], result['fluidinfo.com/info/about'])

    def testCreateWithoutTimestamp(self):
        """
        When no timestamp is passed, L{CommentAPI.create} will use the
        current UTC time. Make sure a C{float} 'timestamp' key appears in the
        result, and that its corresponding ISO 8601 value appears at the end
        of the about value used for the comment object.
        """
        result = self.comments.create(u'Comment text', u'username')
        timestamp = result['fluidinfo.com/info/timestamp']
        self.assertTrue(isinstance(timestamp, float))
        isoTime = result['fluidinfo.com/info/url'][
            len('https://fluidinfo.com/comment/fluidinfo.com/username/'):]
        when = datetime.strptime(isoTime, '%Y-%m-%dT%H:%M:%S.%f')
        self.assertEqual(
            timestamp,
            timegm(when.utctimetuple()) + float(when.strftime('0.%f')),)

    def testURLCommentAboutValue(self):
        """
        When the comment about value is a URL, it must appear in the list of
        about values in the result.
        """
        result = self.comments.create(u'text', u'joe',
                                      about=[u'http://MySite.com/x.html'])
        self.assertEqual([u'http://MySite.com/x.html'],
                         result['fluidinfo.com/info/about'])

    def testMultipleURLCommentAboutValue(self):
        """
        When the comment about value has multiple URLs, they must appear in the
        list of about values in the result.
        """
        urls = [u'http://Site1.com', u'http://Site2.com/x.html',
                u'http://Site3.com/y.html']
        result = self.comments.create(u'text', u'joe', about=urls)
        self.assertEqual(urls, result['fluidinfo.com/info/about'])

    def testAtnameCommentAboutValue(self):
        """
        When the comment about value is an @name, it must appear (in lowercase)
        in the list of about values in the result.
        """
        result = self.comments.create(u'txt', u'joe', about=[u'@Dude'])
        self.assertEqual([u'@dude'],
                         result['fluidinfo.com/info/about'])

    def testMultipleAtnameCommentAboutValue(self):
        """
        When the comment about value contains multiple @names, they must
        appear (in lowercase) in the list of about values in the result.
        """
        result = self.comments.create(u'text', u'joe',
                                      about=[u'@a1', u'@a2'])
        self.assertEqual([u'@a1', u'@a2'],
                         result['fluidinfo.com/info/about'])

    def testMultipleAtnameWithWhitespaceCommentAboutValue(self):
        """
        When the comment about value contains multiple @names, they must
        appear (in lowercase) in the list of about values in the result, and
        any surrounding whitespace must be stripped from them.
        """
        result = self.comments.create(u'text', u'joe',
                                      about=[u' @a1 ', u' @a2 '])
        self.assertEqual([u'@a1', u'@a2'],
                         result['fluidinfo.com/info/about'])

    def testHashtagCommentAboutValueInMixedCaseHashtagInTextInLowercase(self):
        """
        When the comment about value is a hashtag in mixed case and the hashtag
        also appears in the comment text (in a different case), it must appear
        once (lowercased) in the list of about values in the result.
        """
        result = self.comments.create(u'#DogS', u'joe', about=[u'#DOGS'])
        self.assertEqual([u'#dogs'],
                         result['fluidinfo.com/info/about'])

    def testIllegalImporter(self):
        """The importer name cannot contain a space."""
        self.assertRaises(FeatureError, self.comments.create,
                          u'Comment', u'username', importer=u'bad importer')

    def testNoCommentText(self):
        """Comment text must be passed to the creator."""
        self.assertRaises(FeatureError, self.comments.create,
                          None, u'username')

    def testEmptyCommentText(self):
        """Non-empty comment text must be passed to the creator."""
        self.assertRaises(FeatureError, self.comments.create,
                          u'', u'username')

    def testNoURL(self):
        """
        When no url is passed, an http://fluidinfo.com/fluidinfo.com/username/
        url must be in the payload.
        """
        result = self.comments.create(u'Comment text', u'username')
        self.assertTrue(result['fluidinfo.com/info/url'].startswith(
            'https://fluidinfo.com/comment/fluidinfo.com/username/'))

    def testCreateWithExtractAtnamesConfigOption(self):
        """
        L{CommentAPI.create} associates the new comment with atnames in the
        comment text only if the C{extract-atnames} config option is enabled.
        """
        self.config.set('comments', 'extract-atnames', 'true')
        result = self.comments.create(u'@Name', u'username')
        self.assertEqual([u'@name'], result['fluidinfo.com/info/about'])
        self.assertEqual(1, len(self.comments.getForObject(u'@name')))

    def testCreateWithoutExtractAtnamesConfigOption(self):
        """
        L{CommentAPI.create} does not associate the new comment with atnames
        in the comment text if the C{extract-atnames} config option is
        disabled.
        """
        self.config.set('comments', 'extract-atnames', 'false')
        result = self.comments.create(u'@name #hash http://example.com',
                                      u'username')
        self.assertEqual([u'http://example.com', u'#hash'],
                         result['fluidinfo.com/info/about'])
        self.assertEqual(0, len(self.comments.getForObject(u'@name')))

    def testCreateWithExtractHashtagsConfigOption(self):
        """
        L{CommentAPI.create} associates the new comment with hashtags in the
        comment text only if the C{extract-hashtags} config option is enabled.
        """
        self.config.set('comments', 'extract-hashtags', 'true')
        result = self.comments.create(u'#Hash', u'username')
        self.assertEqual([u'#hash'], result['fluidinfo.com/info/about'])
        self.assertEqual(1, len(self.comments.getForObject(u'#hash')))

    def testCreateWithoutExtractHashtagsConfigOption(self):
        """
        L{CommentAPI.create} does not associate the new comment with hashtags
        in the comment text if the C{extract-hashtags} config option is
        disabled.
        """
        self.config.set('comments', 'extract-hashtags', 'false')
        result = self.comments.create(u'@name #hash http://example.com',
                                      u'username')
        self.assertEqual([u'http://example.com', u'@name'],
                         result['fluidinfo.com/info/about'])
        self.assertEqual(0, len(self.comments.getForObject(u'#hash')))

    def testCreateWithExtractPlustagsConfigOption(self):
        """
        L{CommentAPI.create} associates the new comment with plustags in the
        comment text only if the C{extract-plustags} config option is enabled.
        """
        self.config.set('comments', 'extract-plustags', 'true')
        result = self.comments.create(u'+Plus', u'username')
        self.assertEqual([u'+plus'], result['fluidinfo.com/info/about'])
        self.assertEqual(1, len(self.comments.getForObject(u'+plus')))

    def testCreateWithoutExtractPlustagsConfigOption(self):
        """
        L{CommentAPI.create} does not associate the new comment with plustags
        in the comment text if the C{extract-plustags} config option is
        disabled.
        """
        self.config.set('comments', 'extract-plustags', 'false')
        result = self.comments.create(u'@name +plus http://example.com',
                                      u'username')
        self.assertEqual([u'http://example.com', u'@name'],
                         result['fluidinfo.com/info/about'])
        self.assertEqual(0, len(self.comments.getForObject(u'+plus')))

    def testCreateWithExtractUrlsConfigOption(self):
        """
        L{CommentAPI.create} associates the new comment with urls in the
        comment text only if the C{extract-urls} config option is enabled.
        """
        self.config.set('comments', 'extract-urls', 'true')
        result = self.comments.create(u'http://example.com', u'username')
        self.assertEqual([u'http://example.com'],
                         result['fluidinfo.com/info/about'])
        self.assertEqual(
            1, len(self.comments.getForObject(u'http://example.com')))

    def testCreateWithoutExtractUrlsConfigOption(self):
        """
        L{CommentAPI.create} does not associate the new comment with urls in
        the comment text if the C{extract-urls} config option is disabled.
        """
        self.config.set('comments', 'extract-urls', 'false')
        result = self.comments.create(u'@name #hash http://example.com',
                                      u'username')
        self.assertEqual([u'#hash', u'@name'],
                         result['fluidinfo.com/info/about'])
        self.assertEqual(
            0, len(self.comments.getForObject(u'http://example.com')))

    def testCreateWithExtractFilesConfigOption(self):
        """
        L{CommentAPI.create} associates the new comment with files in the
        comment text only if the C{extract-files} config option is enabled.
        """
        self.config.set('comments', 'extract-files', 'true')
        self.config.set('comments', 'file-object', ':files:')
        result = self.comments.create(u'file:doc:eec4f5eeddcfdf229acdbdfa05fd5'
                                      'f25f625e9bca661a8393a4e465e00075be0',
                                      u'username')
        self.assertEqual([u'file:doc:eec4f5eeddcfdf229acdbdfa05fd5f25f625e'
                          u'9bca661a8393a4e465e00075be0', u':files:'],
                         result['fluidinfo.com/info/about'])
        self.assertEqual(
            1,
            len(self.comments.getForObject(
                u'file:doc:eec4f5eeddcfdf229acdbdfa05fd5'
                'f25f625e9bca661a8393a4e465e00075be0')))

        self.assertEqual(
            1,
            len(self.comments.getForObject(u':files:')))

    def testCreateWithoutExtractFilesConfigOption(self):
        """
        L{CommentAPI.create} does not associate the new comment with files in
        the comment text if the C{extract-files} config option is disabled.
        """
        self.config.set('comments', 'extract-files', 'false')
        self.config.set('comments', 'file-object', ':files:')
        result = self.comments.create(u'file:doc:eec4f5eeddcfdf229acdbdfa05fd5'
                                      'f25f625e9bca661a8393a4e465e00075be0',
                                      u'username')
        self.assertEqual([], result['fluidinfo.com/info/about'])
        self.assertEqual(
            0,
            len(self.comments.getForObject(
                u'file:doc:eec4f5eeddcfdf229acdbdfa05fd5'
                'f25f625e9bca661a8393a4e465e00075be0')))
        self.assertEqual(
            0,
            len(self.comments.getForObject(u':files:')))

    def testGetForObject(self):
        """
        L{CommentAPI.getForObject} returns the comments made on an object.
        """
        self.comments.create(u'comment 1', u'username', about=[u'target'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(900000000))

        self.comments.create(u'comment 2', u'username', about=[u'target'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(800000000))

        self.comments.create(u'comment 3', u'username', about=None,
                             url=u'http://example2.com',
                             when=datetime.fromtimestamp(700000000))

        expected = [{u'fluidinfo.com/info/about': [u'target'],
                     u'fluidinfo.com/info/text': u'comment 1',
                     u'fluidinfo.com/info/timestamp': 900000000.0,
                     u'fluidinfo.com/info/url': u'http://example.com',
                     u'fluidinfo.com/info/username': u'username'},
                    {u'fluidinfo.com/info/about': [u'target'],
                     u'fluidinfo.com/info/text': u'comment 2',
                     u'fluidinfo.com/info/timestamp': 800000000.0,
                     u'fluidinfo.com/info/url': u'http://example2.com',
                     u'fluidinfo.com/info/username': u'username'}]
        self.assertEqual(expected, self.comments.getForObject(u'target'))

    def testGetForObjectWithUsername(self):
        """
        L{CommentAPI.getForObject} only returns comments made by the specified
        user when the C{username} parameter is specified.
        """
        self.comments.create(u'comment 1', u'username1', about=[u'target'],
                             url=u'http://example.com/1',
                             when=datetime.utcfromtimestamp(900000000))
        self.comments.create(u'comment 2', u'username2', about=[u'target'],
                             url=u'http://example.com/2',
                             when=datetime.utcfromtimestamp(800000000))
        self.assertEqual([{u'fluidinfo.com/info/about': [u'target'],
                           u'fluidinfo.com/info/text': u'comment 1',
                           u'fluidinfo.com/info/timestamp': 900000000.0,
                           u'fluidinfo.com/info/url': u'http://example.com/1',
                           u'fluidinfo.com/info/username': u'username1'}],
                         self.comments.getForObject(u'target',
                                                    username=u'username1'))

    def testGetForObjectWithUnknownUsername(self):
        """
        L{CommentAPI.getForObject} doesn't return any comments if an unknown
        username is provided.
        """
        self.assertEqual([], self.comments.getForObject(u'target',
                                                        username=u'unknown'))

    def testGetForObjectWithFollowedByUsername(self):
        """
        L{CommentAPI.getForObject} only returns comments made by the L{User}s
        the specified user follows when the C{followedByUsername} parameter is
        specified.
        """
        UserAPI().create([
            (u'friend', u'secret', u'Friend', u'friend@example.com')])
        user = getUser(u'friend')
        TagValueAPI(self.user).set(
            {user.objectID: {u'username/follows': None}})

        self.comments.create(u'comment 1', u'friend', about=[u'about'],
                             url=u'http://example.com/1',
                             when=datetime.utcfromtimestamp(900000000))
        self.comments.create(u'comment 2', u'foe', about=[u'about'],
                             url=u'http://example.com/2',
                             when=datetime.utcfromtimestamp(800000000))
        self.assertEqual(
            [{u'fluidinfo.com/info/about': [u'about'],
              u'fluidinfo.com/info/text': u'comment 1',
              u'fluidinfo.com/info/timestamp': 900000000,
              u'fluidinfo.com/info/url': u'http://example.com/1',
              u'fluidinfo.com/info/username': u'friend'}],
            self.comments.getForObject(u'about',
                                       followedByUsername=u'username'))

    def testGetForObjectWithUnknownFollowedByUsername(self):
        """
        L{CommentAPI.getForObject} only returns comments made by the L{User}s
        the specified user follows when the C{followedByUsername} parameter is
        specified.
        """
        self.comments.create(u'comment 1', u'user1', about=[u'about'],
                             url=u'http://example.com/1',
                             when=datetime.utcfromtimestamp(900000000))
        self.assertEqual(
            [],
            self.comments.getForObject(u'about',
                                       followedByUsername=u'unknown'))

    def testGetForObjectWithFilterTags(self):
        """
        L{CommentAPI.getForObject} only returns comments with the given tag
        when the C{filterTags} parameter is specified.
        """
        when = datetime.utcfromtimestamp(900000000)
        self.comments.create(u'comment 1', u'friend', about=[u'about'],
                             url=u'http://example.com/1',
                             when=when)
        self.comments.create(u'comment 2', u'foe', about=[u'about'],
                             url=u'http://example.com/2',
                             when=datetime.utcfromtimestamp(800000000))

        # Get the comment ID based on the expected about value
        commentAbout = u'fluidinfo.com friend %s' % when.isoformat()
        commentID = ObjectAPI(self.user).create(commentAbout)
        TagValueAPI(self.user).set({commentID: {u'username/tag': None}})

        self.assertEqual(
            [{u'fluidinfo.com/info/about': [u'about'],
              u'fluidinfo.com/info/text': u'comment 1',
              u'fluidinfo.com/info/timestamp': 900000000,
              u'fluidinfo.com/info/url': u'http://example.com/1',
              u'fluidinfo.com/info/username': u'friend'}],
            self.comments.getForObject(u'about', filterTags=[u'username/tag']))

    def testGetForObjectWithfilterAbout(self):
        """
        L{CommentAPI.getForObject} only returns comments made on a given object
        when the C{filterAbout} parameter is specified.
        """
        self.comments.create(u'comment 1', u'friend',
                             about=[u'about', u'+filter'],
                             url=u'http://example.com/1',
                             when=datetime.utcfromtimestamp(900000000))
        self.comments.create(u'comment 2', u'foe',
                             about=[u'about', u'+filter'],
                             url=u'http://example.com/2',
                             when=datetime.utcfromtimestamp(800000000))
        self.comments.create(u'comment 2', u'foe',
                             about=[u'about'],
                             url=u'http://example.com/2',
                             when=datetime.utcfromtimestamp(700000000))

        self.assertEqual(
            [{u'fluidinfo.com/info/about': [u'about', u'+filter'],
              u'fluidinfo.com/info/text': u'comment 1',
              u'fluidinfo.com/info/timestamp': 900000000.0,
              u'fluidinfo.com/info/url': u'http://example.com/1',
              u'fluidinfo.com/info/username': u'friend'},
             {u'fluidinfo.com/info/about': [u'about', u'+filter'],
              u'fluidinfo.com/info/text': u'comment 2',
              u'fluidinfo.com/info/timestamp': 800000000.0,
              u'fluidinfo.com/info/url': u'http://example.com/2',
              u'fluidinfo.com/info/username': u'foe'}],
            self.comments.getForObject(u'about', filterAbout=u'+filter'))

    def testGetForObjectWithFilterTagsAndFollowedByUsername(self):
        """
        L{CommentAPI.getForObject} only returns comments with the given tag
        when the C{filterTags} parameter is specified.
        """
        UserAPI().create([
            (u'friend', u'secret', u'Friend', u'friend@example.com')])
        user = getUser(u'friend')
        TagValueAPI(self.user).set(
            {user.objectID: {u'username/follows': None}})

        when = datetime.utcfromtimestamp(900000000)
        self.comments.create(u'comment 1', u'friend', about=[u'about'],
                             url=u'http://example.com/1',
                             when=when)
        self.comments.create(u'comment 2', u'foe', about=[u'about'],
                             url=u'http://example.com/2',
                             when=when)
        self.comments.create(u'comment 3', u'friend', about=[u'about'],
                             url=u'http://example.com/3',
                             when=datetime.utcfromtimestamp(700000000))

        # Get the comment ID based on the expected about value
        commentAbout = u'fluidinfo.com friend %s' % when.isoformat()
        commentID = ObjectAPI(self.user).create(commentAbout)
        TagValueAPI(self.user).set({commentID: {u'username/tag': None}})

        commentAbout = u'fluidinfo.com foe %s' % when.isoformat()
        commentID = ObjectAPI(self.user).create(commentAbout)
        TagValueAPI(self.user).set({commentID: {u'username/tag': None}})

        self.assertEqual(
            [{u'fluidinfo.com/info/about': [u'about'],
              u'fluidinfo.com/info/text': u'comment 1',
              u'fluidinfo.com/info/timestamp': 900000000,
              u'fluidinfo.com/info/url': u'http://example.com/1',
              u'fluidinfo.com/info/username': u'friend'}],
            self.comments.getForObject(u'about',
                                       filterTags=[u'username/tag'],
                                       followedByUsername=u'username'))

    def testGetForObjectWithNonExistentFilterTags(self):
        """
        L{CommentAPI.getForObject} returns an empty string when C{filterTags}
        does not exist.
        """
        self.comments.create(u'comment 1', u'friend', about=[u'about'],
                             url=u'http://example.com/1',
                             when=datetime.utcfromtimestamp(900000000))
        self.comments.create(u'comment 2', u'foe', about=[u'about'],
                             url=u'http://example.com/2',
                             when=datetime.utcfromtimestamp(800000000))

        self.assertEqual(
            [],
            self.comments.getForObject(u'about', filterTags=[u'username/tag']))

    def testGetForObjectWithLimit(self):
        """
        L{CommentAPI.getForObject} with a limit returns only the C{n} most
        recent comments.
        """
        self.comments.create(u'comment 1', u'username', about=[u'target'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(800000000))

        self.comments.create(u'comment 2', u'username', about=[u'target'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(900000000))
        expected = [{u'fluidinfo.com/info/about': [u'target'],
                     u'fluidinfo.com/info/text': u'comment 2',
                     u'fluidinfo.com/info/timestamp': 900000000.0,
                     u'fluidinfo.com/info/url': u'http://example2.com',
                     u'fluidinfo.com/info/username': u'username'}]
        self.assertEqual(expected,
                         self.comments.getForObject(u'target', limit=1))

    def testGetForObjectWithOlderThan(self):
        """
        L{CommentAPI.getForObject} with an C{olderThan} returns comments older
        than the given argument.
        """
        self.comments.create(u'comment 1', u'username', about=[u'target'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(800000000))

        self.comments.create(u'comment 2', u'username', about=[u'target'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(900000000))
        expected = [{u'fluidinfo.com/info/about': [u'target'],
                     u'fluidinfo.com/info/text': u'comment 1',
                     u'fluidinfo.com/info/timestamp': 800000000.0,
                     u'fluidinfo.com/info/url': u'http://example.com',
                     u'fluidinfo.com/info/username': u'username'}]
        self.assertEqual(
            expected,
            self.comments.getForObject(
                u'target', olderThan=datetime.utcfromtimestamp(900000000)))

    def testGetForObjectWithNewerThan(self):
        """
        L{CommentAPI.getForObject} with a C{newerThan} argument returns
        comments newer than the given argument.
        """
        self.comments.create(u'comment 1', u'username', about=[u'target'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(800000000))

        self.comments.create(u'comment 2', u'username', about=[u'target'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(900000000))
        expected = [{u'fluidinfo.com/info/about': [u'target'],
                     u'fluidinfo.com/info/text': u'comment 2',
                     u'fluidinfo.com/info/timestamp': 900000000.0,
                     u'fluidinfo.com/info/url': u'http://example2.com',
                     u'fluidinfo.com/info/username': u'username'}]
        self.assertEqual(
            expected,
            self.comments.getForObject(
                u'target', newerThan=datetime.utcfromtimestamp(800000000)))

    def testGetForObjectWithNoComments(self):
        """
        L{CommentAPI.getForObject} returns an empty list if there are no
        comments made on a given object.
        """
        self.assertEqual([], self.comments.getForObject(u'target'))

    def testGetForObjectWithAdditionalTagsEmptyList(self):
        """
        L{CommentAPI.getForObject} with an empty C{additionalTags} list returns
        only the default comment tags.
        """
        self.comments.create(u'comment 1', u'username1', about=[u'target'],
                             url=u'http://example.com/1',
                             when=datetime.utcfromtimestamp(900000000))
        self.assertEqual([{u'fluidinfo.com/info/about': [u'target'],
                           u'fluidinfo.com/info/text': u'comment 1',
                           u'fluidinfo.com/info/timestamp': 900000000.0,
                           u'fluidinfo.com/info/url': u'http://example.com/1',
                           u'fluidinfo.com/info/username': u'username1'}],
                         self.comments.getForObject(u'target',
                                                    username=u'username1',
                                                    additionalTags=[]))

    def testGetForObjectWithAdditionalTags(self):
        """
        L{CommentAPI.getForObject} with C{additionalTags} list returns
        additional tags plus default ones.
        """
        when = datetime.utcfromtimestamp(900000000)
        self.comments.create(u'comment', u'username1', about=[u'banana'],
                             url=u'http://example.com/1',
                             when=when)

        # Get the comment ID based on the expected about value
        commentAbout = u'fluidinfo.com username1 %s' % when.isoformat()
        commentID = ObjectAPI(self.user).create(commentAbout)
        TagValueAPI(self.user).set({commentID: {u'minion/lunch': u'paple',
                                                u'minion/dinner': u'banana'}})

        additionalTags = [u'minion/lunch',
                          u'minion/dinner']
        expected = [{u'fluidinfo.com/info/about': [u'banana'],
                     u'fluidinfo.com/info/text': u'comment',
                     u'fluidinfo.com/info/timestamp': 900000000.0,
                     u'fluidinfo.com/info/url': u'http://example.com/1',
                     u'fluidinfo.com/info/username': u'username1',
                     u'minion/lunch': u'paple',
                     u'minion/dinner': u'banana'}]
        self.assertEqual(
            expected,
            self.comments.getForObject(u'banana', username=u'username1',
                                       additionalTags=additionalTags))

    def testGetForObjectWithAdditionalTagsOpaqueValue(self):
        """
        L{CommentAPI.getForObject} where C{additionalTags} contain an opaque
        value return the id, mime-type and size, but not the contents.
        """
        when = datetime.utcfromtimestamp(900000000)
        self.comments.create(u'comment', u'username1', about=[u'banana'],
                             url=u'http://example.com/1',
                             when=when)

        # Get the comment ID based on the expected about value
        commentAbout = u'fluidinfo.com username1 %s' % when.isoformat()
        commentID = ObjectAPI(self.user).create(commentAbout)
        doc = {'mime-type': u'image/gif',
               'contents': 'GIF87a\x01\x00\x01\x00\xf0\x00\x00\xff\xff\xff\x00'
               + '\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01'
               + '\x00;'}
        TagValueAPI(self.user).set({commentID: {u'username/file': doc}})

        expected = [{u'fluidinfo.com/info/about': [u'banana'],
                     u'fluidinfo.com/info/text': u'comment',
                     u'fluidinfo.com/info/timestamp': 900000000.0,
                     u'fluidinfo.com/info/url': u'http://example.com/1',
                     u'fluidinfo.com/info/username': u'username1',
                     u'username/file': {
                         u'id': str(commentID),
                         u'mime-type': u'image/gif',
                         u'size': 35
                     }}]
        self.assertEqual(
            expected,
            self.comments.getForObject(u'banana', username=u'username1',
                                       additionalTags=[u'username/file']))

    def testSummarizeObjectWithoutComments(self):
        """
        L{CommentAPI.summarizeObject} returns a C{dict} without data when no
        comments are available.
        """
        self.assertEqual({'commentCount': 0, 'followers': [],
                          'relatedObjects': {}},
                         self.comments.summarizeObject(u'about'))

    def testSummarizeObjectWithFollowers(self):
        """
        L{CommentAPI.summarizeObject} includes a count of people that follow
        the object.
        """
        objectID = ObjectAPI(self.user).create(u'about')
        TagValueAPI(self.user).set({objectID: {u'username/follows': None}})
        self.assertEqual({'commentCount': 0, 'followers': [u'username'],
                          'relatedObjects': {}},
                         self.comments.summarizeObject(u'about'))

    def testSummarizeObjectWithComments(self):
        """
        L{CommentAPI.summarizeObject} includes a count of comments about the
        object.
        """
        self.comments.create(u'comment', u'username', about=[u'about'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(900000000))
        self.assertEqual({'commentCount': 1, 'followers': [],
                          'relatedObjects': {}},
                         self.comments.summarizeObject(u'about'))

    def testSummarizeObjectsWithRelatedObjects(self):
        """
        L{CommentAPI.summarizeObject} includes a count of all about values the
        comments for the object are related to.
        """
        self.comments.create(u'@name1 #hashtag1 http://example.com',
                             u'username', about=[u'about'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(900000000))
        self.comments.create(u'@name2 #hashtag2 http://example.com',
                             u'username', about=[u'about'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(900000050))
        self.assertEqual(
            {'commentCount': 2, 'followers': [],
             'relatedObjects': {'#hashtag1': 1, '#hashtag2': 1,
                                '@name1': 1, '@name2': 1,
                                'http://example.com': 2}},
            self.comments.summarizeObject(u'about'))

    def testGetRecent(self):
        """L{CommentAPI.getRecent} returns recent comments."""
        self.comments.create(u'comment 1', u'user', about=[u'target 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(900000000))

        self.comments.create(u'comment 2', u'user2', about=[u'target 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(800000000))

        expected = [{u'fluidinfo.com/info/about': [u'target 1'],
                     u'fluidinfo.com/info/text': u'comment 1',
                     u'fluidinfo.com/info/timestamp': 900000000.0,
                     u'fluidinfo.com/info/url': u'http://example.com',
                     u'fluidinfo.com/info/username': u'user'},
                    {u'fluidinfo.com/info/about': [u'target 2'],
                     u'fluidinfo.com/info/text': u'comment 2',
                     u'fluidinfo.com/info/timestamp': 800000000.0,
                     u'fluidinfo.com/info/url': u'http://example2.com',
                     u'fluidinfo.com/info/username': u'user2'}]
        self.assertEqual(expected, self.comments.getRecent())

    def testGetRecentWithLimit(self):
        """
        L{CommentAPI.getRecent} with a limit returns only the C{n} most
        recent comments.
        """
        self.comments.create(u'comment 1', u'user', about=[u'target 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(800000000))

        self.comments.create(u'comment 2', u'user', about=[u'target 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(900000000))
        expected = [{u'fluidinfo.com/info/about': [u'target 2'],
                     u'fluidinfo.com/info/text': u'comment 2',
                     u'fluidinfo.com/info/timestamp': 900000000.0,
                     u'fluidinfo.com/info/url': u'http://example2.com',
                     u'fluidinfo.com/info/username': u'user'}]
        self.assertEqual(expected,
                         self.comments.getRecent(limit=1))

    def testGetRecentWithOlderThan(self):
        """
        L{CommentAPI.getRecent} with an C{olderThan} returns comments older
        than the given argument.
        """
        self.comments.create(u'comment 1', u'user', about=[u'target 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(800000000))

        self.comments.create(u'comment 2', u'user', about=[u'target 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(900000000))
        expected = [{u'fluidinfo.com/info/about': [u'target 1'],
                     u'fluidinfo.com/info/text': u'comment 1',
                     u'fluidinfo.com/info/timestamp': 800000000.0,
                     u'fluidinfo.com/info/url': u'http://example.com',
                     u'fluidinfo.com/info/username': u'user'}]
        self.assertEqual(
            expected,
            self.comments.getRecent(
                olderThan=datetime.utcfromtimestamp(900000000)))

    def testGetRecentWithNewerThan(self):
        """
        L{CommentAPI.getRecent} with a C{newerThan} argument returns
        comments newer than the given argument.
        """
        self.comments.create(u'comment 1', u'user', about=[u'target 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(800000000))

        self.comments.create(u'comment 2', u'user', about=[u'target 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(900000000))
        expected = [{u'fluidinfo.com/info/about': [u'target 2'],
                     u'fluidinfo.com/info/text': u'comment 2',
                     u'fluidinfo.com/info/timestamp': 900000000.0,
                     u'fluidinfo.com/info/url': u'http://example2.com',
                     u'fluidinfo.com/info/username': u'user'}]
        self.assertEqual(
            expected,
            self.comments.getRecent(
                newerThan=datetime.utcfromtimestamp(800000000)))

    def testGetRecentWithNoComments(self):
        """
        L{CommentAPI.getRecent} returns an empty list if there are no
        comments made by the given user.
        """
        self.assertEqual([], self.comments.getRecent())

    def testGetByUser(self):
        """L{CommentAPI.getByUser} returns the comments made by a user."""
        self.comments.create(u'comment 1', u'user', about=[u'target 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(900000000))

        self.comments.create(u'comment 2', u'user', about=[u'target 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(800000000))

        expected = [{u'fluidinfo.com/info/about': [u'target 1'],
                     u'fluidinfo.com/info/text': u'comment 1',
                     u'fluidinfo.com/info/timestamp': 900000000.0,
                     u'fluidinfo.com/info/url': u'http://example.com',
                     u'fluidinfo.com/info/username': u'user'},
                    {u'fluidinfo.com/info/about': [u'target 2'],
                     u'fluidinfo.com/info/text': u'comment 2',
                     u'fluidinfo.com/info/timestamp': 800000000.0,
                     u'fluidinfo.com/info/url': u'http://example2.com',
                     u'fluidinfo.com/info/username': u'user'}]
        self.assertEqual(expected, self.comments.getByUser(u'user'))

    def testByUserWithLimit(self):
        """
        L{CommentAPI.getByUser} with a limit returns only the C{n} most
        recent comments.
        """
        self.comments.create(u'comment 1', u'user', about=[u'target 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(800000000))

        self.comments.create(u'comment 2', u'user', about=[u'target 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(900000000))
        expected = [{u'fluidinfo.com/info/about': [u'target 2'],
                     u'fluidinfo.com/info/text': u'comment 2',
                     u'fluidinfo.com/info/timestamp': 900000000.0,
                     u'fluidinfo.com/info/url': u'http://example2.com',
                     u'fluidinfo.com/info/username': u'user'}]
        self.assertEqual(expected,
                         self.comments.getByUser(u'user', limit=1))

    def testGetByUserWithOlderThan(self):
        """
        L{CommentAPI.getByUser} with an C{olderThan} returns comments older
        than the given argument.
        """
        self.comments.create(u'comment 1', u'user', about=[u'target 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(800000000))

        self.comments.create(u'comment 2', u'user', about=[u'target 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(900000000))
        expected = [{u'fluidinfo.com/info/about': [u'target 1'],
                     u'fluidinfo.com/info/text': u'comment 1',
                     u'fluidinfo.com/info/timestamp': 800000000.0,
                     u'fluidinfo.com/info/url': u'http://example.com',
                     u'fluidinfo.com/info/username': u'user'}]
        self.assertEqual(
            expected,
            self.comments.getByUser(
                u'user', olderThan=datetime.utcfromtimestamp(900000000)))

    def testGetByUserWithNewerThan(self):
        """
        L{CommentAPI.getByUser} with a C{newerThan} argument returns
        comments newer than the given argument.
        """
        self.comments.create(u'comment 1', u'user', about=[u'target 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(800000000))

        self.comments.create(u'comment 2', u'user', about=[u'target 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(900000000))
        expected = [{u'fluidinfo.com/info/about': [u'target 2'],
                     u'fluidinfo.com/info/text': u'comment 2',
                     u'fluidinfo.com/info/timestamp': 900000000.0,
                     u'fluidinfo.com/info/url': u'http://example2.com',
                     u'fluidinfo.com/info/username': u'user'}]
        self.assertEqual(
            expected,
            self.comments.getByUser(
                u'user', newerThan=datetime.utcfromtimestamp(800000000)))

    def testGetByUserWithNoComments(self):
        """
        L{CommentAPI.getByUser} returns an empty list if there are no
        comments made by the given user.
        """
        self.assertEqual([], self.comments.getByUser(u'unknown'))

    def testGetForUser(self):
        """
        L{CommentAPI.getForUser} returns the comments made by a user and on the
        user object.
        """
        self.comments.create(u'hello #kitty', u'username', about=[u'@user'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(900000000))

        self.comments.create(u'comment 2', u'user', about=[u'target 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(800000000))

        expected = [{u'fluidinfo.com/info/about': [u'@user', u'#kitty'],
                     u'fluidinfo.com/info/text': u'hello #kitty',
                     u'fluidinfo.com/info/timestamp': 900000000.0,
                     u'fluidinfo.com/info/url': u'http://example.com',
                     u'fluidinfo.com/info/username': u'username'},
                    {u'fluidinfo.com/info/about': [u'target 2'],
                     u'fluidinfo.com/info/text': u'comment 2',
                     u'fluidinfo.com/info/timestamp': 800000000.0,
                     u'fluidinfo.com/info/url': u'http://example2.com',
                     u'fluidinfo.com/info/username': u'user'}]
        self.assertEqual(expected, self.comments.getForUser(u'user'))

    def testForUserWithLimit(self):
        """
        L{CommentAPI.getForUser} with a limit returns only the C{n} most
        recent comments.
        """
        self.comments.create(u'comment 1', u'username', about=[u'@user'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(800000000))

        self.comments.create(u'hello #kitty', u'user', about=[u'target 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(900000000))

        expected = [{u'fluidinfo.com/info/about': [u'target 2', u'#kitty'],
                     u'fluidinfo.com/info/text': u'hello #kitty',
                     u'fluidinfo.com/info/timestamp': 900000000.0,
                     u'fluidinfo.com/info/url': u'http://example2.com',
                     u'fluidinfo.com/info/username': u'user'}]
        self.assertEqual(expected,
                         self.comments.getForUser(u'user', limit=1))

    def testGetForUserWithOlderThan(self):
        """
        L{CommentAPI.getByUser} with an C{olderThan} returns comments older
        than the given argument.
        """
        self.comments.create(u'comment 1', u'user', about=[u'target 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(800000000))

        self.comments.create(u'hello @user', u'username', about=[u'target 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(900000000))
        expected = [{u'fluidinfo.com/info/about': [u'target 1'],
                     u'fluidinfo.com/info/text': u'comment 1',
                     u'fluidinfo.com/info/timestamp': 800000000.0,
                     u'fluidinfo.com/info/url': u'http://example.com',
                     u'fluidinfo.com/info/username': u'user'}]
        self.assertEqual(
            expected,
            self.comments.getForUser(
                u'user', olderThan=datetime.utcfromtimestamp(900000000)))

    def testGetForUserWithNewerThan(self):
        """
        L{CommentAPI.getByUser} with a C{newerThan} argument returns
        comments newer than the given argument.
        """
        self.comments.create(u'comment 1', u'user', about=[u'target 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(800000000))

        self.comments.create(u'comment 2', u'user', about=[u'target 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(900000000))
        expected = [{u'fluidinfo.com/info/about': [u'target 2'],
                     u'fluidinfo.com/info/text': u'comment 2',
                     u'fluidinfo.com/info/timestamp': 900000000.0,
                     u'fluidinfo.com/info/url': u'http://example2.com',
                     u'fluidinfo.com/info/username': u'user'}]
        self.assertEqual(
            expected,
            self.comments.getForUser(
                u'user', newerThan=datetime.utcfromtimestamp(800000000)))

    def testGetForUserWithfilterAbout(self):
        """
        L{CommentAPI.getForUser} only returns comments made on a given object
        when the C{filterAbout} parameter is specified.
        """
        self.comments.create(u'comment 1', u'user',
                             about=[u'about1', u'+filter'],
                             url=u'http://example.com/1',
                             when=datetime.utcfromtimestamp(900000000))
        self.comments.create(u'comment 2', u'user',
                             about=[u'about2', u'+filter'],
                             url=u'http://example.com/2',
                             when=datetime.utcfromtimestamp(800000000))
        self.comments.create(u'comment 2', u'user',
                             about=[u'about2'],
                             url=u'http://example.com/3',
                             when=datetime.utcfromtimestamp(700000000))

        self.assertEqual(
            [{u'fluidinfo.com/info/about': [u'about1', u'+filter'],
              u'fluidinfo.com/info/text': u'comment 1',
              u'fluidinfo.com/info/timestamp': 900000000.0,
              u'fluidinfo.com/info/url': u'http://example.com/1',
              u'fluidinfo.com/info/username': u'user'},
             {u'fluidinfo.com/info/about': [u'about2', u'+filter'],
              u'fluidinfo.com/info/text': u'comment 2',
              u'fluidinfo.com/info/timestamp': 800000000.0,
              u'fluidinfo.com/info/url': u'http://example.com/2',
              u'fluidinfo.com/info/username': u'user'}],
            self.comments.getForUser(u'user', filterAbout=u'+filter'))

    def testGetForUserWithNoComments(self):
        """
        L{CommentAPI.getByUser} returns an empty list if there are no
        comments made by the given user.
        """
        self.assertEqual([], self.comments.getForUser(u'unknown'))

    def testGetForUserWithAdditionalTagsEmptyList(self):
        """
        L{CommentAPI.getForUser} with an empty C{additionalTags} list returns
        only the default comment tags.
        """
        self.comments.create(u'comment 1', u'username', about=[u'target'],
                             url=u'http://example.com/1',
                             when=datetime.utcfromtimestamp(900000000))
        self.assertEqual([{u'fluidinfo.com/info/about': [u'target'],
                           u'fluidinfo.com/info/text': u'comment 1',
                           u'fluidinfo.com/info/timestamp': 900000000.0,
                           u'fluidinfo.com/info/url': u'http://example.com/1',
                           u'fluidinfo.com/info/username': u'username'}],
                         self.comments.getForUser(u'username',
                                                  additionalTags=[]))

    def testGetForUserWithAdditionalTags(self):
        """
        L{CommentAPI.getForUser} with C{additionalTags} list returns
        additional tags plus default ones.
        """
        when = datetime.utcfromtimestamp(900000000)
        self.comments.create(u'comment', u'username', about=[u'banana'],
                             url=u'http://example.com/1',
                             when=when)

        # Get the comment ID based on the expected about value
        commentAbout = u'fluidinfo.com username %s' % when.isoformat()
        commentID = ObjectAPI(self.user).create(commentAbout)
        TagValueAPI(self.user).set({commentID: {u'minion/lunch': u'paple',
                                                u'minion/dinner': u'banana'}})

        additionalTags = [u'minion/lunch',
                          u'minion/dinner']
        expected = [{u'fluidinfo.com/info/about': [u'banana'],
                     u'fluidinfo.com/info/text': u'comment',
                     u'fluidinfo.com/info/timestamp': 900000000.0,
                     u'fluidinfo.com/info/url': u'http://example.com/1',
                     u'fluidinfo.com/info/username': u'username',
                     u'minion/lunch': u'paple',
                     u'minion/dinner': u'banana'}]
        self.assertEqual(
            expected,
            self.comments.getForUser(username=u'username',
                                     additionalTags=additionalTags))

    def testGetForUserWithAdditionalTagsOpaqueValue(self):
        """
        L{CommentAPI.getForUser} where C{additionalTags} contain an opaque
        value return the id, mime-type and size, but not the contents.
        """
        when = datetime.utcfromtimestamp(900000000)
        self.comments.create(u'comment', u'username1', about=[u'banana'],
                             url=u'http://example.com/1',
                             when=when)

        # Get the comment ID based on the expected about value
        commentAbout = u'fluidinfo.com username1 %s' % when.isoformat()
        commentID = ObjectAPI(self.user).create(commentAbout)
        doc = {'mime-type': u'image/gif',
               'contents': 'GIF87a\x01\x00\x01\x00\xf0\x00\x00\xff\xff\xff\x00'
               + '\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01'
               + '\x00;'}
        TagValueAPI(self.user).set({commentID: {u'username/file': doc}})

        expected = [{u'fluidinfo.com/info/about': [u'banana'],
                     u'fluidinfo.com/info/text': u'comment',
                     u'fluidinfo.com/info/timestamp': 900000000.0,
                     u'fluidinfo.com/info/url': u'http://example.com/1',
                     u'fluidinfo.com/info/username': u'username1',
                     u'username/file': {
                         u'id': str(commentID),
                         u'mime-type': u'image/gif',
                         u'size': 35
                     }}]
        self.assertEqual(
            expected,
            self.comments.getForUser(u'username1',
                                     additionalTags=[u'username/file']))

    def testGetForFollowedObjects(self):
        """
        L{CommentAPI.getForFollowedObjects} returns the comments made on all
        the objects a user follows.
        """
        objectID1 = ObjectAPI(self.user).create(u'object 1')
        objectID2 = ObjectAPI(self.user).create(u'object 2')
        TagValueAPI(self.user).set({
            objectID1: {u'username/follows': None},
            objectID2: {u'username/follows': None},
        })

        self.comments.create(u'comment 1', u'user1', about=[u'object 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(900000000))

        self.comments.create(u'comment 2', u'user2', about=[u'object 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(800000000))

        expected = [{u'fluidinfo.com/info/about': [u'object 1'],
                     u'fluidinfo.com/info/text': u'comment 1',
                     u'fluidinfo.com/info/timestamp': 900000000,
                     u'fluidinfo.com/info/url': u'http://example.com',
                     u'fluidinfo.com/info/username': u'user1'},
                    {u'fluidinfo.com/info/about': [u'object 2'],
                     u'fluidinfo.com/info/text': u'comment 2',
                     u'fluidinfo.com/info/timestamp': 800000000,
                     u'fluidinfo.com/info/url': u'http://example2.com',
                     u'fluidinfo.com/info/username': u'user2'}]
        self.assertEqual(expected,
                         self.comments.getForFollowedObjects(u'username'))

    def testGetForFollowedObjectsWithLimit(self):
        """
        L{CommentAPI.getForFollowedObjects} with a limit returns only the C{n}
        most recent comments.
        """
        objectID1 = ObjectAPI(self.user).create(u'object 1')
        objectID2 = ObjectAPI(self.user).create(u'object 2')
        TagValueAPI(self.user).set({
            objectID1: {u'username/follows': None},
            objectID2: {u'username/follows': None},
        })

        self.comments.create(u'comment 1', u'user1', about=[u'object 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(900000000))

        self.comments.create(u'comment 2', u'user2', about=[u'object 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(800000000))

        expected = [{u'fluidinfo.com/info/about': [u'object 1'],
                     u'fluidinfo.com/info/text': u'comment 1',
                     u'fluidinfo.com/info/timestamp': 900000000,
                     u'fluidinfo.com/info/url': u'http://example.com',
                     u'fluidinfo.com/info/username': u'user1'}]
        self.assertEqual(
            expected,
            self.comments.getForFollowedObjects(u'username', limit=1))

    def testGetForFollowedObjectsWithOlderThan(self):
        """
        L{CommentAPI.getForFollowedObjects} with an C{olderThan} returns
        comments older than the given argument.
        """
        objectID1 = ObjectAPI(self.user).create(u'object 1')
        objectID2 = ObjectAPI(self.user).create(u'object 2')
        TagValueAPI(self.user).set({
            objectID1: {u'username/follows': None},
            objectID2: {u'username/follows': None},
        })

        self.comments.create(u'comment 1', u'username', about=[u'object 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(800000000))

        self.comments.create(u'comment 2', u'username', about=[u'object 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(900000000))

        expected = [{u'fluidinfo.com/info/about': [u'object 1'],
                     u'fluidinfo.com/info/text': u'comment 1',
                     u'fluidinfo.com/info/timestamp': 800000000.0,
                     u'fluidinfo.com/info/url': u'http://example.com',
                     u'fluidinfo.com/info/username': u'username'}]
        self.assertEqual(
            expected,
            self.comments.getForFollowedObjects(
                u'username', olderThan=datetime.utcfromtimestamp(900000000)))

    def testGetForFollowedObjectsWithNewerThan(self):
        """
        L{CommentAPI.getForFollowedObjects} with a C{newerThan} argument
        returns comments newer than the given argument.
        """
        objectID1 = ObjectAPI(self.user).create(u'object 1')
        objectID2 = ObjectAPI(self.user).create(u'object 2')
        TagValueAPI(self.user).set({
            objectID1: {u'username/follows': None},
            objectID2: {u'username/follows': None},
        })

        self.comments.create(u'comment 1', u'username', about=[u'object 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(800000000))

        self.comments.create(u'comment 2', u'username', about=[u'object 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(900000000))

        expected = [{u'fluidinfo.com/info/about': [u'object 2'],
                     u'fluidinfo.com/info/text': u'comment 2',
                     u'fluidinfo.com/info/timestamp': 900000000.0,
                     u'fluidinfo.com/info/url': u'http://example2.com',
                     u'fluidinfo.com/info/username': u'username'}]
        self.assertEqual(
            expected,
            self.comments.getForFollowedObjects(
                u'username', newerThan=datetime.utcfromtimestamp(800000000)))

    def testGetForFollowedObjectsWithNoComments(self):
        """
        L{CommentAPI.getForFollowedObjects} returns an empty list if there are
        no comments made on a given object.
        """
        self.assertEqual([], self.comments.getForFollowedObjects(u'username'))

    def testGetForFollowedUsers(self):
        """
        L{CommentAPI.getForFollowedUsers} returns the comments made by the
        followed users.
        """
        UserAPI().create([(u'user1', u'secret', u'User', u'user@example.com')])
        user = getUser(u'user1')
        TagValueAPI(self.user).set({
            user.objectID: {u'username/follows': None},
            uuid4(): {u'username/follows': None},
        })

        self.comments.create(u'comment 1', u'user1', about=[u'object 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(900000000))

        self.comments.create(u'comment 2', u'user1', about=[u'object 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(800000000))

        expected = [{u'fluidinfo.com/info/about': [u'object 1'],
                     u'fluidinfo.com/info/text': u'comment 1',
                     u'fluidinfo.com/info/timestamp': 900000000,
                     u'fluidinfo.com/info/url': u'http://example.com',
                     u'fluidinfo.com/info/username': u'user1'},
                    {u'fluidinfo.com/info/about': [u'object 2'],
                     u'fluidinfo.com/info/text': u'comment 2',
                     u'fluidinfo.com/info/timestamp': 800000000,
                     u'fluidinfo.com/info/url': u'http://example2.com',
                     u'fluidinfo.com/info/username': u'user1'}]
        self.assertEqual(expected,
                         self.comments.getForFollowedUsers(u'username'))

    def testGetForFollowedUsersWithLimit(self):
        """
        L{CommentAPI.getForFollowedUsers} with a limit returns only the C{n}
        most recent comments.
        """
        UserAPI().create([(u'user1', u'secret', u'User', u'user@example.com')])
        user = getUser(u'user1')
        TagValueAPI(self.user).set({
            user.objectID: {u'username/follows': None},
            uuid4(): {u'username/follows': None},
        })

        self.comments.create(u'comment 1', u'user1', about=[u'object 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(900000000))

        self.comments.create(u'comment 2', u'user1', about=[u'object 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(800000000))

        expected = [{u'fluidinfo.com/info/about': [u'object 1'],
                     u'fluidinfo.com/info/text': u'comment 1',
                     u'fluidinfo.com/info/timestamp': 900000000.0,
                     u'fluidinfo.com/info/url': u'http://example.com',
                     u'fluidinfo.com/info/username': u'user1'}]
        self.assertEqual(
            expected,
            self.comments.getForFollowedUsers(u'username', limit=1))

    def testGetForFollowedUsersWithOlderThan(self):
        """
        L{CommentAPI.getForFollowedUsers} with an C{olderThan} returns comments
        older than the given argument.
        """
        UserAPI().create([(u'user1', u'secret', u'User', u'user@example.com')])
        user = getUser(u'user1')
        TagValueAPI(self.user).set({
            user.objectID: {u'username/follows': None},
            uuid4(): {u'username/follows': None},
        })

        self.comments.create(u'comment 1', u'user1', about=[u'object 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(800000000))

        self.comments.create(u'comment 2', u'user1', about=[u'object 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(900000000))

        expected = [{u'fluidinfo.com/info/about': [u'object 1'],
                     u'fluidinfo.com/info/text': u'comment 1',
                     u'fluidinfo.com/info/timestamp': 800000000.0,
                     u'fluidinfo.com/info/url': u'http://example.com',
                     u'fluidinfo.com/info/username': u'user1'}]
        self.assertEqual(
            expected,
            self.comments.getForFollowedUsers(
                u'username', olderThan=datetime.utcfromtimestamp(900000000)))

    def testGetForFollowedUsersWithNewerThan(self):
        """
        L{CommentAPI.getForFollowedUsers} with a C{newerThan} argument returns
        comments newer than the given argument.
        """
        UserAPI().create([(u'user1', u'secret', u'User', u'user@example.com')])
        user = getUser(u'user1')
        TagValueAPI(self.user).set({
            user.objectID: {u'username/follows': None},
            uuid4(): {u'username/follows': None},
        })

        self.comments.create(u'comment 1', u'user1', about=[u'object 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(800000000))

        self.comments.create(u'comment 2', u'user1', about=[u'object 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(900000000))

        expected = [{u'fluidinfo.com/info/about': [u'object 2'],
                     u'fluidinfo.com/info/text': u'comment 2',
                     u'fluidinfo.com/info/timestamp': 900000000.0,
                     u'fluidinfo.com/info/url': u'http://example2.com',
                     u'fluidinfo.com/info/username': u'user1'}]
        self.assertEqual(
            expected,
            self.comments.getForFollowedUsers(
                u'username', newerThan=datetime.utcfromtimestamp(800000000)))

    def testGetForFollowedUsersWithNoComments(self):
        """
        L{CommentAPI.getForFollowedUsers} returns an empty list if there are
        no comments made on a given object.
        """
        self.assertEqual([], self.comments.getForFollowedUsers(u'username'))

    def testGetAllFollowed(self):
        """
        L{CommentAPI.getAllFollowed} returns the comments on the followed
        objects, by the followed users and by the requested user.
        """
        objectID = ObjectAPI(self.user).create(u'object 1')
        UserAPI().create([(u'user1', u'secret', u'User', u'user@example.com')])
        user = getUser(u'user1')
        TagValueAPI(self.user).set({
            objectID: {u'username/follows': None},
            user.objectID: {u'username/follows': None},
        })

        self.comments.create(u'comment 1', u'username', about=[u'object 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(900000000))

        self.comments.create(u'comment 2', u'user1', about=[u'object 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(800000000))

        self.comments.create(u'comment 3', u'username', about=[u'object 3'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(700000000))

        expected = [{u'fluidinfo.com/info/about': [u'object 1'],
                     u'fluidinfo.com/info/text': u'comment 1',
                     u'fluidinfo.com/info/timestamp': 900000000,
                     u'fluidinfo.com/info/url': u'http://example.com',
                     u'fluidinfo.com/info/username': u'username'},
                    {u'fluidinfo.com/info/about': [u'object 2'],
                     u'fluidinfo.com/info/text': u'comment 2',
                     u'fluidinfo.com/info/timestamp': 800000000,
                     u'fluidinfo.com/info/url': u'http://example2.com',
                     u'fluidinfo.com/info/username': u'user1'},
                    {u'fluidinfo.com/info/about': [u'object 3'],
                     u'fluidinfo.com/info/text': u'comment 3',
                     u'fluidinfo.com/info/timestamp': 700000000,
                     u'fluidinfo.com/info/url': u'http://example.com',
                     u'fluidinfo.com/info/username': u'username'}]
        self.assertEqual(expected,
                         self.comments.getAllFollowed(u'username'))

    def testGetAllFollowedWithMultipleAbouts(self):
        """
        L{CommentAPI.getAllFollowed} returns unique comments even when a
        comment is associated with multiple about values. (See bug #1845.)
        """
        objectID = ObjectAPI(self.user).create(u'object 1')
        UserAPI().create([(u'user1', u'secret', u'User', u'user@example.com')])
        user = getUser(u'user1')
        TagValueAPI(self.user).set({
            objectID: {u'username/follows': None},
            user.objectID: {u'username/follows': None},
        })

        self.comments.create(u'#hashtag', u'user1', about=[u'object 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(900000000))

        expected = [{u'fluidinfo.com/info/about': [u'object 1', u'#hashtag'],
                     u'fluidinfo.com/info/text': u'#hashtag',
                     u'fluidinfo.com/info/timestamp': 900000000,
                     u'fluidinfo.com/info/url': u'http://example.com',
                     u'fluidinfo.com/info/username': u'user1'}]
        self.assertEqual(expected,
                         self.comments.getAllFollowed(u'username'))

    def testGetAllFollowedWithLimit(self):
        """
        L{CommentAPI.getAllFollowed} with a limit returns only the C{n} most
        recent comments.
        """
        objectID = ObjectAPI(self.user).create(u'object 1')
        UserAPI().create([(u'user1', u'secret', u'User', u'user@example.com')])
        user = getUser(u'user1')
        TagValueAPI(self.user).set({
            objectID: {u'username/follows': None},
            user.objectID: {u'username/follows': None},
        })

        self.comments.create(u'comment 1', u'username', about=[u'object 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(900000000))

        self.comments.create(u'comment 2', u'user1', about=[u'object 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(800000000))

        expected = [{u'fluidinfo.com/info/about': [u'object 1'],
                     u'fluidinfo.com/info/text': u'comment 1',
                     u'fluidinfo.com/info/timestamp': 900000000,
                     u'fluidinfo.com/info/url': u'http://example.com',
                     u'fluidinfo.com/info/username': u'username'}]
        self.assertEqual(expected,
                         self.comments.getAllFollowed(u'username', limit=1))

    def testGetAllFollowedWithOlderThan(self):
        """
        L{CommentAPI.getAllFollowed} with an C{olderThan} returns comments
        older than the given argument.
        """
        objectID = ObjectAPI(self.user).create(u'object 1')
        UserAPI().create([(u'user1', u'secret', u'User', u'user@example.com')])
        user = getUser(u'user1')
        TagValueAPI(self.user).set({
            objectID: {u'username/follows': None},
            user.objectID: {u'username/follows': None},
        })

        self.comments.create(u'comment 1', u'username', about=[u'object 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(900000000))

        self.comments.create(u'comment 2', u'user1', about=[u'object 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(800000000))

        expected = [{u'fluidinfo.com/info/about': [u'object 2'],
                     u'fluidinfo.com/info/text': u'comment 2',
                     u'fluidinfo.com/info/timestamp': 800000000,
                     u'fluidinfo.com/info/url': u'http://example2.com',
                     u'fluidinfo.com/info/username': u'user1'}]
        self.assertEqual(
            expected,
            self.comments.getAllFollowed(
                u'username',
                olderThan=datetime.utcfromtimestamp(900000000)))

    def testGetAllFollowedWithNewerThan(self):
        """
        L{CommentAPI.getAllFollowed} with a C{newerThan} argument returns
        comments newer than the given argument.
        """
        objectID = ObjectAPI(self.user).create(u'object 1')
        UserAPI().create([(u'user1', u'secret', u'User', u'user@example.com')])
        user = getUser(u'user1')
        TagValueAPI(self.user).set({
            objectID: {u'username/follows': None},
            user.objectID: {u'username/follows': None},
        })

        self.comments.create(u'comment 1', u'username', about=[u'object 1'],
                             url=u'http://example.com',
                             when=datetime.utcfromtimestamp(900000000))

        self.comments.create(u'comment 2', u'user1', about=[u'object 2'],
                             url=u'http://example2.com',
                             when=datetime.utcfromtimestamp(800000000))

        expected = [{u'fluidinfo.com/info/about': [u'object 1'],
                     u'fluidinfo.com/info/text': u'comment 1',
                     u'fluidinfo.com/info/timestamp': 900000000,
                     u'fluidinfo.com/info/url': u'http://example.com',
                     u'fluidinfo.com/info/username': u'username'}]
        self.assertEqual(
            expected,
            self.comments.getAllFollowed(
                u'username',
                newerThan=datetime.utcfromtimestamp(800000000)))

    def testGetAllFollowedWithNoComments(self):
        """
        L{CommentAPI.getAllFollowed} returns an empty list if there are
        no comments made on a given object.
        """
        self.assertEqual([], self.comments.getAllFollowed(u'username'))

    def testGetFollowedObjectsWithUnknownUser(self):
        """
        L{CommentAPI.getFollowedObjects} returns an empty result set when an
        unknown username is provided.
        """
        self.assertEqual([], self.comments.getFollowedObjects(u'unknown'))

    def testGetFollowedObjectsWithoutFollowedObjects(self):
        """
        L{CommentAPI.getFollowedObjects} returns an empty result set when the
        specified user isn't following any objects.
        """
        self.assertEqual([], self.comments.getFollowedObjects(u'username'))

    def testGetFollowedObjects(self):
        """
        L{CommentAPI.getFollowedObjects} returns the objects followed by the
        specified user.
        """
        objectID = ObjectAPI(self.user).create(u'about')
        TagValueAPI(self.user).set({objectID: {u'username/follows': None}})
        tag = getTags(paths=[u'username/follows']).one()
        value = getTagValues([(objectID, tag.id)]).one()
        value.creationTime = datetime.utcnow()
        timestamp = timegm(value.creationTime.utctimetuple()) + float(
            value.creationTime.strftime('0.%f'))
        [result] = self.comments.getFollowedObjects(u'username')
        self.assertEqual({u'about': u'about',
                          u'creationTime': timestamp,
                          u'following': True}, result)

    def testGetFollowedObjectsForDifferentUser(self):
        """
        L{CommentAPI.getFollowedObjects} returns the following state for the
        L{User} making the request when the objects requested are for a
        different user.
        """
        UserAPI().create([
            (u'friend', u'secret', u'Friend', u'friend@example.com')])
        user = getUser(u'friend')
        objectID1 = ObjectAPI(self.user).create(u'following')
        objectID2 = ObjectAPI(self.user).create(u'not-following')
        TagValueAPI(user).set({objectID1: {u'friend/follows': None},
                               objectID2: {u'friend/follows': None}})
        TagValueAPI(self.user).set({objectID1: {u'username/follows': None}})
        tag = getTags(paths=[u'friend/follows']).one()
        value1 = getTagValues([(objectID1, tag.id)]).one()
        value1.creationTime = datetime.utcnow()
        value2 = getTagValues([(objectID2, tag.id)]).one()
        value2.creationTime = datetime.utcnow()
        timestamp1 = timegm(value1.creationTime.utctimetuple()) + float(
            value1.creationTime.strftime('0.%f'))
        timestamp2 = timegm(value2.creationTime.utctimetuple()) + float(
            value2.creationTime.strftime('0.%f'))

        result = sorted(self.comments.getFollowedObjects(u'friend'),
                        key=lambda value: value['about'])
        self.assertEqual({u'about': u'following',
                          u'creationTime': timestamp1,
                          u'following': True},
                         result[0])
        self.assertEqual({u'about': u'not-following',
                          u'creationTime': timestamp2,
                          u'following': False},
                         result[1])

    def testGetFollowedObjectsWithLimit(self):
        """
        L{CommentAPI.getFollowedObjects} with a limit returns only the C{n}
        most recent comments.
        """
        UserAPI().create([
            (u'friend', u'secret', u'Friend', u'friend@example.com')])
        user = getUser(u'friend')
        objectID1 = ObjectAPI(self.user).create(u'following')
        objectID2 = ObjectAPI(self.user).create(u'not-following')
        TagValueAPI(user).set({objectID1: {u'friend/follows': None},
                               objectID2: {u'friend/follows': None}})
        TagValueAPI(self.user).set({objectID1: {u'username/follows': None}})

        self.assertEqual(
            1,
            len(self.comments.getFollowedObjects(u'friend', limit=1)))

    def testGetFollowedObjectsWithOlderThan(self):
        """
        L{CommentAPI.getFollowedObjects} with an C{olderThan} returns comments
        older than the given argument.
        """
        UserAPI().create([
            (u'friend', u'secret', u'Friend', u'friend@example.com')])
        user = getUser(u'friend')
        objectID1 = ObjectAPI(self.user).create(u'following')
        objectID2 = ObjectAPI(self.user).create(u'not-following')
        TagValueAPI(user).set({objectID1: {u'friend/follows': None},
                               objectID2: {u'friend/follows': None}})
        TagValueAPI(self.user).set({objectID1: {u'username/follows': None}})
        tag = getTags(paths=[u'friend/follows']).one()
        value = getTagValues([(objectID2, tag.id)]).one()
        value.creationTime = datetime.utcnow() - timedelta(hours=24)
        timestamp = timegm(value.creationTime.utctimetuple()) + float(
            value.creationTime.strftime('0.%f'))

        self.assertEqual(
            [{'about': u'not-following',
              u'creationTime': timestamp,
              u'following': False}],
            self.comments.getFollowedObjects(
                u'friend', olderThan=datetime.utcnow() - timedelta(hours=12)))

    def testGetFollowedObjectsWithURLObjectType(self):
        """
        L{CommentAPI.getFollowedObjects} with an URL as the C{objectType}
        returns the objects of that type followed by the specified user.
        """
        objectapi = ObjectAPI(self.user)
        objectID1 = objectapi.create(u'about')
        objectID2 = objectapi.create(u'http://google.com')
        TagValueAPI(self.user).set({objectID1: {u'username/follows': None},
                                    objectID2: {u'username/follows': None}})
        [result] = self.comments.getFollowedObjects(u'username',
                                                    objectType='url')
        self.assertEqual(u'http://google.com', result['about'])
        self.assertTrue(result['following'])

    def testGetFollowedObjectsWithUserObjectType(self):
        """
        L{CommentAPI.getFollowedObjects} with a user as the C{objectType}
        returns the objects of that type followed by the specified user.
        """
        objectapi = ObjectAPI(self.user)
        objectID1 = objectapi.create(u'about')
        objectID2 = objectapi.create(u'@paparent')
        TagValueAPI(self.user).set({objectID1: {u'username/follows': None},
                                    objectID2: {u'username/follows': None}})
        [result] = self.comments.getFollowedObjects(u'username',
                                                    objectType='user')
        self.assertEqual(u'@paparent', result['about'])
        self.assertTrue(result['following'])

    def testGetFollowedObjectsWithHashtagObjectType(self):
        """
        L{CommentAPI.getFollowedObjects} with an hashtag as the C{objectType}
        returns the objects of that type followed by the specified user.
        """
        objectapi = ObjectAPI(self.user)
        objectID1 = objectapi.create(u'about')
        objectID2 = objectapi.create(u'#like')
        TagValueAPI(self.user).set({objectID1: {u'username/follows': None},
                                    objectID2: {u'username/follows': None}})
        [result] = self.comments.getFollowedObjects(u'username',
                                                    objectType='hashtag')
        self.assertEqual(u'#like', result['about'])
        self.assertTrue(result['following'])

    def testGetFollowedObjectsWithUnkownObjectType(self):
        """
        L{CommentAPI.getFollowedObjects} with an unkown C{objectType} raises
        an C{FeatureError} exception.
        """
        self.assertRaises(FeatureError, self.comments.getFollowedObjects,
                          u'username', objectType='unknown')

    def testGetFollowedObjectsWithoutURLObjectType(self):
        """
        L{CommentAPI.getFollowedObjects} with a URL as the C{objectType}
        returns empty list if no URL.
        """
        objectapi = ObjectAPI(self.user)
        objectID1 = objectapi.create(u'@paparent')
        objectID2 = objectapi.create(u'#like')
        TagValueAPI(self.user).set({objectID1: {u'username/follows': None},
                                    objectID2: {u'username/follows': None}})
        self.assertEqual(
            0,
            len(self.comments.getFollowedObjects(u'username',
                                                 objectType='url')))

    def testGetFollowedObjectsWithoutUserObjectType(self):
        """
        L{CommentAPI.getFollowedObjects} with a user as the C{objectType}
        returns empty list if no user.
        """
        objectapi = ObjectAPI(self.user)
        objectID1 = objectapi.create(u'http://google.com')
        objectID2 = objectapi.create(u'#like')
        TagValueAPI(self.user).set({objectID1: {u'username/follows': None},
                                    objectID2: {u'username/follows': None}})
        self.assertEqual(
            0,
            len(self.comments.getFollowedObjects(u'username',
                                                 objectType='user')))

    def testGetFollowedObjectsWithoutHashtagObjectType(self):
        """
        L{CommentAPI.getFollowedObjects} with a hashtag as the C{objectType}
        returns empty list if no hashtag.
        """
        objectapi = ObjectAPI(self.user)
        objectID1 = objectapi.create(u'@paparent')
        objectID2 = objectapi.create(u'http://google.com')
        TagValueAPI(self.user).set({objectID1: {u'username/follows': None},
                                    objectID2: {u'username/follows': None}})
        self.assertEqual(
            0,
            len(self.comments.getFollowedObjects(u'username',
                                                 objectType='hashtag')))

    def testUpdateExistingComment(self):
        """L{CommentAPI.update} updates the text of an existing comment."""
        when = datetime.utcnow()
        isoTime = when.isoformat()
        floatTime = timegm(when.utctimetuple()) + float(when.strftime('0.%f'))
        objectAPI = ObjectAPI(self.user)
        commentID = objectAPI.create(u'digg.com username %s' % isoTime)
        self.comments.create(
            u'comment', u'username', when=when, about=[u'chickens'],
            importer=u'digg.com', url=u'http://domain.com/post123')

        result = self.comments.update(u'digg.com', u'username', when,
                                      u'new text')

        values = TagValueAPI(self.user).get([commentID],
                                            [u'fluidinfo.com/info/text'])
        commentText = values[commentID][u'fluidinfo.com/info/text'].value

        self.assertEqual('new text', commentText)

        expected = {
            u'fluidinfo.com/info/url': u'http://domain.com/post123',
            u'fluidinfo.com/info/text': u'new text',
            u'fluidinfo.com/info/username': u'username',
            u'fluidinfo.com/info/about': [u'chickens'],
            u'fluidinfo.com/info/timestamp': floatTime
        }
        self.assertEqual(expected, result)

    def testUpdateRemovesAssociationsExtractedFromOldText(self):
        """
        L{CommentAPI.update} removes associations extracted from the old
        comment's text.
        """
        when = datetime.utcnow()
        isoTime = when.isoformat()
        floatTime = timegm(when.utctimetuple()) + float(when.strftime('0.%f'))
        objectAPI = ObjectAPI(self.user)
        commentID = objectAPI.create(u'digg.com username %s' % isoTime)
        self.comments.create(
            u'@atname #hashtag', u'username', when=when, about=[u'chickens'],
            importer=u'digg.com', url=u'http://domain.com/post123')

        result = self.comments.update(u'digg.com', u'username', when,
                                      u'new text')

        values = TagValueAPI(self.user).get([commentID],
                                            [u'fluidinfo.com/info/text'])
        commentText = values[commentID][u'fluidinfo.com/info/text'].value

        self.assertEqual('new text', commentText)

        expected = {
            u'fluidinfo.com/info/url': u'http://domain.com/post123',
            u'fluidinfo.com/info/text': 'new text',
            u'fluidinfo.com/info/username': u'username',
            u'fluidinfo.com/info/about': [u'chickens'],
            u'fluidinfo.com/info/timestamp': floatTime
        }
        self.assertEqual(expected, result)
        self.assertEqual([], self.comments.getForObject(u'#hashtag'))
        self.assertEqual([], self.comments.getForObject(u'@atname'))

    def testUpdateAddsAssociationsExtractedFromNewText(self):
        """
        L{CommentAPI.update} adds associations extracted from the new comment's
        text.
        """
        when = datetime.utcnow()
        isoTime = when.isoformat()
        floatTime = timegm(when.utctimetuple()) + float(when.strftime('0.%f'))
        objectAPI = ObjectAPI(self.user)
        commentID = objectAPI.create(u'digg.com username %s' % isoTime)
        self.comments.create(
            u'@atname #hashtag', u'username', when=when, about=[u'chickens'],
            importer=u'digg.com', url=u'http://domain.com/post123')

        result = self.comments.update(u'digg.com', u'username', when,
                                      u'#other @name')

        values = TagValueAPI(self.user).get([commentID],
                                            [u'fluidinfo.com/info/text'])
        commentText = values[commentID][u'fluidinfo.com/info/text'].value

        self.assertEqual(u'#other @name', commentText)

        expected = {
            u'fluidinfo.com/info/url': u'http://domain.com/post123',
            u'fluidinfo.com/info/text': u'#other @name',
            u'fluidinfo.com/info/username': u'username',
            u'fluidinfo.com/info/about': [u'chickens', u'#other', u'@name'],
            u'fluidinfo.com/info/timestamp': floatTime
        }
        self.assertEqual(expected, result)
        self.assertEqual([], self.comments.getForObject(u'#hashtag'))
        self.assertEqual([], self.comments.getForObject(u'@atname'))
        self.assertEqual(1, len(self.comments.getForObject(u'#other')))
        self.assertEqual(1, len(self.comments.getForObject(u'@name')))

    def testUpdateNonExistentComment(self):
        """
        L{CommentAPI.update} raises C{RuntimeError} if the comment object does
        not exist.
        """
        self.assertRaises(RuntimeError,
                          self.comments.update,
                          u'digg.com', u'username', datetime.utcnow(), u'new')

    def testUpdateWithEmptyText(self):
        """
        L{CommentAPI.update} raises L{FeatureError} if the new text provied is
        empty.
        """
        when = datetime.utcnow()
        self.comments.create(
            u'comment', u'username', when=when, about=[u'chickens'],
            importer=u'digg.com', url=u'http://domain.com/post123')

        self.assertRaises(FeatureError,
                          self.comments.update,
                          u'digg.com', u'username', when, u'')

    def testDeleteExistingComment(self):
        """
        When a comment is deleted, its tag values must be removed from FluidDB.
        """
        when = datetime.utcnow()
        isoTime = when.isoformat()
        objectAPI = ObjectAPI(self.user)
        objectID = objectAPI.create(u'digg.com username %s' % isoTime)
        self.comments.create(
            u'comment', u'username', when=when, about=[u'chickens'],
            importer=u'digg.com', url=u'http://domain.com/post123')

        self.assertEqual(1,
                         self.comments.delete(u'digg.com', u'username', when))
        # Test the comment tag values are no longer present in FluidDB.
        # Only the fluiddb/about tag should remain on the comment object.
        tagValueAPI = TagValueAPI(self.user)
        self.assertEqual([u'fluiddb/about'],
                         tagValueAPI.get([objectID])[objectID].keys())
        # And make sure the comment API doesn't find any comments.
        self.assertEqual([], self.comments.getForObject(u'chickens'))

    def testDeleteCommentDoesNotDeleteAllTagValues(self):
        """
        When a comment is deleted, other tag values in FluidDB must not be
        deleted.
        """
        when = datetime.utcnow()
        self.comments.create(
            u'comment', u'username', when=when, about=[u'chickens'],
            importer=u'digg.com', url=u'http://domain.com/post123')
        # Add an unrelated (non-comment) tag value.
        objectID = ObjectAPI(self.user).create(u'#hashtag')
        TagValueAPI(self.user).set({objectID: {u'username/rating': 12345}})
        # Delete the comment.
        self.comments.delete(u'digg.com', u'username', when)
        # Check the unrelated tag still exists.
        tag = getTags(paths=[u'username/rating']).one()
        value = getTagValues([(objectID, tag.id)]).one()
        self.assertEqual(12345, value.value)

    def testDeleteNonexistentComment(self):
        """
        When an attempt is made to delete a non-existent comment,
        L{CommentAPI.delete} must return C{0}.
        """
        when = datetime.utcnow()
        self.assertEqual(0,
                         self.comments.delete(u'digg.com', u'username', when))


class CommentAPITest(CommentAPITestMixin, FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(CommentAPITest, self).setUp()
        createSystemData()
        UserAPI().create([
            (u'username', u'password', u'User', u'user@example.com'),
            (u'fluidinfo.com', u'secret', u'Fluidinfo', u'info@example.com')])
        self.user = getUser(u'username')
        self.comments = CommentAPI(self.user)


class ParseCommentURLTest(FluidinfoTestCase):

    def testParseCommentURL(self):
        """
        L{parseCommentURL} extracts the importer, username and timestamp from
        a comment URL.
        """
        url = ('https://loveme.do/comment/'
               'fluidinfo.com/username/2012-08-03T22:04:13.698896')
        importer, username, timestamp = parseCommentURL(url)
        self.assertEqual('fluidinfo.com', importer)
        self.assertEqual('username', username)
        self.assertEqual(datetime(2012, 8, 3, 22, 4, 13, 698896), timestamp)

    def testParseCommentURLWithoutMicroseconds(self):
        """
        L{parseCommentURL} correctly parses the ISO timestamp when it doesn't
        contain microseconds.
        """
        url = ('https://loveme.do/comment/'
               'fluidinfo.com/username/2012-08-03T22:04:13')
        importer, username, timestamp = parseCommentURL(url)
        self.assertEqual('fluidinfo.com', importer)
        self.assertEqual('username', username)
        self.assertEqual(datetime(2012, 8, 3, 22, 4, 13), timestamp)

    def testParseCommentURLWithIncorrectRootPath(self):
        """
        L{parseCommentURL} raises a C{ValueError} if the root path of the URL
        is not C{comment}.
        """
        url = ('https://loveme.do/remark/'
               'fluidinfo.com/username/2012-08-03T22:04:13')
        self.assertRaises(ValueError, parseCommentURL, url)

    def testParseCommentURLWithIncorrectISOTimestamp(self):
        """
        L{parseCommentURL} raises a C{ValueError} if the ISO timestamp in the
        URL cannot be parsed.
        """
        url = ('https://loveme.do/comment/'
               'fluidinfo.com/username/2012-08-03T22:04')
        self.assertRaises(ValueError, parseCommentURL, url)
