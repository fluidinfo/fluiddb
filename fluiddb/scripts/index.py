from datetime import datetime
from itertools import groupby
import logging
from operator import itemgetter
import sys
from uuid import UUID
import time

import transaction
from txsolr.client import SolrClient
from twisted.internet.defer import inlineCallbacks

from fluiddb.data.object import touchObjects
from fluiddb.data.store import getMainStore
from fluiddb.data.tag import Tag
from fluiddb.data.value import TagValue
from fluiddb.model.object import ObjectIndex


@inlineCallbacks
def deleteIndex(url):
    """Delete all documents in an L{ObjectIndex}.

    @param url: The URL of the Solr index to delete.
    @return: A C{Deferred} that will fire when all documents have been
        deleted.
    """
    client = SolrClient(url)
    yield client.deleteByQuery('*:*')
    yield client.commit()


@inlineCallbacks
def buildIndex(url, stream=sys.stderr):
    """Build documents in an L{ObjectIndex} for data in the main store.

    @param url: The URL of the Solr index to create documents in.
    @param stream: The file descriptor to send progress updates to. Defaults to
        C{sys.stderr}.
    @raise RuntimeError: Raised if the Solr index is not empty.
    @return: A C{Deferred} that will fire with the number of new documents
        that were created in the index.
    """
    client = SolrClient(url)
    response = yield client.search('*:*', rows=1)
    if response.results.docs:
        raise RuntimeError('Index is not empty!')
    yield updateIndex(url, stream=stream)


@inlineCallbacks
def updateIndex(url, createdAfterTime=datetime.min, stream=sys.stderr):
    """
    Build documents in an L{ObjectIndex} for data in the main store
    that has been updated since the provided C{datetime}.

    @param url: The URL of the Solr index to create documents in.
    @param createdAfterTime: An inclusive C{datetime} offset from which to
        update new tag-values.
    @param stream: The file descriptor to send progress updates to. Defaults to
        C{sys.stderr}.
    @return: A C{Deferred} that will fire with the number of new documents
        that were created in the index.
    """
    client = SolrClient(url)
    index = ObjectIndex(client)
    MAX_DOCUMENTS = 1000

    # setup progress bar
    progressbarWidth = 78
    totalRows = getMainStore().find(TagValue).count()
    documentsPerDash = totalRows / progressbarWidth
    stream.write("[%s]" % (" " * progressbarWidth))
    stream.flush()
    stream.write("\b" * (progressbarWidth + 1))  # return to start of bar

    documents = {}
    documentsProcessed = 0
    result = groupby(_getAllTagValues(createdAfterTime), itemgetter(2))
    for objectID, values in result:
        tagValues = dict((path, value) for path, value, _ in values)
        documents.update({objectID: tagValues})
        if len(documents) >= MAX_DOCUMENTS:
            yield index.update(documents)
            documents = {}
        documentsProcessed += 1
        if documentsProcessed == documentsPerDash:
            stream.write("-")
            stream.flush()
            documentsProcessed = 0
    if documents:
        yield index.update(documents)

    yield client.commit()


def _getAllTagValues(updatedSince):
    """
    Get all L{Tag} and L{TagValue}s that have been updated since the
    provided C{datetime}.

    @param updatedSince: An inclusive C{datetime} offset from which to
        update new tag-values.
    @return: A C{generator} that yields each updated tag individually.
    """
    store = getMainStore()
    CHUNK_SIZE = 500000
    result = store.find(TagValue, TagValue.creationTime >= updatedSince)
    totalRows = result.count()
    chunks = totalRows / CHUNK_SIZE
    if chunks == 0:
        chunks = 1

    for i in range(chunks):
        limit = CHUNK_SIZE if (i != chunks - 1) else None
        offset = i * CHUNK_SIZE
        result = store.find((Tag.path, TagValue.value, TagValue.objectID,
                             TagValue.creationTime),
                            Tag.id == TagValue.tagID,
                            TagValue.creationTime >= updatedSince)
        result = result.order_by(TagValue.objectID, TagValue.creationTime)
        result = result.config(limit=limit, offset=offset)
        for row in result:
            yield row[:-1]


def batchIndex(objectsFilename, interval, maxObjects, sleepFunction=None):
    """
    Touches all the objects in a given file in batches every a given interval.

    @param objectsFilename: The path of the file with the object IDS to touch.
    @param interval: The interval in minutes to touch a batch of objects.
    @param maxObjects: The number of objects to process in each batch.
    @param sleepFunction: a C{time.sleep} like function used for testing
        purposes.
    """
    if sleepFunction is None:
        sleepFunction = time.sleep
    objectIDs = []
    batch = 0
    interval = interval * 60
    with open(objectsFilename) as objectsFile:
        for line in objectsFile:
            if len(objectIDs) == 0:
                logging.info('Processing batch %d (%d objects processed).'
                             % (batch, batch * maxObjects))
            try:
                objectID = UUID(line.strip())
                objectIDs.append(objectID)
            except ValueError:
                logging.error('Invalid objectID: %r', line)
                continue
            if len(objectIDs) >= maxObjects:
                touchObjects(objectIDs)
                try:
                    transaction.commit()
                except:
                    transaction.abort()
                    raise
                logging.info('Batch done. Sleeping until next batch.')
                objectIDs = []
                batch += 1
                sleepFunction(interval)
        touchObjects(objectIDs)
        try:
            transaction.commit()
        except:
            transaction.abort()
            raise
        logging.info('All objects processed.')
