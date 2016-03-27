"""
Find primitive user/like tag values and convert them to #like comments.
"""

# Set dryRun to False if you want to actually import the comments.
dryRun = True

from collections import defaultdict
from datetime import datetime
import time

from fluiddb.application import setConfig, setupConfig
from fluiddb.data.tag import getTags, Tag
from fluiddb.data.user import User
from fluiddb.data.value import AboutTagValue, TagValue
from fluiddb.model.user import getUser
from fluiddb.scripts.commands import setupStore


class Config(object):
    store = setupStore('postgres:///fluidinfo', 'main')
    fluidinfoUser = getUser(u'fluidinfo.com')
    aboutTag = getTags(paths=[u'fluiddb/about']).one()
    start = datetime.strptime('2012-01-04 00:01', '%Y-%m-%d %H:%M')


def uploadComments(comments):
    """Upload batch comment data directly into Fluidinfo.

    This function is copied from fluiddb/scripts/dataset.py and modified to
    allow an explicit about value for comments to be given and to drop the
    passing of the importer name and url.

    @param comments: A C{list} of comment C{dict}s, each with keys:
        about: The C{unicode} string that the comment is about.
        text: The C{unicode} text of the comment.
        timestamp: A C{datetime.datetime} instance or C{None} if the
            current time should be used.
        username: The user's C{unicode} name in Fluidinfo.
    """
    if not dryRun:
        # import transaction and CommentAPI here to make sure no other code
        # in this file can possibly create comments.
        from fluiddb.security.comment import CommentAPI
        import transaction

    countByUser = defaultdict(int)
    nComments = len(comments)
    nUploaded = 0
    batchSize = 100
    print 'Uploading %d new comments.' % nComments

    while comments:
        # NOTE: Be careful here.  An obvious refactoring, at first glance,
        # is to move the logic to get the user and create the comment API
        # outside the loop, but doing so will cause the user object to be
        # used across transaction boundaries, which we don't want to do.
        # It's important that the database interactions for each batch
        # processed here are managed in a single transaction.
        thisBatch = comments[0:min(len(comments), batchSize)]
        try:
            user = getUser(u'fluidinfo.com')
            if user is None:
                raise Exception('Could not find fluidinfo.com user!')
            if not dryRun:
                api = CommentAPI(user)
            for comment in thisBatch:
                # An explicit about value must be in a list and should
                # be lowercased (if not a URL).
                print 'IMPORT %d: %r' % (nUploaded, comment)
                about = [lowercaseAbout(comment['about'])]
                text = comment['text']
                if text is not None:
                    text = text.strip()
                if text:
                    countByUser[comment['username']] += 1
                    if not dryRun:
                        api.create(text, comment['username'], about=about,
                                   when=comment['when'])
                else:
                    print 'Skipped comment with invalid text: %r' % (comment,)
                nUploaded += 1
            if not dryRun:
                transaction.commit()
            print '%d of %d comments imported.' % (nUploaded, nComments)
        except:
            if not dryRun:
                transaction.abort()
            raise
        else:
            comments = comments[len(thisBatch):]

    print 'Number of comments added by user:'
    for user in countByUser:
        print user, countByUser[user]


def lowercaseAbout(about):
    """Lowercase about values, leaving URLs alone.

    @param about: A C{unicode} about value.
    @return: An appropriately lowercased about value.
    """
    if not (about.startswith('http://') or about.startswith('https://')):
        return about.lower()
    else:
        return about


def extractLikes(config):
    comments = []
    result = config.store.find((TagValue, User, AboutTagValue),
                               TagValue.tagID == Tag.id,
                               TagValue.creatorID == User.id,
                               User.id != config.fluidinfoUser.id,
                               AboutTagValue.objectID == TagValue.objectID,
                               TagValue.creationTime > config.start,
                               Tag.path.like(u'%/like'))
    nResults = result.count()
    nAdded = nIgnored = 0
    print 'PROCESSING */like tags. Found %d instances.' % nResults
    for count, (tagValue, user, about) in enumerate(result):
        path = tagValue.tag.path
        username = user.username
        value = tagValue.value
        about = about.value
        when = tagValue.creationTime
        if (path.count('/') != 1 or
                username == u'tagnroll.com' or
                username == u'gottahavacuppamocha.com' or
                username == u'simonandschuster.com' or
                username == u'test' or
                isinstance(value, dict) or
                value == u'' or
                value == [u'']):
            # Note: the above condition filters out
            # user/private/tagname tags by testing the count of '/' in the
            # path.
            nIgnored += 1
            # print '\nlike %d/%s: Skipped.' % (count + 1, nResults)
            continue
        if value is True or value is None:
            comment = u'#like'
        else:
            print 'UNUSUAL: like value: %r' % (value,)
            comment = value

        print ('\nlike %d/%d:\n  user=%r\n  when=%s\n  tag=%r\n  about=%r'
               '\n  comment=%r' % (count + 1, nResults, username,
                                   when.isoformat(), path, about, comment))
        if comment != value:
            print '  orig=%r' % (value,)
        nAdded += 1
        comments.append({'about': about, 'text': comment,
                         'when': when, 'username': username})

    print ('\nSummary: found %d/%d usable like comments. Ignored %d '
           'values.' % (nAdded, nResults, nIgnored))

    return comments


if __name__ == '__main__':
    print __doc__
    config = Config()
    setConfig(setupConfig(None))

    # USERNAME/LIKE TAGS
    start = overallStart = time.time()
    comments = extractLikes(config)
    elapsed = time.time() - start
    print 'Extracted %d username/like comments in %s seconds' % (
        len(comments), elapsed)

    # UPLOAD & COMMIT
    start = time.time()
    uploadComments(comments)
    elapsed = time.time() - start
    print 'Upload of %d comments took %s seconds' % (len(comments), elapsed)
    elapsed = time.time() - overallStart
    print 'Extraction & upload of %d comments took %s seconds' % (
        len(comments), elapsed)
    if not dryRun:
        print 'Committing.'
        config.store.commit()

    print 'Done.'
