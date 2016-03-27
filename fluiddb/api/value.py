from json import dumps
from uuid import UUID

from twisted.internet.defer import fail
from twisted.internet import reactor
from twisted.internet.threads import blockingCallFromThread

from fluiddb.api.util import getCategoryAndAction
from fluiddb.common.types_thrift.ttypes import (
    ThriftValueType, TNonexistentTag, TPathPermissionDenied,
    TNoInstanceOnObject, TParseError, TBadRequest, TInvalidPath,
    TUnauthorized, ThriftValue)
from fluiddb.data.exceptions import MalformedPathError
from fluiddb.data.object import SearchError
from fluiddb.data.permission import Operation
from fluiddb.model.exceptions import UnknownPathError
from fluiddb.query.parser import IllegalQueryError, parseQuery
from fluiddb.query.grammar import QueryParseError
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.security.object import SecureObjectAPI
from fluiddb.security.value import SecureTagValueAPI
from fluiddb.web.query import (
    createBinaryThriftValue, createThriftValue, guessValue)


class TagPathAndValue(object):
    """Represents a pair of tag path and value.

    @param path: A UTF-8 C{str} with the tag path.
    @param value: A tag value.
    """

    def __init__(self, path=None, value=None):
        if not isinstance(value, ThriftValue):
            value = createThriftValue(value)
        self.path = path
        self.value = value


class FacadeTagValueMixin(object):

    def getTagInstance(self, session, path, objectId):
        """Get the L{TagValue} stored for an object.

        @param session: The L{FluidinfoSession} for the request.
        @param path: The L{Tag.path} of the value to retrieve.
        @param objectId: The object ID to retrieve the value for.
        @raise TNonexistentTag: Raised if the L{User} doesn't have
            permission to read the value.
        @raise TNoInstanceOnObject: Raised if specified L{Tag.path} doesn't
            exist or if no value is available for the specified object ID.
        @return: A C{Deferred} that will fire with a tuple of the Thrift value
            for the specified path and object ID, and the L{TagValue} itself.
        """
        path = path.decode('utf-8')
        objectID = UUID(objectId)

        def run():
            tagValues = SecureTagValueAPI(session.auth.user)
            try:
                result = tagValues.get([objectID], [path])
            except PermissionDeniedError as error:
                session.log.exception(error)
                path_, operation = error.pathsAndOperations[0]
                raise TNonexistentTag(path_)
            except UnknownPathError as error:
                session.log.exception(error)
                raise TNonexistentTag(path)
            if not result:
                raise TNoInstanceOnObject(path, objectId)
            else:
                tagValue = result[objectID][path]
                value = tagValue.value
                # FIXME This is a bit crap, but its easier than modifying
                # Thrift-related logic.
                if isinstance(value, dict):
                    mimeType = value['mime-type'].encode('utf-8')
                    value = createBinaryThriftValue(value['contents'],
                                                    mimeType)
                elif isinstance(value, UUID):
                    value = createThriftValue(str(value))
                else:
                    value = createThriftValue(value)
                return (value, tagValue)

        return session.transact.run(run)

    def setTagInstance(self, session, path, objectId, thriftValue):
        """Set a L{TagValue} for an object.

        @param session: The L{FluidinfoSession} for the request.
        @param path: The L{Tag.path} of the value to set.
        @param objectId: The object ID to set the value for.
        @param thriftValue: The value to set.
        @raise TNonexistentPath: Raised if the L{Tag.path} doesn't exist.
        @raise TPathPermissionDenied: Raised if the L{User} doesn't have
            permission to set the value.
        @return: A C{Deferred} that will fire when the value has been stored.
        """
        path = path.decode('utf-8')
        objectID = UUID(objectId)
        if thriftValue.valueType == ThriftValueType.BINARY_TYPE:
            value = {'mime-type': thriftValue.binaryKeyMimeType,
                     'contents': thriftValue.binaryKey}
        else:
            value = guessValue(thriftValue)
            if isinstance(value, list):
                value = [item.decode('utf-8') for item in value]
        values = {objectID: {path: value}}

        def run():
            try:
                SecureTagValueAPI(session.auth.user).set(values)
            except UnknownPathError as error:
                session.log.exception(error)
                raise TNonexistentTag(path.encode('utf-8'))
            except MalformedPathError as error:
                raise TInvalidPath(path.encode('utf-8'))
            except PermissionDeniedError as error:
                session.log.exception(error)
                path_, operation = error.pathsAndOperations[0]
                category, action = getCategoryAndAction(operation)
                raise TPathPermissionDenied(category, action, path_)

        return session.transact.run(run)

    def hasTagInstance(self, session, path, objectId):
        """Determine if a L{TagValue} is stored for an object.

        @param session: The L{FluidinfoSession} for the request.
        @param path: The L{Tag.path} of the value to check.
        @param objectId: The object ID to check.
        @raise TNonexistentPath: Raised if the L{Tag.path} doesn't exist,
            or if the L{User} doesn't have permission to read the value.
        """
        path = path.decode('utf-8')
        objectID = UUID(objectId)

        def run():
            tagValues = SecureTagValueAPI(session.auth.user)
            try:
                values = tagValues.get([objectID], [path])
                return createThriftValue(len(values.keys()) > 0)
            except UnknownPathError as error:
                session.log.exception(error)
                raise TNonexistentTag(path.encode('utf-8'))
            except PermissionDeniedError as error:
                session.log.exception(error)
                path_, operation = error.pathsAndOperations[0]
                raise TNonexistentTag(path_)

        return session.transact.run(run)

    def deleteTagInstance(self, session, path, objectId):
        """Delete a C{TagValue} stored for an object.

        @param session: The L{FluidinfoSession} for the request.
        @param path: The L{Tag.path} of the value to check.
        @param objectId: The object ID to check.
        @raise TNonexistentPath: Raised if the L{Tag.path} doesn't exist.
        @raise TPathPermissionDenied: Raised if the L{User} doesn't have
            permission to delete the value.
        """
        path = path.decode('utf-8')
        values = [(UUID(objectId), path)]

        def run():
            try:
                SecureTagValueAPI(session.auth.user).delete(values)
            except UnknownPathError as error:
                session.log.exception(error)
                raise TNonexistentTag(path.encode('utf-8'))
            except PermissionDeniedError as error:
                session.log.exception(error)
                path_, operation = error.pathsAndOperations[0]
                category, action = getCategoryAndAction(operation)
                raise TPathPermissionDenied(category, action, path_)

        return session.transact.run(run)

    def resolveQuery(self, session, query):
        """Get the object IDs that match a query.

        @param session: The L{FluidinfoSession} for the request.
        @param query: The query to resolve.
        @raise TBadRequest: If the given query is not encoded properly.
        @raise TParseError: If the query is not well formed.
        @raise TNonexistentTag: If the user doesn't have read permissions
            on the tags in the query.
        @return: A C{Deferred} that will fire with a C{list} of object ID
            C{str}s that match the query.
        """
        try:
            query = query.decode('utf-8')
        except UnicodeDecodeError as error:
            session.log.exception(error)
            error = TBadRequest('Query string %r was not valid UTF-8.' % query)
            return fail(error)
        try:
            parsedQuery = parseQuery(query)
        except QueryParseError as error:
            session.log.exception(error)
            return fail(TParseError(query, error.message))
        except IllegalQueryError as error:
            return fail(TBadRequest(str(error)))

        def run():
            objects = SecureObjectAPI(session.auth.user)
            objectIDs = self._resolveQuery(session, objects, parsedQuery)
            return [str(objectID) for objectID in objectIDs]

        return session.transact.run(run)

    def _resolveQuery(self, session, objects, query):
        """Resolve a L{Query}.

        @param session: The L{FluidinfoSession} for the request.
        @param objects: The L{SecureObjectAPI} to use to fetch object IDs.
        @param query: The L{Query} to resolve.
        @return: A C{list} of object ID C{str}s that match the query.
        """
        try:
            result = objects.search([query])
        except UnknownPathError as error:
            session.log.exception(error)
            unknownPath = error.paths[0]
            raise TNonexistentTag(unknownPath.encode('utf-8'))
        except PermissionDeniedError as error:
            session.log.exception(error)
            deniedPath, operation = error.pathsAndOperations[0]
            raise TNonexistentTag(deniedPath)

        try:
            with session.timer.track('index-search'):
                result = blockingCallFromThread(reactor, result.get)
        except SearchError as error:
            session.log.exception(error)
            raise TParseError(query, error.message)

        return result[query]

    def getValuesForQuery(self, session, query, tags=None):
        """Get L{TagValue}s that match a query.

        Existence checks are performed for L{Tag.path}s specified in the
        L{Query}, but not in the return list.  If requested tags don't exist
        we treat them as having no matches.

        @param session: The L{FluidinfoSession} for the request.
        @param query: The query to resolve.
        @param tags: Optionally, the sequence of L{Tag.path}s to retrieve
            values for.
        @raise TNonexistentTag: Raised if L{Tag}s in the L{Query} don't exist,
            or if the L{User} doesn't have L{Operation.READ_TAG_VALUE}
            permission on all L{Tag}s in the query.
        @raise TParseError: Raised if the L{Query} can't be parsed.
        @return: A L{Deferred} that will fire with a C{dict} that maps object
            IDs to L{Tag.path}s with L{TagValue}s, matching the following
            format::

              {'results': {
                  'id': {<object-id>: {<path>: {'value': <contents>},
                                       <path>: {'value-type': <contents>,
                                                'size': <size>}}}}}

            We only return the value type and the size for binary L{TagValue}s
            since JSON doesn't support binary strings.
        """
        try:
            parsedQuery = parseQuery(query.decode('utf-8'))
        except QueryParseError as error:
            session.log.exception(error)
            return fail(TParseError(query, error.message))
        except IllegalQueryError as error:
            return fail(TBadRequest(str(error)))
        if tags is not None:
            tags = [tag.decode('utf-8') for tag in tags]

        def run():
            tagValues = SecureTagValueAPI(session.auth.user)
            objects = SecureObjectAPI(session.auth.user)
            objectIDs = self._resolveQuery(session, objects, parsedQuery)
            if not objectIDs:
                return dumps({'results': {'id': {}}})
            try:
                values = tagValues.get(objectIDs, tags)
            except UnknownPathError as error:
                # One or more of the requested return Tag's doesn't exist.
                # We'll filter them out and try again because we don't want to
                # fail the request just because of a missing tag.
                filteredTags = set(tags) - set(error.paths)
                if not filteredTags:
                    return dumps({'results': {'id': {}}})
                values = tagValues.get(objectIDs, filteredTags)
            except PermissionDeniedError as error:
                session.log.exception(error)
                path_, operation = error.pathsAndOperations[0]
                raise TNonexistentTag(path_)

            valuesByObjectID = {}
            for objectID, tagPaths in values.iteritems():
                for tagPath, tagValue in tagPaths.iteritems():
                    value = tagValue.value
                    if isinstance(value, dict):
                        size = len(value[u'contents'])
                        mimeType = value[u'mime-type']
                        value = {u'value-type': mimeType,
                                 u'size': size}
                    elif isinstance(value, UUID):
                        value = {'value': str(value)}
                    else:
                        value = {'value': value}
                    value['updated-at'] = tagValue.creationTime.isoformat()
                    value['username'] = tagValue.creator.username
                    objectID = str(objectID)
                    valuesByObjectID.setdefault(objectID, {})[tagPath] = value
            result = {'results': {'id': valuesByObjectID}}
            return dumps(result)

        return session.transact.run(run)

    def deleteValuesForQuery(self, session, query, tags=None):
        """Delete L{TagValue}s that match a query.

        @param session: The L{FluidinfoSession} for the request.
        @param query: The query to resolve.
        @param tags: Optionally, the sequence of L{Tag.path}s to delete values
            for.
        @raise TNonexistentTag: Raised if any of the L{Tag}s in the
            L{Query} or to delete does not exist.
        @raise TPathPermissionDenied: Raised if the L{User} does not have
            L{Operation.READ_TAG_VALUE} permission on any of the L{Tag}s in the
            L{Query} or does not have L{Operation.DELETE_TAG_VALUE} permission
            on any of the L{Tag}s to set.
        @raise TParseError: Raised if the L{Query} can't be parsed.
        """
        try:
            parsedQuery = parseQuery(query.decode('utf-8'))
        except QueryParseError as error:
            session.log.exception(error)
            return fail(TParseError(query, error.message))
        except IllegalQueryError as error:
            return fail(TBadRequest(str(error)))
        if tags is not None:
            tags = [tag.decode('utf-8') for tag in tags]

        def run():
            tagValues = SecureTagValueAPI(session.auth.user)
            objects = SecureObjectAPI(session.auth.user)
            objectIDs = self._resolveQuery(session, objects, parsedQuery)
            values = []

            if tags is None:
                # delete all tags user has permissions for
                result = objects.getTagsByObjects(objectIDs,
                                                  Operation.DELETE_TAG_VALUE)
                for objectID, paths in result.iteritems():
                    for path in paths:
                        values.append((objectID, path))
            else:
                # delete only tags requested by user
                result = objects.getTagsByObjects(objectIDs)
                for objectID, paths in result.iteritems():
                    for path in paths:
                        if tags is None or path in tags:
                            values.append((objectID, path))

            if values:
                try:
                    tagValues.delete(values)
                except UnknownPathError as error:
                    session.log.exception(error)
                    path = error.paths[0]
                    raise TNonexistentTag(path.encode('utf-8'))
                except PermissionDeniedError as error:
                    session.log.exception(error)
                    path_, operation = error.pathsAndOperations[0]
                    category, action = getCategoryAndAction(operation)
                    raise TPathPermissionDenied(category, action, path_)

        return session.transact.run(run)

    def updateValuesForQueries(self, session, valuesQuerySchema):
        """Set L{TagValue}s that match a list of L{Query}s.

        @param session: The L{FluidinfoSession} for the request.
        @param valuesQuerySchema: L{ValuesQuerySchema}
        @raise TNonexistentTag: Raised if any of the L{Tag}s in the
            L{Query} or to set does not exist.
        @raise TNonexistentTag: Raised if the L{User} does not have
            L{Opeartion.READ_TAG_VALUE} permission on any of the L{Tag}s in the
            L{Query}.
        @raise TPathPermissionDenied: Raised if the L{User} does not have
            L{Operation.WRITE_TAG_VALUE} permission on any of the L{Tag}s to
            set.
        @raise TParseError: Raised if the L{Query} can't be parsed.
        """
        # Parse queries in the reactor thread, the query parser is not thread
        # safe.
        valuesByQuery = {}
        for query, tagsAndValues in valuesQuerySchema.queryItems:
            try:
                parsedQuery = parseQuery(query)
            except QueryParseError as error:
                session.log.exception(error)
                return fail(TParseError(query, error.message))
            except IllegalQueryError as error:
                return fail(TBadRequest(str(error)))
            valuesByQuery[parsedQuery] = tagsAndValues

        def run():
            objects = SecureObjectAPI(session.auth.user)

            try:
                searchQueries = objects.search(valuesByQuery.keys())
            except UnknownPathError as error:
                session.log.exception(error)
                unknownPath = error.paths[0]
                raise TNonexistentTag(unknownPath.encode('utf-8'))
            except PermissionDeniedError as error:
                session.log.exception(error)
                path_, operation = error.pathsAndOperations[0]
                if operation == Operation.CREATE_OBJECT:
                    raise TUnauthorized()
                else:
                    raise TNonexistentTag(path_)

            # Run queries.
            try:
                with session.timer.track('index-search'):
                    result = blockingCallFromThread(reactor, searchQueries.get)
            except SearchError as error:
                session.log.exception(error)
                raise TParseError(query, error.message)

            # Build a result set from the searches.
            values = {}
            for parsedQuery, objectIDs in result.iteritems():
                for objectID in objectIDs:
                    for tagAndValue in valuesByQuery[parsedQuery]:
                        value = guessValue(tagAndValue.value)
                        # FIXME: this code sucks, but I rather not having
                        # to modify guessValue to return a list, as that
                        # would break other code.
                        # Hopefully, we'll be able to remove this pretty
                        # soon.
                        if isinstance(value, list):
                            value = [item.decode('utf-8') for item in value]
                        if objectID not in values:
                            values[objectID] = {}
                        values[objectID][tagAndValue.path] = value

            # Update values.
            if values:
                tagValues = SecureTagValueAPI(session.auth.user)
                try:
                    result = tagValues.set(values)
                except UnknownPathError as error:
                    session.log.exception(error)
                    path = error.paths[0]
                    raise TNonexistentTag(path.encode('utf-8'))
                except MalformedPathError as error:
                    # FIXME: Modify MalformedPathError to have a path field.
                    raise TInvalidPath(str(error).encode('utf-8'))
                except PermissionDeniedError as error:
                    session.log.exception(error)
                    path_, operation = error.pathsAndOperations[0]
                    category, action = getCategoryAndAction(operation)
                    raise TPathPermissionDenied(category, action, path_)

        return session.transact.run(run)
