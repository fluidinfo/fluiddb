"""Generates a fluidinfo.com/trending tag on the fluidinfo.com object."""

from datetime import datetime, timedelta
import json
from operator import itemgetter
import re
import time

from storm.expr import Alias, Count, Desc, Func, Like, Row

from fluiddb.application import setConfig, setupConfig
from fluiddb.data.comment import Comment, CommentObjectLink
from fluiddb.data.value import AboutTagValue
from fluiddb.model.object import ObjectAPI
from fluiddb.model.user import getUser
from fluiddb.model.value import TagValueAPI
from fluiddb.scripts.commands import setupStore


def _sortUsernames(usernames):
    """
    Unescapes the usernames returned by PostgreSQL and sorts them by
    comment creation date.

    @param usernames: A C{str} with the usernames and comment creation time
        escaped.

    @return: A {list} of {list}s with usernames and comment creation time.
    """

    usernames = usernames.replace('\\\\\\"', '').replace('\\"', '')
    groups = re.findall('\((.*?)\)', usernames)
    usernames = []
    for item in groups:
        username, timestampText = item.split(',', 1)
        try:
            timestamp = datetime.strptime(
                timestampText, '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            timestamp = datetime.strptime(
                timestampText, '%Y-%m-%d %H:%M:%S')

        seconds = time.mktime(timestamp.utctimetuple())
        seconds += (timestamp.microsecond / 1000000.0)
        seconds -= time.timezone
        usernames.append([username, seconds])
    usernames = sorted(usernames, key=itemgetter(1), reverse=True)
    return usernames


def extractTrendingHashtags(store, limit=10, duration=None):
    """Extract information about trending hashtags and store it in FluidDB.

    @param store: The storm store to query and to save our result to.
    @param limit: Optionally, the number of objects to retrieve.
    @param duration: Optionally, the recent time period to look at when
        determining which hashtags are trending.  Default is 28 days.

    The storm query below results in SQL like:

        SELECT COUNT(DISTINCT comments.object_id) AS count,
               about_tag_values.value,
               array_agg(ROW(comments.username, comments.creation_time))
        FROM about_tag_values, comment_object_link, comments
        WHERE about_tag_values.value LIKE '#%' AND
              about_tag_values.object_id = comment_object_link.object_id AND
              comments.object_id = comment_object_link.comment_id AND
              comments.creation_time >= '2012-11-09 07:42:40'::TIMESTAMP AND
              CHAR_LENGTH(about_tag_values.value) >= 2
        GROUP BY about_tag_values.value
        ORDER BY count DESC
        LIMIT 10
    """
    duration = timedelta(days=28) if duration is None else duration
    startTime = datetime.utcnow() - duration
    count = Alias(Count(Comment.objectID, distinct=True))
    result = store.find(
        (count,
         AboutTagValue.value,
         Func('array_agg',
              Row(Comment.username, Comment.creationTime))),
        Like(AboutTagValue.value, u'#%'),
        AboutTagValue.objectID == CommentObjectLink.objectID,
        Comment.objectID == CommentObjectLink.commentID,
        Comment.creationTime >= startTime,
        Func('CHAR_LENGTH', AboutTagValue.value) >= 2)
    result.group_by(AboutTagValue.value)
    result.order_by(Desc(count))
    result.config(limit=limit)

    data = [{'count': count,
             'usernames': _sortUsernames(usernames),
             'value': hashtag}
            for count, hashtag, usernames in result]

    user = getUser(u'fluidinfo.com')
    tagValues = TagValueAPI(user)
    objectID = ObjectAPI(user).create(u'fluidinfo.com')
    tagValues.set({objectID: {
        u'fluidinfo.com/trending-hashtags': json.dumps(data)}})
    store.commit()


if __name__ == '__main__':
    store = setupStore('postgres:///fluidinfo', 'main')
    setConfig(setupConfig(None))
    extractTrendingHashtags(store)
