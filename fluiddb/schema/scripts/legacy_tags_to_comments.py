"""
Find primitive tag values that can be converted to comments, and
convert them.
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


def autovivify(levels=1, final=dict):
    return (defaultdict(final) if levels < 2 else
            defaultdict(lambda: autovivify(levels - 1, final)))


def lowercaseAbout(about):
    """Lowercase about values, leaving URLs alone.

    @param about: A C{unicode} about value.
    @return: An appropriately lowercased about value.
    """
    if not (about.startswith('http://') or about.startswith('https://')):
        return about.lower()
    else:
        return about


def extractNonStandardTagsForUser(config, username):
    user = getUser(username)
    result = config.store.find((TagValue, AboutTagValue),
                               TagValue.tagID == Tag.id,
                               TagValue.creatorID == user.id,
                               AboutTagValue.objectID == TagValue.objectID,
                               TagValue.creationTime > config.start)
    comments = []
    nResults = result.count()
    nAdded = nIgnored = 0
    print '\nProcessing non-standard tags for %r. Found %d instances.' % (
        username, nResults)
    for count, (tagValue, about) in enumerate(result):
        path = tagValue.tag.path
        value = tagValue.value
        when = tagValue.creationTime
        about = about.value

        if (path.endswith('/comment') or
                path.endswith('/flickr') or
                path.endswith('/follows') or
                path.endswith('/foursquare') or
                path.endswith('/image') or
                path.endswith('/lastfm') or
                path.endswith('/lat-long') or
                path.endswith('/latitude') or
                path.endswith('/like') or
                path.endswith('/linkedin') or
                path.endswith('/longitude') or
                path.endswith('/mentioned') or
                path.endswith('/rating') or
                path.endswith('/read-later') or
                path.endswith('/tumblr') or
                path.endswith('/tweet') or
                path.endswith('/twitter') or
                path.endswith('/url') or
                path.endswith('/yahoo') or
                path == u'stocktwits.com/symbol' or
                isinstance(value, dict) or
                # Ignore massive njr tag values:
                (isinstance(value, unicode) and len(value) > 500) or
                path.count('/') != 1):
            # Note the count of '/' in the path excludes all private tags
            # and also all username/tags/xxx tags.
            nIgnored += 1
            # print '\nread-later %d/%s: Skipped.' % (count + 1, nResults)
            continue

        nAdded += 1

        if value is not None and value != '':
            if isinstance(value, list):
                value = u' '.join(value)
            comment = u'#%s %s' % (path.split('/')[-1], value)
        else:
            comment = u'#%s' % (path.split('/')[-1],)

        print ('\nnon-standard tag %d/%d for %s:\n  tag=%r\n  value=%r'
               '\n  about=%r\n  comment=%r\n  when=%s' % (
                   count + 1, nResults, username, path, value, about, comment,
                   when.isoformat()))

        comments.append({'about': about, 'text': comment, 'when': when,
                         'username': username})

    print ('\nSummary: found %d/%d usable non-standard tags for %s. '
           'Ignored %d values.' % (nAdded, nResults, username, nIgnored))

    return {'comments': comments}


def extractReadLater(config):
    result = config.store.find((TagValue, User, AboutTagValue),
                               TagValue.tagID == Tag.id,
                               TagValue.creatorID == User.id,
                               AboutTagValue.objectID == TagValue.objectID,
                               TagValue.creationTime > config.start,
                               Tag.path.like(u'%/read-later'))
    nResults = result.count()
    nAdded = nIgnored = 0
    print 'PROCESSING */read-later tags. Found %d instances.' % nResults
    comments = []
    usernames = set()

    for count, (tagValue, user, about) in enumerate(result):
        path = tagValue.tag.path
        username = user.username
        value = tagValue.value
        about = about.value
        when = tagValue.creationTime

        if (path.count('/') != 1 or
                username == u'test'):
            nIgnored += 1
            # print '\nread-later %d/%s: Skipped.' % (count + 1, nResults)
            continue

        usernames.add(username)
        if value is not True and value is not None:
            print 'UNUSUAL: read-later value: %r for path %r.' % (value, path)

        comment = u'#readlater'

        print ('\nread-later %d/%d:\n  user=%r\n  when=%s\n  path=%r'
               '\n  about=%r\n  comment=%r' %
               (count + 1, nResults, username,
                when.isoformat(), path, about, comment))

        nAdded += 1
        comments.append({'about': about, 'text': comment,
                         'when': when, 'username': username})

    print ('\nSummary: found %d/%d usable read-later tags. Ignored %d values.'
           % (nAdded, nResults, nIgnored))

    return {'usernames': usernames, 'comments': comments}


def extractTags(config):
    result = config.store.find((TagValue, User, AboutTagValue),
                               TagValue.tagID == Tag.id,
                               TagValue.creatorID == User.id,
                               AboutTagValue.objectID == TagValue.objectID,
                               TagValue.creationTime > config.start,
                               Tag.path.like(u'%/tags/%'))
    nResults = result.count()
    nAdded = nIgnored = 0
    print 'PROCESSING */tags/* tags. Found %d instances.' % nResults
    tags = autovivify(3, set)
    comments = []
    usernames = set()

    for count, (tagValue, user, about) in enumerate(result):
        path = tagValue.tag.path
        username = user.username
        value = tagValue.value
        about = about.value
        tag = path.split('/')[-1]
        when = tagValue.creationTime

        if (path.count('/') != 2 or
                username == u'fluiddb' or
                username == u'nfpetrovici' or
                username == u'tagnroll.com' or
                username == u'test'):
            nIgnored += 1
            # print '\ntags %d/%s: Skipped.' % (count + 1, nResults)
            continue

        usernames.add(username)
        if value:
            print 'UNUSUAL: tags value: %r for path %r.' % (value, path)

        comment = u'#' + tag

        print ('\ntags %d/%d:\n  user=%r\n  when=%s\n  path=%r'
               '\n  about=%r\n  comment=%r' %
               (count + 1, nResults, username,
                when.isoformat(), path, about, comment))

        tags[username][lowercaseAbout(about)][when].add(comment)

        nAdded += 1

    print ('\nScan summary: found %d/%d usable */tags/* values. Ignored %d '
           'values.' % (nAdded, nResults, nIgnored))

    nAdded = 0
    for username in tags:
        for about in tags[username]:
            for when in tags[username][about]:
                nAdded += 1
                comment = u' '.join(sorted(tags[username][about][when]))
                print ('\ngrouped */tags/*\n  user=%r\n  when=%s\n  about=%r'
                       '\n  comment=%r'
                       % (username, when.isoformat(), about, comment))
                comments.append({'about': about, 'text': comment,
                                 'when': when, 'username': username})

    return {'usernames': usernames, 'comments': comments}


def extractRatings(config):
    result = config.store.find((TagValue, User, AboutTagValue),
                               TagValue.tagID == Tag.id,
                               TagValue.creatorID == User.id,
                               AboutTagValue.objectID == TagValue.objectID,
                               TagValue.creationTime > config.start,
                               Tag.path.like(u'%/' + u'rating'))
    nResults = result.count()
    nAdded = nIgnored = 0
    usernames = set()
    comments = []
    print 'PROCESSING */rating tags. Found %d instances.' % nResults
    for count, (tagValue, user, about) in enumerate(result):
        path = tagValue.tag.path
        username = user.username
        value = tagValue.value
        about = about.value
        when = tagValue.creationTime
        if (path.count('/') != 1 or
                username == u'fluidinfo.com' or
                username == u'tagnroll.com' or
                username == u'gottahavacuppamocha.com' or
                username == u'simonandschuster.com' or
                username == u'test' or
                path == u'nfpetrovici/links/rating' or
                path == u'nfpetrovici/users/rating' or
                isinstance(value, dict) or
                value is None):
            # Note: the above condition filters out private tags by testing
            # the count of '/' in the path.
            nIgnored += 1
            # print '\nrating %d/%s: Skipped.' % (count + 1, nResults)
            continue

        comment = 'Rating: %s' % (value,)
        print ('\nrating %d/%d:\n  user=%r\n  when=%s\n  tag=%r\n  about=%r'
               '\n  comment=%r' % (count + 1, nResults, username,
                                   when.isoformat(), path, about, comment))
        nAdded += 1
        usernames.add(username)
        comments.append({'about': about, 'text': comment,
                         'when': when, 'username': username})

    print '\nSummary: found %d/%d usable rating tags. Ignored %d values.' % (
        nAdded, nResults, nIgnored)

    return {'usernames': usernames, 'comments': comments}


def extractCommentsImagesLikesAndURLs(config):
    comments = []
    usernames = set()
    for tagName in (u'comment', u'image', u'like', u'url'):
        result = config.store.find((TagValue, User, AboutTagValue),
                                   TagValue.tagID == Tag.id,
                                   TagValue.creatorID == User.id,
                                   AboutTagValue.objectID == TagValue.objectID,
                                   TagValue.creationTime > config.start,
                                   Tag.path.like(u'%/' + tagName))
        nResults = result.count()
        nAdded = nIgnored = 0
        print 'PROCESSING */%s tags. Found %d instances.' % (tagName, nResults)
        for count, (tagValue, user, about) in enumerate(result):
            path = tagValue.tag.path
            username = user.username
            value = tagValue.value
            about = about.value
            when = tagValue.creationTime
            if (path.count('/') != 1 or
                    username == u'fluidinfo.com' or
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
                # print '\n%s %d/%s: Skipped.' % (tagName, count + 1, nResults)
                continue
            if tagName == u'like':
                if value is True or value is None:
                    comment = 'Like!'
                else:
                    print 'UNUSUAL: like value: %r' % (value,)
                    comment = value
            elif tagName == u'rating':
                comment = 'Rating: %s' % (value,)
            else:
                if isinstance(value, list):
                    comment = u' '.join(value)
                else:
                    comment = value

            print ('\n%s %d/%d:\n  user=%r\n  when=%s\n  tag=%r\n  about=%r'
                   '\n  comment=%r' % (
                   tagName, count + 1, nResults, username, when.isoformat(),
                   path, about, comment))
            if comment != value:
                print '  orig=%r' % (value,)
            nAdded += 1
            usernames.add(username)
            comments.append({'about': about, 'text': comment,
                             'when': when, 'username': username})

        print ('\nSummary: found %d/%d usable %r comments. Ignored %d '
               'values.' % (nAdded, nResults, tagName, nIgnored))

    return {'usernames': usernames, 'comments': comments}


if __name__ == '__main__':
    print __doc__
    config = Config()
    setConfig(setupConfig(None))
    usernames = set()
    comments = []

    # USERNAME/READ-LATER TAGS
    start = overallStart = time.time()
    previousCount = len(comments)
    result = extractReadLater(config)
    usernames.update(result['usernames'])
    comments.extend(result['comments'])
    elapsed = time.time() - start
    print 'Extracted %d readlater comments in %s seconds' % (
        len(comments) - previousCount, elapsed)

    # USERNAME/TAG/* TAGS
    start = time.time()
    previousCount = len(comments)
    result = extractTags(config)
    usernames.update(result['usernames'])
    comments.extend(result['comments'])
    elapsed = time.time() - start
    print 'Extracted %d user/tags/* comments in %s seconds' % (
        len(comments) - previousCount, elapsed)

    # USERNAME/RATING TAGS
    start = time.time()
    previousCount = len(comments)
    result = extractRatings(config)
    usernames.update(result['usernames'])
    comments.extend(result['comments'])
    elapsed = time.time() - start
    print 'Extracted %d user/rating comments in %s seconds' % (
        len(comments) - previousCount, elapsed)

    # USERNAME/{COMMENT/IMAGE/LIKE/URL} TAGS
    start = time.time()
    previousCount = len(comments)
    result = extractCommentsImagesLikesAndURLs(config)
    usernames.update(result['usernames'])
    comments.extend(result['comments'])
    elapsed = time.time() - start
    print 'Extracted %d comment/image/like/url comments in %s seconds' % (
        len(comments) - previousCount, elapsed)

    print '%d users have used the system.' % len(usernames)

    # USERNAME/<NON-STANDARD-NAME> TAGS
    start = time.time()
    previousCount = len(comments)
    for username in sorted(usernames):
        result = extractNonStandardTagsForUser(config, username)
        comments.extend(result['comments'])
    elapsed = time.time() - start
    print 'Extracted %d non-standard comments in %s seconds' % (
        len(comments) - previousCount, elapsed)

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
