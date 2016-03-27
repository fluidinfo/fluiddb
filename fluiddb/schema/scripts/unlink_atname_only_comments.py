"""Remove comments that are only linked to an @name."""

import logging
from uuid import UUID

from fluiddb.data.comment import CommentObjectLink
from fluiddb.data.tag import getTags
from fluiddb.data.value import TagValue
from fluiddb.scripts.commands import setupStore


BATCH_SIZE = 100


def migrate(store):
    # Find all the @name about values.
    result = store.execute('SELECT value, object_id'
                           '    FROM about_tag_values'
                           "    WHERE value LIKE '@%'")
    aboutValues = dict((value, UUID(objectID)) for value, objectID in result)
    logging.info('Loaded %d @name about values', len(aboutValues))

    # Remove all the links between comments and @name values.
    affectedComments = set()
    i = 0
    for aboutValue, objectID in aboutValues.iteritems():
        result = store.find(
            CommentObjectLink,
            CommentObjectLink.objectID == objectID)
        comments = set(result.values(CommentObjectLink.commentID))
        affectedComments.update(comments)
        result.remove()
        store.commit()
        if len(comments):
            logging.info('Removed %s comment links for %d comments.',
                         aboutValue, len(comments))
    logging.info('Removed @name comment links for %d comments.',
                 len(affectedComments))

    # Find fluidinfo.com/info/about values for affected comments and remove
    # @names from the about lists.
    tagID = getTags([u'fluidinfo.com/info/about']).one().id
    comments = list(affectedComments)
    while comments:
        batch = comments[0:min(len(comments), BATCH_SIZE)]
        if not batch:
            break
        result = store.find(TagValue,
                            TagValue.tagID == tagID,
                            TagValue.objectID.is_in(batch))
        for i, value in enumerate(result):
            pass
            value.value = [about for about in value.value
                           if about not in aboutValues]
        logging.info('Updated about values for %d comments.', i + 1)
        store.commit()
        comments = comments[len(batch):]

    logging.info('Finished updating about values for %d comments.',
                 len(affectedComments))


if __name__ == '__main__':
    logging.basicConfig(filename='/mnt/unlink-log/unlink.log',
                        level=logging.INFO,
                        format='%(asctime)s %(levelname)8s  %(message)s')
    logging.info(__doc__)
    store = setupStore('postgres:///fluidinfo', 'main')
    try:
        migrate(store)
    except StandardError:
        store.rollback()
        logging.error("*** MASSIVE FAIL ***")
        raise
    else:
        store.commit()
        logging.info("*** DONE ***")
