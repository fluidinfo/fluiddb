import re
from uuid import UUID

from storm.locals import Storm, DateTime, Int, UUID as StormUUID

from twisted.internet.defer import inlineCallbacks, fail
from txsolr import escapeTerm

from fluiddb.data.path import isValidPath
from fluiddb.data.store import getMainStore
from fluiddb.query.grammar import Node


DEFAULT_ROW_LIMIT = 10 ** 6
CONTAINS_SPACES_REGEX = re.compile(r'\s', flags=re.UNICODE)


class SearchError(Exception):
    """Raised if an error occurs when a L{Query} is resolved."""

    def __init__(self, message):
        self.message = message


class ObjectIndex(object):
    """A full-text object index capable of finding results for L{Query}s.

    The Solr queries run in the process of using this index do not include
    explicit commits.  Either the Solr server should be configured to perform
    regular autocommits or users of this index should call L{commit}
    appropriately.

    @param client: The C{SolrClient} to use when interacting with the backend
        index.
    @param shards: An optional comma separated list of shard URLs to use for
        querying Solr.
    """

    def __init__(self, client, shards=None):
        self._client = client
        self._shards = shards

    def commit(self):
        """Commit changes to update the index.

        @return: A C{Deferred} that will fire when the commit is complete.
        """
        return self._client.commit()

    @inlineCallbacks
    def update(self, values):
        """Update indexed L{TagValue}s.

        @param values: A C{dict} mapping object IDs to tags and values,
            matching the following format::

              {<object-id>: {<path>: <value>,
                             <path>: {'value-type': <mime-type>,
                                      'file-id': <file-id>,
                                      'size': <size>}}}

            A binary L{TagValue} is represented using a C{dict} instead of a
            primitive, as shown for the second value.
        @return: A C{Deferred} that will fire when updates have completed.
        """
        documents = []
        for objectID, tagValues in values.iteritems():
            document = {'fluiddb/id': objectID,
                        'paths': tagValues.keys()}
            for path, value in tagValues.iteritems():
                fieldName, fieldValue = self._getField(path, value, raw=True)
                document[fieldName] = fieldValue

            documents.append(document)
        yield self._client.add(documents)

    def search(self, query):
        """Find object IDs matching the specified L{Query}.

        @param query: The L{Query} to resolve.
        @return: A C{Deferred} that will fire with a C{set} of matching object
            IDs.
        """
        try:
            solrQuery = self._buildSolrQuery(query.rootNode)
        except SearchError as error:
            return fail(error)

        if self._shards:
            deferred = self._client.search(solrQuery, rows=DEFAULT_ROW_LIMIT,
                                           shards=self._shards)
        else:
            deferred = self._client.search(solrQuery, rows=DEFAULT_ROW_LIMIT)

        def unpackObjectIDs(response):
            return set(UUID(document['fluiddb/id'])
                       for document in response.results.docs)

        return deferred.addCallback(unpackObjectIDs)

    def _buildSolrQuery(self, node):
        """Build a Solr query based on a L{Query} L{Node}.

        @param node: The L{Node} to build the query for.
        @return: A C{unicode} string with the resulting Solr query.
        """
        # Resolve composed queries recursively.
        if node.kind == Node.OR:
            return '(%s) OR (%s)' % (self._buildSolrQuery(node.left),
                                     self._buildSolrQuery(node.right))
        elif node.kind == Node.AND:
            return '(%s) AND (%s)' % (self._buildSolrQuery(node.left),
                                      self._buildSolrQuery(node.right))
        elif node.kind == Node.EXCEPT:
            return '(%s) NOT (%s)' % (self._buildSolrQuery(node.left),
                                      self._buildSolrQuery(node.right))

        path = node.left.value

        if path == u'fluiddb/id':
            raise SearchError("fluiddb/id is not supported in queries.")

        # Resolve unary operators.
        if node.kind == Node.HAS:
            return 'paths:"%s"' % path

        # Resolve binary operators.
        value = node.right.value
        if node.kind == Node.EQ_OPERATOR:
            fieldName, fieldValue = self._getField(path, value, raw=True)
            fieldValue = unicode(fieldValue)
            return '%s:"%s"' % (fieldName, escapeTerm(fieldValue))

        if node.kind == Node.NEQ_OPERATOR:
            fieldName, fieldValue = self._getField(path, value, raw=True)
            fieldValue = unicode(fieldValue)
            return 'NOT %s:"%s"' % (fieldName, escapeTerm(fieldValue))

        if node.kind == Node.MATCHES:
            fieldName, fieldValue = self._getField(path, value, raw=False)
            if value == '':
                # Ff value is empty, the value_fts_str field won't be present
                # in the document, because the <copyfield> directive in the
                # schema won't copy empty fields. We have to use this special
                # query to search documents without that field. This is a
                # special Solr query and won't work with raw lucene. More
                # information: http://wiki.apache.org/solr/SolrQuerySyntax
                return '-%s:[* TO *]' % fieldName
            else:
                #enable wildcards only if the query doesn't contain whitespace.
                if CONTAINS_SPACES_REGEX.search(value) is None:
                    matcher = escapeWithWildcards(fieldValue)
                else:
                    matcher = '"%s"' % escapeTerm(fieldValue)
                return '%s:%s' % (fieldName, matcher)

        if node.kind == Node.CONTAINS:
            fieldName, _ = self._getField(path, [], raw=True)
            return '%s:"%s"' % (fieldName, escapeTerm(value))

        # TODO: raise exception if we're using comparision operators with non
        # number values.
        if node.kind == Node.LT_OPERATOR:
            fieldName, fieldValue = self._getField(path, value, raw=False)
            return '%s:{* TO %f}' % (fieldName, fieldValue)
        if node.kind == Node.LTE_OPERATOR:
            fieldName, fieldValue = self._getField(path, value, raw=False)
            return '%s:[* TO %f]' % (fieldName, fieldValue)
        if node.kind == Node.GT_OPERATOR:
            fieldName, fieldValue = self._getField(path, value, raw=False)
            return '%s:{%f TO *}' % (fieldName, fieldValue)
        if node.kind == Node.GTE_OPERATOR:
            fieldName, fieldValue = self._getField(path, value, raw=False)
            return '%s:[%f TO *]' % (fieldName, fieldValue)

        raise SearchError('Unknown query operator')

    def _getField(self, path, value, raw):
        """Get a Solr dynamic field name and value for a given path and value.

        The dynamic field name is generated using the path and a suffix
        according to the value type.

        @param path: The C{unicode} path of the tag value.
        @param value: The value of the tag value.
        @param raw: A C{bool} indicating whether the document value should be
            raw or full text search for fields that use one.
        @return: A C{(fieldName, fieldValue)} 2-tuple.
        """
        if not isValidPath(path):
            raise ValueError('Path is not valid.')

        elif value is None:
            suffix = '_tag_null'
            value = False
        elif isinstance(value, bool):
            suffix = '_tag_bool'
        elif isinstance(value, (int, long, float)):
            suffix = '_tag_number'
        elif isinstance(value, basestring):
            suffix = '_tag_raw_str' if raw else '_tag_fts'
        elif isinstance(value, list):
            suffix = '_tag_set_str' if raw else '_tag_fts'
        elif isinstance(value, dict):
            suffix = '_tag_binary'
            value = value['file-id']
        else:
            raise TypeError("Unrecognized type: %s" % type(value))

        return (path + suffix), value


def escapeWithWildcards(term):
    """
    Escapes special characters of the Lucene Query Syntax except wildcards.

    @param term: The term to be escaped.
    @return the term with all the special characters escaped.
    """
    # First escape everything except \
    term = re.sub(r'[\+\-\&\|\!\(\)\{\}\[\]\^\"\:]', r'\\\g<0>', term)
    # Then escape \
    return re.sub(r'\\([^\+\-\&\|\!\(\)\{\}\[\]\^\"\:\*\?\~])', r'\\\\\g<1>',
                  term)


class DirtyObject(Storm):
    """An object in the system.

    @param objectId: The ID of the object.
    """

    __storm_table__ = 'dirty_objects'

    id = Int('id', primary=True, allow_none=False)
    objectID = StormUUID('object_id')
    updateTime = DateTime('update_time')

    def __init__(self, objectID):
        self.objectID = objectID


def createDirtyObject(objectID):
    """Create a new L{DirtyObject}.

    @param objectID: The ID for this object.
    @return: A new L{DirtyObject} instance persisted in the main store.
    """
    store = getMainStore()
    return store.add(DirtyObject(objectID))


def getDirtyObjects(objectIDs=None):
    """Get L{DirtyObject}s.

    @param objectIDs: Optionally, a sequence of L{DirtyObject.objectID}s to
        filter the result with.
    @return: A C{ResultSet} with matching L{DirtyObject}s.
    """
    store = getMainStore()
    where = []
    if objectIDs:
        where.append(DirtyObject.objectID.is_in(objectIDs))
    return store.find(DirtyObject, *where)


def touchObjects(objectIDs):
    """Add an object ID to the list of dirty objects.

    @param objectIDs: A sequence of object IDs.
    """
    for objectID in objectIDs:
        createDirtyObject(objectID)
