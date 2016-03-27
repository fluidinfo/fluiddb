from uuid import uuid4, UUID

from twisted.internet.defer import DeferredList, fail
from txsolr import SolrClient

from fluiddb.application import getConfig
from fluiddb.data.object import ObjectIndex, SearchError
from fluiddb.data.value import (
    AboutTagValue, createAboutTagValue, getAboutTagValues,
    getTagPathsAndObjectIDs, getTagPathsForObjectIDs, getObjectIDs)
from fluiddb.exceptions import FeatureError
from fluiddb.model.factory import APIFactory
from fluiddb.query.grammar import Node


class ObjectAPI(object):
    """The public API for objectIDs in the model layer.

    @param user: The L{User} to perform operations on behalf of.
    @param factory: Optionally, the API factory to use when creating internal
        APIs.  Default is L{APIFactory}.
    """

    def __init__(self, user, factory=None):
        self._user = user
        self._factory = factory or APIFactory()

    def create(self, value=None):
        """Create a new object.

        If the about C{value} already exists, the matching object ID will be
        returned.  Otherwise, a new one is created.  An L{AboutTagValue} is
        not created if C{value} is not provided.

        @param value: Optionally, an L{AboutTagValue.value} to associate with
            the new object.
        @return: A L{UUID} representing the object ID for the exsiting object,
            if one matching the value already exists, or a new object ID.
        """
        if not value:
            return uuid4()

        from fluiddb.model.user import getUser

        existingValue = getAboutTagValues(values=[value]).one()
        if existingValue:
            return existingValue.objectID
        else:
            objectID = uuid4()
            updates = {objectID: {u'fluiddb/about': value}}
            self._factory.tagValues(getUser(u'fluiddb')).set(updates)
            createAboutTagValue(objectID, value)
            return objectID

    def get(self, values):
        """Get object IDs matching C{fluiddb/about} tag values.

        @param values: A C{list} of C{fluiddb/about} tag values.
        @return: A C{dict} mapping C{fluiddb/about} tag values to object IDs.
        """
        result = getAboutTagValues(values=values)
        return dict(result.values(AboutTagValue.value, AboutTagValue.objectID))

    def getTagsByObjects(self, objectIDs):
        """Get the L{Tag.path}s associated with a C{list} of objects.

        @param objectIDs: A C{list} of C{objectID} for which we want to request
            all the L{Tag.path}s.
        @return: A C{dict} mapping object IDs to C{list}s of L{Tag.path}s.
        """
        result = {}
        for path, objectID in getTagPathsAndObjectIDs(objectIDs):
            if objectID not in result:
                result[objectID] = []
            result[objectID].append(path)
        return result

    def getTagsForObjects(self, objectIDs):
        """Get the L{Tag.path}s associated with a C{list} of objects.

        @param objectIDs: A C{list} of C{objectID} for which we want to request
            all the L{Tag.path}s.
        @return: A C{list} of L{Tag.path}s associated with the objects.
        """
        return list(getTagPathsForObjectIDs(objectIDs))

    def search(self, queries, implicitCreate=True):
        """Find object IDs matching specified L{Query}s.

        @param queries: The sequence of L{Query}s to resolve.
        @param implicitCreate: Optionally a flag indicating if nonexistent
            objects should be created for special tags like C{fluiddb/about}.
            Default is L{True}.
        @return: A L{SearchResult} configured to resolve the specified
            L{Query}s.
        """
        if not queries:
            raise FeatureError('Queries must be provided.')

        idQueries = []
        aboutQueries = []
        hasQueries = []
        solrQueries = []
        for query in queries:
            if isEqualsQuery(query, u'fluiddb/id'):
                idQueries.append(query)
            elif isEqualsQuery(query, u'fluiddb/about'):
                aboutQueries.append(query)
            elif isHasQuery(query):
                hasQueries.append(query)
            else:
                solrQueries.append(query)

        index = getObjectIndex()
        specialResults = self._resolveAboutQueries(aboutQueries,
                                                   implicitCreate)
        specialResults.update(self._resolveFluiddbIDQueries(idQueries))
        specialResults.update(self._resolveHasQueries(hasQueries))
        return SearchResult(index, solrQueries, specialResults)

    def _resolveAboutQueries(self, queries, implicitCreate):
        """
        Find object IDs matching specified C{fluiddb/about == "..."} L{Query}s.

        @param queries: A sequence of L{Query}s to resolve.
        @param implicitCreate: A flag indicating if nonexistent objects should
            be created.
        """
        from fluiddb.model.user import getUser

        results = {}
        aboutValues = set()
        queriesByAboutValue = {}
        for query in queries:
            aboutValue = query.rootNode.right.value
            if not isinstance(aboutValue, unicode):
                # Search errors should be raised by the asynchronous
                # SearchResult.get().
                results[query] = SearchError('Invalid about value type.')
                continue
            aboutValues.add(aboutValue)
            queriesByAboutValue[aboutValue] = query

        if aboutValues:
            objectsByAbout = self._factory.objects(self._user).get(aboutValues)

            # Create non existent objects if the option is given.
            if implicitCreate:
                existingAboutValues = set(objectsByAbout)
                missingAboutValues = aboutValues - existingAboutValues
                updates = {}
                for aboutValue in missingAboutValues:
                    objectID = uuid4()
                    updates[objectID] = {u'fluiddb/about': aboutValue}
                    createAboutTagValue(objectID, aboutValue)
                    objectsByAbout[aboutValue] = objectID
                if missingAboutValues:
                    # FIXME We should use cachingGetUser here when
                    # possible. -jkakar
                    admin = getUser(u'fluiddb')
                    self._factory.tagValues(admin).set(updates)

            for aboutValue in aboutValues:
                objectID = objectsByAbout.get(aboutValue)
                query = queriesByAboutValue[aboutValue]
                results[query] = set([objectID]) if objectID else set()
        return results

    def _resolveFluiddbIDQueries(self, queries):
        """
        Find object IDs matching specified C{fluiddb/id == "..."} L{Query}s.
        """
        results = {}
        for query in queries:
            try:
                results[query] = set([UUID(query.rootNode.right.value)])
            except ValueError:
                # Search errors should be raised by the asynchronous
                # SearchResult.get().
                results[query] = SearchError('Invalid UUID.')
        return results

    def _resolveHasQueries(self, queries):
        """Find object IDs with a particular tag attached to them.

        @param queries: A list of L{Query} objects to resolve.
        @return: A C{dict} mapping L{Query}s sets of object IDs.
        """
        results = {}
        for query in queries:
            path = query.rootNode.left.value
            if path == u'fluiddb/id':
                results[query] = SearchError(
                    'fluiddb/id is not supported in queries.')
                continue

            # FIXME: make limits consistent across all the code base.
            result = getObjectIDs([path]).config(limit=10000)
            results[query] = set(result)
        return results


class SearchResult(object):
    """The representation of the result of a search operation.

    Note that having an instance of this class does not mean that a search has
    been performed.  Index queries are put off until absolutely necessary.

    Generally these should not be constructed directly, but instead retrieved
    from L{ObjectAPI.search}.

    @param index: The L{ObjectIndex} to use when resolving queries.
    @param queries: A sequence of L{Query} instances to resolve.
    @param results: Previous results of special queries already resolved.
    """

    def __init__(self, index, queries, results):
        self._index = index
        self._queries = queries
        self._specialResults = results

    def get(self):
        """Get the results of a search.

        @raise SearchError: Raised if a query could not be resolved (because
            Solr returned an error).
        @return: A C{Deferred} that fires with C{dict} that maps L{Query}
            instances to search results.
        """
        # Raise errors found when resolving special results.
        for result in self._specialResults.values():
            if isinstance(result, SearchError):
                return fail(result)

        deferreds = []
        for query in self._queries:
            deferreds.append(self._index.search(query))
        deferreds = DeferredList(deferreds, consumeErrors=True)

        def unpackValues(values):
            results = dict(self._specialResults)
            for i, (success, value) in enumerate(values):
                query = self._queries[i]
                if not success:
                    # FIXME If there's more than one exception we'll
                    # effectively ignore all but the first one with this
                    # logic.  It would be good if we didn't ignore/hide issues
                    # like this.
                    value.raiseException()
                results[query] = value
            return results

        return deferreds.addCallback(unpackValues)


def getObjectIndex():
    """Get an L{ObjectIndex}.

    @return: An L{ObjectIndex} configured to communicate with a Solr index.
    """
    url = getConfig().get('index', 'url')
    shards = getConfig().get('index', 'shards')
    client = SolrClient(url)
    return ObjectIndex(client, shards=shards)


def isEqualsQuery(query, path):
    """
    Determine if a L{Query} is of the form C{fluiddb/special = "..."}.
    Where special can be fluiddb/id, fluiddb/about, etc.

    @param query: The L{Query} to inspect.
    @param path: The C{unicode} path we're looking for.
    @return: C{True} if the query matches, otherwise C{False}.
    """
    return (query.rootNode.kind is Node.EQ_OPERATOR and
            query.rootNode.left.kind is Node.PATH and
            query.rootNode.left.value == path)


def isHasQuery(query):
    """Determine if a L{Query} is of the form C{has <path>}.

    @param query: The L{Query} to inspect.
    @return: C{True} if the query matches, otherwise C{False}.
    """
    return (query.rootNode.kind is Node.HAS)
