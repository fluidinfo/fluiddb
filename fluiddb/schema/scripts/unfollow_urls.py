"""
Unfollow auto followed URLs
"""
from datetime import datetime
import re
import time

from fluiddb.application import setConfig, setupConfig
from fluiddb.data.comment import Comment
from fluiddb.data.tag import Tag
from fluiddb.data.value import TagValue, getAboutTagValues
from fluiddb.model.user import getUser
from fluiddb.model.value import TagValueAPI
from fluiddb.scripts.commands import setupStore

URL_REGEX = re.compile(r'(?:^|\s)(https?://\S+)', re.UNICODE)

# Date the comment_autofollow.py patch was applied.
OLDER_THAN = datetime(2012, 06, 07, 02, 47)

if __name__ == '__main__':
    store = setupStore('postgres:///fluidinfo', 'main')
    setConfig(setupConfig(None))
    print __doc__

    usernames = store.find(Comment.username).config(distinct=True)

    count = 0
    for username in list(usernames):
        user = getUser(username)
        if user is None:
            print "Ignoring non existing user."
            continue

        print 'Examining objects followed by', username

        followTag = username + u'/follows'
        result = store.find(TagValue.objectID,
                            TagValue.tagID == Tag.id,
                            Tag.path == followTag,
                            TagValue.creationTime > OLDER_THAN)

        allObjectIDs = list(result)
        print '\t Found', len(allObjectIDs), 'followed objects.'
        BATCH_SIZE = 100
        while allObjectIDs:
            objectIDs = allObjectIDs[:BATCH_SIZE]
            allObjectIDs = allObjectIDs[BATCH_SIZE:]
            result = getAboutTagValues(objectIDs=objectIDs)
            followedURLsObjectIDs = [about.objectID for about in result
                                     if URL_REGEX.match(about.value)]
            if not followedURLsObjectIDs:
                continue
            print '\t Unfollowing', len(followedURLsObjectIDs), 'URLs'
            count += len(followedURLsObjectIDs)
            TagValueAPI(user).delete([(objectID, followTag)
                                      for objectID in followedURLsObjectIDs])

            store.commit()
            if count > 50000:
                print '** Sleeping one minute. Giving a breath to the DIH. **'
                time.sleep(60)
                count = 0
    print 'Done.'
