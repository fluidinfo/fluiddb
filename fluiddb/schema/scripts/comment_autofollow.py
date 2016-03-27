"""
Follows all objects commented by users.
"""
import time

from fluiddb.application import setConfig, setupConfig
from fluiddb.scripts.commands import setupStore
from fluiddb.data.comment import Comment, CommentObjectLink
from fluiddb.model.user import getUser
from fluiddb.model.value import TagValueAPI

if __name__ == '__main__':
    store = setupStore('postgres:///fluidinfo', 'main')
    setConfig(setupConfig(None))
    print __doc__

    usernames = store.find(Comment.username).config(distinct=True)

    for username in list(usernames):
        user = getUser(username)
        if user is None:
            print "Ignoring non existing user."
            continue

        print 'Following objects commented by', username
        result = store.find(CommentObjectLink.objectID,
                            CommentObjectLink.commentID == Comment.objectID,
                            Comment.username == username)

        allObjectIDs = list(result.config(distinct=True))
        BATCH_SIZE = 100
        while allObjectIDs:
            targets = allObjectIDs[:BATCH_SIZE]
            followValues = dict((objectID, {username + u'/follows': None})
                                for objectID in targets)
            TagValueAPI(user).set(followValues)
            print '\t Following', len(targets), 'objects.'
            store.commit()
            allObjectIDs = allObjectIDs[BATCH_SIZE:]
            print 'Sleeping two seconds. Giving a breath to the DIH.'
            time.sleep(2)
