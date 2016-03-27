"""Remove comments without linked about values from the comments table."""

from fluiddb.data.comment import Comment
from fluiddb.data.tag import Tag
from fluiddb.data.value import TagValue
from fluiddb.scripts.commands import setupStore


BATCH_SIZE = 100


if __name__ == '__main__':
    print __doc__
    store = setupStore('postgres:///fluidinfo', 'main')
    result = store.find(TagValue,
                        TagValue.tagID == Tag.id,
                        Tag.path == u'fluidinfo.com/info/about',
                        TagValue.value == [])
    objectIDs = list(result.values(TagValue.objectID))
    print 'Found %d comments without abouts to remove.' % len(objectIDs)

    while objectIDs:
        batch = objectIDs[0:min(len(objectIDs), BATCH_SIZE)]
        result = store.find(Comment, Comment.objectID.is_in(batch))
        result.remove()
        store.commit()
        print 'Removed %d comments.' % len(batch)
        objectIDs = objectIDs[len(batch):]
    print 'Done.'
