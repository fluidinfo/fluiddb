from calendar import timegm
from datetime import datetime
from re import compile, findall, UNICODE

from storm.locals import Desc, Like, Min, Or
from storm.expr import SQL

from fluiddb.application import getConfig
from fluiddb.data.comment import (
    Comment, CommentObjectLink, createComment, deleteComment)
from fluiddb.data.path import getParentPath
from fluiddb.data.store import getMainStore
from fluiddb.data.tag import Tag
from fluiddb.data.user import User
from fluiddb.data.value import (
    AboutTagValue, TagValue, getAboutTagValues, getObjectIDs)
from fluiddb.exceptions import FeatureError
from fluiddb.model.factory import APIFactory
from fluiddb.model.user import getUser
from fluiddb.util.unique import uniqueList

ATNAME_REGEX = compile(r'(?:^|[\s\(])(@\w+)', UNICODE)
HASHTAG_REGEX = compile(r'(?:^|[\s\(])(#[\w\-]+)', UNICODE)
PLUSTAG_REGEX = compile(r'(?:^|[\s\(])(\+[\w\-]+)', UNICODE)
URL_REGEX = compile(r'(?:^|\s)(https?://\S+)', UNICODE)
FILE_REGEX = compile(r'(?:^|\s)(file:(?:\w*:)?[a-f\d]{64})', UNICODE)


class CommentAPI(object):
    """The public API for comments in the model layer.

    @param user: The L{User} to perform operations on behalf of.
    @param factory: Optionally, the API factory to use when creating internal
        APIs.  Default is L{APIFactory}.
    """
    COMMENT_TAGS = [u'fluidinfo.com/info/about',
                    u'fluidinfo.com/info/text',
                    u'fluidinfo.com/info/timestamp',
                    u'fluidinfo.com/info/url',
                    u'fluidinfo.com/info/username']

    def __init__(self, user, factory=None):
        factory = factory or APIFactory()
        fluidinfoUser = getUser(u'fluidinfo.com')
        self._user = user

        self._objects = factory.objects(fluidinfoUser)
        self._tagValues = factory.tagValues(fluidinfoUser)

    def create(self, text, username, about=None, importer=None, when=None,
               url=None):
        """Create a new comment.

        @param text: The C{unicode} comment text.
        @param username: the C{unicode} username of the commenter.
        @param about: Optionally, a C{list} of C{unicode} values the comment is
            about.
        @param importer: A C{unicode} string giving the name of the importer.
        @param when: A C{datetime.datetime} instance or C{None} if the
            current time should be used.
        @param url: A C{str} URL or C{None} if there is no URL associated with
            this comment.
        @raise L{FeatureError}: if (1) the comment text is C{None} or is all
            whitespace, or (2) if the importer name contains the separator
            (space) that we use in the about value for comment objects.
        @return: A C{dict} as follows:
            {
                fluidinfo.com/info/about: A C{list} of all the about values
                    (i.e., URLs and hashtags) in the comment text, including
                    the thing the comment was about (if anything). The hashtags
                    are in lowercase.
                fluidinfo.com/info/timestamp: The C{int} UTC timestamp (seconds
                    since the epoch) the comment was created at.
                fluidinfo.com/info/url: The C{url}, as received.
                fluidinfo.com/info/username: The C{username}, as received.
            }
        """
        if not text or text.strip() == '':
            raise FeatureError('Comment text non-existent or just whitespace.')

        if importer:
            if ' ' in importer:
                raise FeatureError('Comment importer name contains a space.')
        else:
            importer = u'fluidinfo.com'

        when = when or datetime.utcnow()
        floatTime = timegm(when.utctimetuple()) + float(when.strftime('0.%f'))
        isoTime = when.isoformat()

        if not url:
            url = 'https://fluidinfo.com/comment/%s/%s/%s' % (
                importer, username, isoTime)

        # Put all the explicit about values into a list called abouts. Items
        # are stripped and those that are not URLs are lowercased.
        abouts = []
        if about:
            for item in map(unicode.strip, about):
                abouts.append(item if URL_REGEX.match(item) else item.lower())
        abouts.extend(self._extractAbouts(text))
        abouts = uniqueList(abouts)

        commentObjectAbout = u'%s %s %s' % (importer, username, isoTime)
        commentID = self._objects.create(commentObjectAbout)

        values = {u'fluidinfo.com/info/about': abouts,
                  u'fluidinfo.com/info/username': username,
                  u'fluidinfo.com/info/text': text,
                  u'fluidinfo.com/info/url': url,
                  u'fluidinfo.com/info/timestamp': floatTime}
        self._tagValues.set({commentID: values})

        if abouts:
            # Get all the object IDs of the target objects. If an object does
            # not exist, create it.
            result = getAboutTagValues(values=abouts)
            existingObjects = dict(result.values(AboutTagValue.value,
                                                 AboutTagValue.objectID))
            missingAbouts = set(abouts) - set(existingObjects.iterkeys())
            for aboutValue in missingAbouts:
                existingObjects[aboutValue] = self._objects.create(aboutValue)
            createComment(commentID, existingObjects.values(), username, when)
        return values

    def delete(self, importer, username, when):
        """Delete a comment.

        @param importer: A C{unicode} string giving the name of the importer.
        @param username: The C{unicode} username of the commenter.
        @param when: A C{datetime.datetime} instance.
        @return: An C{int} count of the number of comments removed.
        """
        isoTime = when.isoformat()
        commentObjectAbout = u'%s %s %s' % (importer, username, isoTime)
        aboutValue = getAboutTagValues(values=[commentObjectAbout]).one()
        if aboutValue is None:
            return 0
        objectID = aboutValue.objectID
        self._tagValues.delete((objectID, path) for path in self.COMMENT_TAGS)
        return deleteComment(objectID)

    def update(self, importer, username, when, newText):
        """Updates the text of a comment.

        All object associations previously extracted from the old comment's
        text are removed and new associations extracted from the new text are
        added. Object associations not extracted from the text are kept.

        @param importer: A C{unicode} string giving the name of the importer.
        @param username: The C{unicode} username of the commenter.
        @param when: A C{datetime.datetime} instance.
        @param text: The new text for the comment.
        @return: A C{dict} as follows:
            {
                fluidinfo.com/info/about: A C{list} of all the about values
                    (i.e., URLs and hashtags) in the comment text, including
                    the thing the comment was about (if anything). The hashtags
                    are in lowercase.
                fluidinfo.com/info/timestamp: The C{int} UTC timestamp (seconds
                    since the epoch) the comment was created at.
                fluidinfo.com/info/url: The C{url}, as received.
                fluidinfo.com/info/username: The C{username}, as received.
            }
        """
        # 1. Get the object ID of the comment object.
        isoTime = when.isoformat()
        commentObjectAbout = u'%s %s %s' % (importer, username, isoTime)
        aboutValue = getAboutTagValues(values=[commentObjectAbout]).one()
        if aboutValue is None:
            raise RuntimeError('Comment does not exist.')
        commentID = aboutValue.objectID

        # 2. Get the old text and url of the comment.
        result = self._tagValues.get([commentID], [u'fluidinfo.com/info/text',
                                                   u'fluidinfo.com/info/url'])
        oldText = result[commentID][u'fluidinfo.com/info/text'].value
        url = result[commentID][u'fluidinfo.com/info/url'].value

        # 3. Get abouts in comment's text.
        aboutsInText = self._extractAbouts(oldText)

        # 4. Get all the about values associated with the comment.
        store = getMainStore()
        allAbouts = store.find(
            AboutTagValue.value,
            CommentObjectLink.commentID == commentID,
            AboutTagValue.objectID == CommentObjectLink.objectID)

        # 5. Get abouts not in comment's text:
        aboutsNotInText = set(allAbouts) - set(aboutsInText)

        self.delete(importer, username, when)
        return self.create(newText, username, aboutsNotInText, importer, when,
                           url)

    def _extractAbouts(self, text):
        abouts = []
        config = getConfig()

        # The following 4 extractions are done in a non-alphabetical order
        # because (historically at least, for loveme.do) we want to have a
        # URL as the first about value in the about list, if any URLs are
        # present.  If you change the order here, you'll probably need to
        # change tests in tests/test_comment.py too.

        if config.getboolean('comments', 'extract-urls'):
            # Add any URLs in the text to the abouts list.
            abouts.extend(extractURLs(text))

        if config.getboolean('comments', 'extract-files'):
            # Add (in lower case) any files in the text to the abouts list.
            files = map(unicode.lower, extractFiles(text))
            if files:
                abouts.extend(files)
                abouts.append(config.get('comments',
                                         'file-object').decode('utf-8'))

        if config.getboolean('comments', 'extract-hashtags'):
            # Add (in lowercase) any hashtags in the text.
            abouts.extend(map(unicode.lower, extractHashtags(text)))

        if config.getboolean('comments', 'extract-plustags'):
            # Add (in lowercase) any +plustags in the text.
            abouts.extend(map(unicode.lower, extractPlustags(text)))

        if config.getboolean('comments', 'extract-atnames'):
            # Add (in lowercase) any @names in the text.
            abouts.extend(map(unicode.lower, extractAtnames(text)))

        return abouts

    def _findComments(self, where, limit, olderThan, newerThan, username=None,
                      followedByUsername=None, filterTags=None,
                      filterAbout=None, additionalTags=None):
        """Find comments in the database and format the result.

        @param where: The conditions for querying the comments table.
        @param limit: The maximum number of comments to return.
        @param olderThan: A C{datetime} indicating to return only
            comments older than it.
        @param newerThan: A C{datetime} indicating to return only
            comments newer than it.
        @param username: Optionally, only return comments made by the
            specified L{User.username}.
        @param followedByUsername: Optionally, only return comments made by
            L{User}s that the specified L{User.username} follows.
        @param filterTags: Optionally a C{list} of tag paths. If not C{None},
            return only comment objects with _all_ of the specified tag paths.
        @param filterAbout: Optionally, return only comments made on a
            given object.
        @param additionalTags: Optionally, a list of paths of additional tags
            to retrieve.
        @return: A C{list} of comments represented by a C{dict} with the
            following format::

            {
                'fluidinfo.com/info/about': <about-value-list>,
                'fluidinfo.com/info/text': <comment-text>,
                'fluidinfo.com/info/timestamp': <float-timestamp>,
                'fluidinfo.com/info/url': <url>,
                'fluidinfo.com/info/username': <username>,
            }
        """
        store = getMainStore()
        if olderThan is not None:
            where.append(Comment.creationTime < olderThan)
        if newerThan is not None:
            where.append(Comment.creationTime > newerThan)
        if username is not None:
            where.append(Comment.username == username)
        if followedByUsername:
            result = store.find(User.username,
                                User.objectID == TagValue.objectID,
                                Tag.id == TagValue.tagID,
                                Tag.path == followedByUsername + u'/follows')
            subselect = result.get_select_expr(User.username)
            where.append(Comment.username.is_in(subselect))
        if filterTags is not None:
            # Partial SQL, because Storm doesn't do "= ALL()"
            where.append(SQL("""
                comments.object_id IN (
                    SELECT tag_values.object_id
                    FROM tag_values, tags
                    WHERE
                        tags.id = tag_values.tag_id
                        AND tags.path = ANY(?)
                    GROUP BY tag_values.object_id
                    HAVING COUNT(*) = ?
                )
            """, [filterTags, len(filterTags)]))
        if filterAbout is not None:
            result = store.find(
                CommentObjectLink.commentID,
                CommentObjectLink.objectID == AboutTagValue.objectID,
                AboutTagValue.value == filterAbout)
            subselect = result.get_select_expr(CommentObjectLink.commentID)
            where.append(Comment.objectID.is_in(subselect))

        result = store.find(Comment.objectID, *where)

        # Use GROUP BY and MIN here to return unique object IDs. It's not
        # possible to use DISTINCT because postgres expects an ORDER BY
        # expression to be in the select list. -- ceronman
        result = result.group_by(Comment.objectID)
        result = result.order_by(Desc(Min(Comment.creationTime)))
        result = result.config(limit=limit)
        commentIDs = list(result)

        if not commentIDs:
            return []

        paths = self.COMMENT_TAGS + (additionalTags or [])
        tagValues = self._tagValues.get(objectIDs=commentIDs, paths=paths)
        result = []
        for commentID in commentIDs:
            valuesByTag = {}
            for path in paths:
                if path in tagValues[commentID]:
                    value = tagValues[commentID][path].value
                    if isinstance(value, dict):
                        del value['contents']
                        value['id'] = str(commentID)
                    valuesByTag[path] = value
            result.append(valuesByTag)
        return result

    def getForObject(self, about, limit=20, olderThan=None, newerThan=None,
                     username=None, followedByUsername=None, filterTags=None,
                     filterAbout=None, additionalTags=None):
        """Get the comments made for a particular object.

        @param about: The about value of the object to get the comments from.
        @param limit: Optionally, The maximum number of comments to return.
        @param olderThan: Optionally a C{datetime} indicating to return only
            comments older than it.
        @param newerThan: A C{datetime} indicating to return only
            comments newer than it.
        @param username: Optionally, only return comments made by the
            specified L{User.username}.
        @param followedByUsername: Optionally, only return comments made by
            L{User}s that the specified L{User.username} follows.
        @param filterTags: Optionally a C{list} of tag paths. If not C{None},
            return only comment objects with _all_ of the specified tag paths.
        @param filterAbout: Optionally, return only comments made on a
            given object.
        @param additionalTags: Optionally, a list of paths of additional tags
            to retrieve.
        @return: A C{list} of comments represented by a C{dict} with the
            following format::

            {
                'fluidinfo.com/info/about': <about-value-list>,
                'fluidinfo.com/info/text': <comment-text>,
                'fluidinfo.com/info/timestamp': <float-timestamp>,
                'fluidinfo.com/info/url': <url>,
                'fluidinfo.com/info/username': <username>,
            }
        """
        where = [Comment.objectID == CommentObjectLink.commentID,
                 CommentObjectLink.objectID == AboutTagValue.objectID,
                 AboutTagValue.value == about]
        return self._findComments(
            where, limit, olderThan, newerThan, username=username,
            followedByUsername=followedByUsername, filterTags=filterTags,
            filterAbout=filterAbout, additionalTags=additionalTags)

    def summarizeObject(self, about):
        """Get summary information for an object.

        @param about: The about value of the object to summarize.
        @return: A C{dict} matching the following format::

              {'commentCount':   <count>,
               'followers':      [<username>, ...],
               'relatedObjects': {'<about>': <count>, ...}}
        """
        # List followers.
        result = self._objects.get([about])
        objectID = result.get(about)

        if objectID is None:
            return {'commentCount': 0,
                    'followers': [],
                    'relatedObjects': {}}

        paths = self._objects.getTagsForObjects([objectID])
        followers = []
        for path in paths:
            parent = getParentPath(path)
            if parent and not u'/' in parent and path.endswith('/follows'):
                followers.append(parent)

        # Count comments.
        store = getMainStore()
        result = store.find(CommentObjectLink.commentID,
                            CommentObjectLink.objectID == objectID)
        commentCount = result.count()

        # Count related objects. I'm using raw SQL here because don't know how
        # to translate this query to Storm.
        result = store.execute("""
            SELECT about_tag_values."value", summary.count
            FROM (
                  SELECT comment_object_link.object_id AS object_id,
                         COUNT(comment_object_link.comment_id) AS count
                  FROM comment_object_link
                  WHERE comment_object_link.comment_id IN (
                      SELECT comment_object_link.comment_id
                      FROM comment_object_link
                      WHERE comment_object_link.object_id = '{objectID}')
                    AND comment_object_link.object_id != '{objectID}'
                  GROUP BY comment_object_link.object_id
                ) AS summary JOIN about_tag_values
                 ON summary.object_id = about_tag_values.object_id;
        """.format(objectID=objectID))

        relatedObjects = dict(result)

        return {'commentCount': commentCount,
                'followers': followers,
                'relatedObjects': relatedObjects}

    def getRecent(self, limit=20, olderThan=None, newerThan=None,
                  filterTags=None, additionalTags=None):
        """Get the recent comments.

        @param limit: Optionally, The maximum number of comments to return.
        @param olderThan: Optionally a C{datetime} indicating to return only
            comments older than it.
        @param newerThan: A C{datetime} indicating to return only
            comments newer than it.
        @param additionalTags: Optionally, a list of paths of additional tags
            to retrieve.
        @return: A C{list} of comments represented by a C{dict} with the
            following format::

            {
                'fluidinfo.com/info/about': <about-value-list>,
                'fluidinfo.com/info/text': <comment-text>,
                'fluidinfo.com/info/timestamp': <float-timestamp>,
                'fluidinfo.com/info/url': <url>,
                'fluidinfo.com/info/username': <username>,
            }
        """
        return self._findComments([], limit, olderThan, newerThan,
                                  filterTags=filterTags,
                                  additionalTags=additionalTags)

    def getByUser(self, username, limit=20, olderThan=None, newerThan=None):
        """Get the comments made by a particular user.

        @param username: The user to get the comments for.
        @param limit: Optionally, The maximum number of comments to return.
        @param olderThan: Optionally a C{datetime} indicating to return only
            comments older than it.
        @param newerThan: A C{datetime} indicating to return only
            comments newer than it.
        @return: A C{list} of comments represented by a C{dict} with the
            following format::

            {
                'fluidinfo.com/info/about': <about-value-list>,
                'fluidinfo.com/info/text': <comment-text>,
                'fluidinfo.com/info/timestamp': <float-timestamp>,
                'fluidinfo.com/info/url': <url>,
                'fluidinfo.com/info/username': <username>,
            }
        """
        where = [Comment.username == username]
        return self._findComments(where, limit, olderThan, newerThan)

    def getForUser(self, username, limit=20, olderThan=None, newerThan=None,
                   filterTags=None, filterAbout=None, additionalTags=None):
        """Get the comments made by a particular user or on the user object.

        @param username: The user to get the comments for.
        @param limit: Optionally, The maximum number of comments to return.
        @param olderThan: Optionally a C{datetime} indicating to return only
            comments older than it.
        @param filterTags: Optionally a C{list} of tag paths. If not C{None},
            return only comment objects with _all_ of the specified tag paths.
        @param filterAbout: Optionally, return only comments made on a
            given object.
        @param additionalTags: Optionally, a list of paths of additional tags
            to retrieve.
        @return: A C{list} of comments represented by a C{dict} with the
            following format::

            {
                'fluidinfo.com/info/about': <about-value-list>,
                'fluidinfo.com/info/text': <comment-text>,
                'fluidinfo.com/info/timestamp': <float-timestamp>,
                'fluidinfo.com/info/url': <url>,
                'fluidinfo.com/info/username': <username>,
            }
        """
        store = getMainStore()
        result = store.find(
            CommentObjectLink.commentID,
            CommentObjectLink.objectID == AboutTagValue.objectID,
            AboutTagValue.value == u'@' + username)
        subselect = result.get_select_expr(CommentObjectLink.commentID)

        where = [Or(Comment.username == username,
                    Comment.objectID.is_in(subselect))]
        return self._findComments(where, limit, olderThan, newerThan,
                                  filterTags=filterTags,
                                  filterAbout=filterAbout,
                                  additionalTags=additionalTags)

    def getForFollowedObjects(self, username, limit=20, olderThan=None,
                              newerThan=None):
        """Get the comments made on all the objects followed by the given user.

        @param username: The user to get the comments for.
        @param limit: Optionally, The maximum number of comments to return.
        @param olderThan: Optionally a C{datetime} indicating to return only
            comments older than it.
        @param newerThan: A C{datetime} indicating to return only
            comments newer than it.
        @return: A C{list} of comments represented by a C{dict} with the
            following format::

            {
                'fluidinfo.com/info/about': <about-value-list>,
                'fluidinfo.com/info/text': <comment-text>,
                'fluidinfo.com/info/timestamp': <float-timestamp>,
                'fluidinfo.com/info/url': <url>,
                'fluidinfo.com/info/username': <username>,
            }
        """
        followedObjectsResult = getObjectIDs([username + u'/follows'])
        subselect = followedObjectsResult.get_select_expr(TagValue.objectID)

        where = [Comment.objectID == CommentObjectLink.commentID,
                 CommentObjectLink.objectID.is_in(subselect)]
        return self._findComments(where, limit, olderThan, newerThan)

    def getForFollowedUsers(self, username, limit=20, olderThan=None,
                            newerThan=None):
        """Get the comments made by all the users followed by the given user.

        @param username: The user to get the comments for.
        @param limit: Optionally, The maximum number of comments to return.
        @param olderThan: Optionally a C{datetime} indicating to return only
            comments older than it.
        @param newerThan: A C{datetime} indicating to return only
            comments newer than it.
        @return: A C{list} of comments represented by a C{dict} with the
            following format::

            {
                'fluidinfo.com/info/about': <about-value-list>,
                'fluidinfo.com/info/text': <comment-text>,
                'fluidinfo.com/info/timestamp': <float-timestamp>,
                'fluidinfo.com/info/url': <url>,
                'fluidinfo.com/info/username': <username>,
            }
        """
        return self._findComments([], limit, olderThan, newerThan,
                                  followedByUsername=username)

    def getAllFollowed(self, username, limit=20, olderThan=None,
                       newerThan=None):
        """
        Get all the comments on the followed objects, by the followed users and
        by the requested user.

        @param username: The user to get the comments for.
        @param limit: Optionally, The maximum number of comments to return.
        @param olderThan: Optionally a C{datetime} indicating to return only
            comments older than it.
        @param newerThan: A C{datetime} indicating to return only
            comments newer than it.
        @return: A C{list} of comments represented by a C{dict} with the
            following format::

            {
                'fluidinfo.com/info/about': <about-value-list>,
                'fluidinfo.com/info/text': <comment-text>,
                'fluidinfo.com/info/timestamp': <float-timestamp>,
                'fluidinfo.com/info/url': <url>,
                'fluidinfo.com/info/username': <username>,
            }
        """
        store = getMainStore()
        result = getObjectIDs([username + u'/follows'])
        objectsSubselect = result.get_select_expr(TagValue.objectID)

        result = store.find(User.username,
                            User.objectID == TagValue.objectID,
                            Tag.id == TagValue.tagID,
                            Tag.path == username + u'/follows')
        usersSubselect = result.get_select_expr(User.username)

        where = [Comment.objectID == CommentObjectLink.commentID,
                 Or(CommentObjectLink.objectID.is_in(objectsSubselect),
                    Comment.username.is_in(usersSubselect),
                    Comment.username == username)]

        if olderThan is not None:
            where.append(Comment.creationTime < olderThan)

        return self._findComments(where, limit, olderThan, newerThan)

    def getFollowedObjects(self, username, limit=20, olderThan=None,
                           objectType=None):
        """Get the objects followed by the specified user.

        @param username: The user to get the followed objects for.
        @param limit: Optionally, The maximum number of objects to return.
        @param olderThan: Optionally a C{datetime} indicating to return only
            objects followed before the specified time.
        @param objectType: Optionally, a C{str} representing the object type
            to filter from the objects. The allowed values are C{url},
            C{user} and C{hashtag}.
        @return: A C{list} of objects followed by C{username} represented by
            a C{dict} with the following format::

              [
                {
                  'about': '<about>',
                  'creationTime': <float_timestamp>,
                  'following': True
                },
              ...
              ]
        """
        store = getMainStore()
        where = [TagValue.tagID == Tag.id,
                 TagValue.objectID == AboutTagValue.objectID,
                 Tag.path == username + u'/follows']
        if olderThan is not None:
            where.append(TagValue.creationTime < olderThan)
        if objectType is not None:
            if objectType == 'user':
                where.append(Like(AboutTagValue.value, u'@%'))
            elif objectType == 'url':
                where.append(Like(AboutTagValue.value, u'http%'))
            elif objectType == 'hashtag':
                where.append(Like(AboutTagValue.value, u'#%'))
            else:
                raise FeatureError('Unknown object type.')

        result = store.find((TagValue.objectID, AboutTagValue.value,
                             TagValue.creationTime), where)
        result = result.order_by(Desc(TagValue.creationTime))
        result = list(result.config(limit=limit))

        objectIDs = [objectID for objectID, _, _ in result]

        if self._user.username != username:
            callerObjectIDs = set(store.find(
                TagValue.objectID,
                Tag.id == TagValue.tagID,
                Tag.path == self._user.username + u'/follows',
                TagValue.objectID.is_in(objectIDs)))
        else:
            callerObjectIDs = None

        return [{u'about': about,
                 u'following': (objectID in callerObjectIDs
                                if callerObjectIDs is not None else True),
                 u'creationTime': (timegm(creationTime.utctimetuple()) +
                                   float(creationTime.strftime('0.%f')))}
                for objectID, about, creationTime in result]


def extractAtnames(comment):
    """Find all @names in a comment.

    @param comment: The C{unicode} comment text.
    @return: A C{list} of C{@}names, with no duplicates, in the order they
        appear in the comment.
    """
    return uniqueList(findall(ATNAME_REGEX, comment))


def extractHashtags(comment):
    """Find all #hashtags in a comment.

    @param comment: The C{unicode} comment text.
    @return: A C{list} of #hashtags, with no duplicates, in the order they
        appear in the comment.
    """
    return uniqueList(findall(HASHTAG_REGEX, comment))


def extractPlustags(comment):
    """Find all +plustags in a comment.

    @param comment: The C{unicode} comment text.
    @return: A C{list} of +plustags, with no duplicates, in the order they
        appear in the comment.
    """
    return uniqueList(findall(PLUSTAG_REGEX, comment))


def extractURLs(comment):
    """Find all URLs in a comment.

    @param comment: The C{unicode} comment text.
    @return: A C{list} of about values from the comment, with no duplicates,
        in the order they appear in the comment.
    """
    return uniqueList(findall(URL_REGEX, comment))


def extractFiles(comment):
    """Find all files in a comment.

    @param comment: The C{unicode} comment text.
    @return: A C{list} of about values from the comment, with no duplicates,
        in the order they appear in the comment.
    """
    return uniqueList(findall(FILE_REGEX, comment))


def parseCommentURL(url):
    """Parse a comment URL and extract the importer, username and timestamp.

    @param url: The URL to parse, matching the following format::

          https://loveme.do/comment/importer/name/2012-08-03T22:04:13.698896

    @raise ValueError: Raised if the URL is malformed.
    @return: A C{(importer, username, timestamp)} 3-tuple.  The timestamp is a
        C{datetime} instance.
    """
    _, path, importer, username, isoTimestamp = url.rsplit('/', 4)
    if path != 'comment':
        raise ValueError('Invalid root path, expected "comment".')
    try:
        timestamp = datetime.strptime(isoTimestamp, '%Y-%m-%dT%H:%M:%S.%f')
    except ValueError:
        # Maybe the ISO timestamp doesn't contain microseconds.
        timestamp = datetime.strptime(isoTimestamp, '%Y-%m-%dT%H:%M:%S')
    return importer, username, timestamp
