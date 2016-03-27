"""
Remove all musicbrainz.org tags since they take up a lot of space
and nobody is using them.
"""

import itertools
import logging
import time

from storm.locals import And

from fluiddb.application import setConfig, setupConfig, setupCache
from fluiddb.data.object import touchObjects
from fluiddb.data.tag import Tag
from fluiddb.data.value import TagValue
from fluiddb.model.user import getUser
from fluiddb.scripts.commands import setupStore


BATCH_SIZE = 100
SLEEP_DURATION = 60


def getTags(store):
    """Get the L{Tag.id}s and L{Tag.path}s for the C{musicbrainz.org} user.

    @param store: The store to user when fetching data.
    @return: A C{list} of L{Tag.id}s for the C{musicbrainz.org} user.
    """
    user = getUser(u'musicbrainz.org')
    result = store.find(Tag.id, Tag.creatorID == user.id)
    return list(result)


def getMusicbrainzObjectCount(store):
    """Get the count of objects with C{musicbrainz.org} L{TagValue}s.

    @param store: The store to user when fetching data.
    @return: The C{int} number of matching objects.
    """
    user = getUser(u'musicbrainz.org')
    result = store.find(TagValue.objectID, TagValue.creatorID == user.id)
    result.config(distinct=True)
    return result.count()


def getObjectIDs(store, tagIDs):
    """Get up to 100 object IDs that have at least one of the specified
    L{Tag}s.

    @param store: The store to use when fetching data.
    @param tagIDs: A sequence of L{Tag.id}s to match values against.
    @return: A C{set} of up to 100 matching object IDs.
    """
    result = store.find(TagValue.objectID, TagValue.tagID.is_in(tagIDs))
    result.config(limit=BATCH_SIZE)
    return set(result)


def deleteTagValues(store, tagIDs, objectIDs):
    """Delete those L{TagValue}s whose tagID is in tagIDs and whose
    objectID is in objectIDs.

    @param store: The store to use when fetching data.
    @param tagIDs: A sequence of L{TagValue.tagID}s to match values against.
    @param objectIDs: A sequence of L{TagValue.objectID}s to match values
        against.
    """
    result = store.find(And(TagValue.tagID.is_in(tagIDs),
                            TagValue.objectID.is_in(objectIDs))).remove()
    if result:
        touchObjects(objectIDs)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)8s  %(message)s')
    logging.info(__doc__)
    store = setupStore('postgres:///fluidinfo', 'main')
    config = setupConfig(None)
    setConfig(config)
    setupCache(config)

    logging.info('Loading musicbrainz.org tag paths.')
    tags = getTags(store)
    totalObjects = getMusicbrainzObjectCount(store)
    logging.info('Found %d objects to remove musicbrainz.org tag values from.',
                 totalObjects)

    deletedObjects = 0
    try:
        for i in itertools.count(1):
            objectIDs = getObjectIDs(store, tags)
            if not objectIDs:
                break

            # NOTE: ideally we'd use the SecureTagValueAPI to ensure that
            # permissions are checked, but the resulting query is poorly
            # optimized for this particular case.
            deleteTagValues(tags, objectIDs)
            store.commit()

            deletedObjects += len(objectIDs)
            logging.info('Deleted values from %d objects of %d.',
                         deletedObjects, totalObjects)
            if i % 100 == 0:
                logging.info('Sleeping for %ds...', SLEEP_DURATION)
                time.sleep(SLEEP_DURATION)
    except:
        logging.info('An error occurred...')
        store.rollback()
        raise
    else:
        logging.info('Done.')
        store.rollback()
