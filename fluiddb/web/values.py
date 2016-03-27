import types

from twisted.internet import defer
from twisted.web import http

from fluiddb.web.resource import WSFEResource
from fluiddb.web import payloads
from fluiddb.common.defaults import httpValueCategoryName
from fluiddb.common import error
from fluiddb.doc.api.http import apiDoc
from fluiddb.doc.api.http.registry import (
    registry, HTTPTopLevel, HTTPUsage, JSONPayload, PayloadField, Argument,
    Return, HTTPExample)
from fluiddb.api.value import TagPathAndValue
from fluiddb.web.query import createThriftValue
from fluiddb.web.mimeparse import parse_mime_type

tagArg = 'tag'
queryArg = 'query'
resultsKey = 'results'
idKey = 'id'
valueKey = 'value'


class ValuesQuerySchema(object):
    """
    Represents a /values request with a set of queries. This class contains
    class methods to parse the payload and check if it's well formed. It also
    checks other components of the request such as C{Content-Type} and C
    {Content-Length} headers and the C{query} argument.

    @param queries: A list of tuples with two elements each. The first one is
        a query and the second one is a list of L{TagPathAndValue}.
    """
    def __init__(self, queryItems):
        self.queryItems = queryItems

    def getQueries(self):
        """
        Get the list of queries.

        @return: a list of C{unicode} queries.
        """
        return [item[0] for item in self.queryItems]

    def getTagsAndValues(self, index):
        """
        Get a list of tags and values for a given query.

        @param index: The number (index) of the query in the list.
        @return: A list of L{TagPathAndValue}.
        """
        return self.queryItems[index][1]

    @classmethod
    def createFromRequest(cls, request, usage):
        """
        Construct the objects from an HTTP request and a usage.

        @param request: The request object.
        @param usage: The L{Usage} object.
        @return: a L{ValuesQuerySchema} object for the given request.
        """
        payload = registry.checkRequest(usage, request)

        contentType = request.getHeader('content-type')
        if contentType is None:
            raise error.NoContentTypeHeader()

        try:
            contentTypeParts = parse_mime_type(contentType)
        except ValueError:
            raise error.UnknownContentType()

        if contentTypeParts[:2] != ('application', 'json'):
            raise error.UnknownContentType()

        if queryArg in request.args:
            try:
                # Decode to unicode from the UTF-8 in the URI.
                query = request.args[queryArg][0].decode('utf-8')
            except UnicodeDecodeError:
                raise error.InvalidUTF8Argument(queryArg)
        else:
            query = None

        payloadDict = cls._getPayloadDict(payload)

        if query is None:
            queryItems = cls._parseNewPayloadDict(payloadDict)
        else:
            tagsAndValues = cls._parseOldPayloadDict(payloadDict)
            queryItems = [(query, tagsAndValues)]

        return ValuesQuerySchema(queryItems)

    @classmethod
    def _getPayloadDict(cls, payload):
        """
        Check that the payload is a valid JSON object.

        @param payload: The C{unicode} payload.
        @return: A C{dict} representing the JSON payload.
        """
        if payload is None:
            raise error.MissingPayload()
        payloadDict = payloads.parseJSONPayload(payload)
        if not isinstance(payloadDict, dict):
            raise error.MalformedPayload('Payload was not a JSON object.')
        return payloadDict

    @classmethod
    def _parseNewPayloadDict(cls, payloadDict):
        """
        Get a dictionary containing the queries and tag/value pairs in the
        payload.

        @param payloadDict: The payload C{dict} representing the queries and
            tag/value pairs.
        @return: a list of tuples with two elements each. The first one is a
            query and the second one is a list of L{TagPathAndValue}.
        """
        # Check the JSON query/tag/value specification to make sure all values
        # are primitive types we know how to handle.
        # TODO: we could use a JSON schema library to facilitate this.
        try:
            queries = payloadDict['queries']
        except KeyError:
            raise error.MalformedPayload(
                'Payload dictionary does not have a "queries" key.')

        if not isinstance(queries, list):
            raise error.MalformedPayload('Value for "queries" is not a list.')

        resultQueries = []
        for queryAndTags in queries:
            if not isinstance(queryAndTags, list):
                raise error.MalformedPayload(
                    'Query item is not a list.')

            if len(queryAndTags) != 2:
                raise error.MalformedPayload(
                    'Wrong length of the query item list.')

            query = queryAndTags[0]
            if not isinstance(query, unicode):
                raise error.MalformedPayload('Queries must be strings.')

            tagsAndValues = queryAndTags[1]
            if not isinstance(queryAndTags[1], dict):
                raise error.MalformedPayload(
                    'Tag/value data was not a JSON object.')

            tagsAndValues = cls._parseOldPayloadDict(tagsAndValues)

            resultQueries.append((query, tagsAndValues))

        return resultQueries

    @classmethod
    def _parseOldPayloadDict(cls, tagValueDict):
        """
        Get a list of Tag/Value pairs from a given payload dictionary.

        @param tagValueDict: A payload C{dict} representing the tag/value
            pairs.
        @return: A list of L{TagPathAndValue} objects.
        """

        # tagsAndValues is what we'll pass to the facade to
        # indicate what values to put on the objects that match the query.
        tagsAndValues = []

        # Check the JSON tag/value specification to make sure all values
        # are primitive types we know how to handle.
        # FIXME: we could use a JSON schema library to facilitate this.
        for tag in tagValueDict:
            try:
                value = tagValueDict[tag][valueKey]
            except TypeError:
                # requestTagValueDict[tag] is not a dict.
                raise error.InvalidPayloadField(tag)
            except KeyError:
                # valueKey not present in requestTagValueDict[tag].
                raise error.PayloadFieldMissing(valueKey)

            valueType = type(value)
            if valueType in (bool, int, float, unicode, types.NoneType):
                # This is a valid primitive type. Nothing to do.
                tvalue = createThriftValue(value)
            elif valueType is list:
                # Make sure we have a list of strings.
                strlist = []
                for s in value:
                    if isinstance(s, unicode):
                        s = s.encode('utf-8')
                    elif not isinstance(s, str):
                        raise error.UnsupportedJSONType()
                    strlist.append(s)
                tvalue = createThriftValue(strlist)
            else:
                raise error.UnsupportedJSONType()

            tagsAndValues.append(TagPathAndValue(tag, tvalue))
        return tagsAndValues


class ValuesResource(WSFEResource):

    allowedMethods = ('GET', 'PUT', 'DELETE', 'OPTIONS')
    isLeaf = True

    @defer.inlineCallbacks
    def deferred_render_GET(self, request):
        """
        Handle a GET request for /values with a query and a list
        of wanted tags.

        @param request: The incoming C{twisted.web.server.Request} request.
        @return: A C{Deferred} which will fire with the body of the
            response.  The deferred may errback for a variety of reasons,
            for example an invalid query, the mention of a non-existent tag
            or a tag that the caller does not have READ permission for.
        """
        usage = registry.findUsage(httpValueCategoryName, 'GET',
                                   ValuesResource)
        registry.checkRequest(usage, request)
        responseType = usage.getResponsePayloadTypeFromAcceptHeader(request)
        query = request.args[queryArg][0]
        tags = request.args[tagArg]
        # FIXME An HTTP 500 will occur if a user passes '*' with some other
        # tags, like 'tag=foo&tag=*'. -jkakar
        if tags == ['*']:
            tags = None
        body = yield self.facadeClient.getValuesForQuery(
            self.session, query, tags)
        request.setHeader('Content-length', str(len(body)))
        request.setHeader('Content-type', responseType)
        request.setResponseCode(usage.successCode)
        defer.returnValue(body)

    @defer.inlineCallbacks
    def deferred_render_PUT(self, request):
        """
        Update values of a set of tags (values and tags are given in a JSON
        payload) on objects that match a query (query is given in the URI).

        @param request: The incoming C{twisted.web.server.Request} request.
        @return: A L{Deferred} which will fire with C{None} when the
            request has completed.  The deferred may errback for a variety of
            reasons, for example an invalid query, the mention of a
            non-existent tag or a tag that the caller does not have CREATE
            permission for.
        """
        usage = registry.findUsage(httpValueCategoryName, 'PUT',
                                   ValuesResource)
        requestObject = ValuesQuerySchema.createFromRequest(request, usage)
        yield self.facadeClient.updateValuesForQueries(
            self.session, requestObject)
        request.setResponseCode(usage.successCode)
        defer.returnValue(None)

    @defer.inlineCallbacks
    def deferred_render_DELETE(self, request):
        """
        Handle a DELETE request for /values with a query and a list of
        wanted tags.

        @param request: The incoming C{twisted.web.server.Request} request.
        @return: A C{Deferred} which will fire when the request has
            completed.  The deferred may errback for a variety of reasons,
            for example an invalid query, the mention of a non-existent tag
            or a tag that the caller does not have DELETE permission for.
        """
        usage = registry.findUsage(httpValueCategoryName, 'DELETE',
                                   ValuesResource)
        registry.checkRequest(usage, request)
        query = request.args[queryArg][0]
        tags = request.args[tagArg]
        if tags == ['*']:
            tags = None
        yield self.facadeClient.deleteValuesForQuery(self.session, query, tags)
        request.setResponseCode(usage.successCode)
        defer.returnValue(None)


# ------------------------------ Values GET -----------------------------
topLevel = HTTPTopLevel(httpValueCategoryName, 'GET')

topLevel.description = """The GET method on values is used to retrieve
    tag values from objects matching a query."""

# We could here mention
# href="http://doc.fluidinfo.com/fluidDB/api/draft-values-spec.html">
# /values draft spec</a>.

registry.register(topLevel)


# --- GET /values --------------------------------------------------------

usage = HTTPUsage(
    '', """Search for objects matching a Fluidinfo query, and return the
           value of the requested tags on the matching objects.""")
usage.resourceClass = ValuesResource
topLevel.addUsage(usage)

usage.addArgument(Argument(
    queryArg,
    '''A query string specifying what objects to match. The
       Fluidinfo query language is described
       <a href="http://doc.fluidinfo.com/fluidDB/queries.html">here</a>.''',
    'string',
    None,
    mandatory=True))

usage.addArgument(Argument(
    tagArg,
    '''The name of a tag whose value should be returned. Repeat this
    argument as many times as needed. All values are returned if '*' is
    specified.''',
    'string',
    None,
    mandatory=True))

usage.addReturn(Return(apiDoc.BAD_REQUEST, 'If no query or tag is given.'))

usage.addReturn(Return(
    apiDoc.BAD_REQUEST,
    'If the query string could not be parsed.'))

# TODO: fix the following description. How large is too large?
usage.addReturn(Return(
    apiDoc.REQUEST_ENTITY_TOO_LARGE,
    """If the query (or any of its sub-parts) results in too many
    matching objects. The current limit is 1 million objects."""))

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the requesting user does not have ' + apiDoc.READ +
    ' permission on a tag whose value is needed to satisfy the query.'))

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the requesting user does not have ' +
    apiDoc.READ + ' permission on a tag whose value is requested.'))

apiDoc.addCannotRespondWithPayload(usage)

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'No error occurred.'))

responsePayload = JSONPayload()
responsePayload.addField(PayloadField(
    resultsKey,
    dict,
    # TODO: describe this better, point to as-implemented version of
    # the original spec/draft.
    '''A dictionary containing information about the requested tag values
    on objects that match the query. See example below.'''))

usage.addResponsePayload(responsePayload)

# TODO: put a real query into the URI.
request = ('GET /%(toplevel)s?%(query)s=mike%%2Frating>5&'
           '%(tag)s=ntoll/rating&%(tag)s=ntoll/resume&%(tag)s=fluiddb/about'
           '&%(tag)s=bit.ly/url HTTP/1.1'
           '\nAuthorization: Basic XXXXXXXX' % {
               'toplevel': httpValueCategoryName,
               'query': queryArg,
               'tag': tagArg})
response = '''HTTP/1.1 200 OK
Content-Length: 817
Date: Mon, 02 Aug 2010 13:14:32 GMT
Content-Type: application/json

{
    "%s" : {
        "id" : {
            "05eee31e-fbd1-43cc-9500-0469707a9bc3" : {
                "fluiddb/about" : {
                    "value" : "Hey you",
                    "updated-at" : "2012-02-13T18:15:24.571150"
                },
                "ntoll/rating" : {
                    "value" : 5,
                    "updated-at" : "2012-02-13T18:16:57.942384"
                },
                "ntoll/resume" : {
                    "value-type" : "application/pdf",
                    "size" : 179393,
                    "updated-at" : "2012-02-13T18:15:24.571150"
                }
            },
            "0521e31e-fbd1-43cc-9500-046974569bc3" : {
                "fluiddb/about" : {
                    "value" : "http://www.yahoo.com",
                    "updated-at" : "2012-02-13T18:15:24.571150",
                },
                "ntoll/rating" : {
                    "value" : 9,
                    "updated-at" : "2012-02-13T18:16:57.942384"
                },
                "bit.ly/url" : {
                    "value" : "http://bit.ly/4bYAV2",
                    "updated-at" : "2012-02-13T18:15:24.571150"
                }
            }
        }
    }
}
''' % resultsKey

description = '''
Search for objects in Fluidinfo matching mike/rating > 5 and retrieve values
for the tags <span class="tag">ntoll/rating</span>,
<span class="tag">ntoll/resume</span>, <span class="tag">fluiddb/about</span>,
and <span class="tag">bit.ly/url</span> from those objects.'''

usage.addExample(HTTPExample(request, response, description))


# ------------------------------ Values PUT -----------------------------
topLevel = HTTPTopLevel(httpValueCategoryName, 'PUT')

topLevel.description = """The PUT method on values sets tag values
    on objects matching queries.  Unknown namespaces and tags are created
    automatically."""

registry.register(topLevel)

# --- PUT /values -----------------------------------------------------

usage = HTTPUsage(
    '', """Search for objects matching a series of Fluidinfo queries, and set
    the values of the given tags on the matching objects.""")
usage.resourceClass = ValuesResource
usage.successCode = http.NO_CONTENT
usage.unformattedPayloadPermitted = True
topLevel.addUsage(usage)

usage.addReturn(Return(apiDoc.BAD_REQUEST, """If the payload specifying
queries and tag values cannot be parsed."""))

# TODO: fix the following description. How large is too large?
usage.addReturn(Return(
    apiDoc.REQUEST_ENTITY_TOO_LARGE,
    """If a query (or any of its sub-parts) results in too many
    matching objects. The current limit is 1 million objects."""))

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the requesting user does not have ' + apiDoc.READ +
    ' permission on a tag whose value is needed to satisfy a query.'))

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the requesting user does not have ' +
    apiDoc.CREATE + ' permission on a tag whose update is requested.'))

usage.addReturn(Return(
    apiDoc.NOT_FOUND,
    'If a tag whose update is requested does not exist.'))

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'No error occurred.'))

request = r'''PUT /%(toplevel)s HTTP/1.1
Authorization: Basic XXXXXXXX
Content-type: application/json
Content-length: 587

{
    "queries" : [
        [ "mike/rating > 5",
          {
              "ntoll/rating" : {
                  "value" : 6
              },
              "ntoll/seen" : {
                  "value" : true
              }
          }
        ],
        [ "fluiddb/about matches \"great\"",
          {
              "ntoll/rating" : {
                  "value" : 10
              }
          }
        ],
        [ "fluiddb/id = \"6ed3e622-a6a6-4a7e-bb18-9d3440678851\"",
          {
              "mike/seen" : {
                  "value" : true
              }
          }
        ]
    ]
}
''' % {
    'toplevel': httpValueCategoryName,
}

response = '''HTTP/1.1 204 No Content
Content-Type: text/html
Date: Mon, 02 Aug 2010 13:14:32 GMT
'''

description = ''' The following example request will put the given values
of <span class="tag">ntoll/rating</span> and <span
class="tag">ntoll/seen</span> onto all objects matching the Fluidinfo query
mike/rating > 5, then put the given value of <span
class="tag">ntoll/rating</span> onto objects matching the query
fluiddb/about matches "great", and finally update the <span
class="tag">mike/seen</span> tag on the object with ID <span
class="obj">6ed3e622-a6a6-4a7e-bb18-9d3440678851</span>.'''

usage.addExample(HTTPExample(request, response, description))


# ------------------------------ Values DELETE --------------------------
topLevel = HTTPTopLevel(httpValueCategoryName, 'DELETE')

topLevel.description = """The DELETE method on values is used to delete
    tags from objects matching a query."""

registry.register(topLevel)

# --- DELETE /values -----------------------------------------------------

usage = HTTPUsage(
    '', """Search for objects matching a Fluidinfo query, and delete the
           the requested tags from the matching objects.""")
usage.resourceClass = ValuesResource
usage.successCode = http.NO_CONTENT
topLevel.addUsage(usage)

usage.addArgument(Argument(
    queryArg,
    '''A query string specifying what objects to match. The
       Fluidinfo query language is described
       <a href="http://doc.fluidinfo.com/fluidDB/queries.html">here</a>.''',
    'string',
    None,
    mandatory=True))

usage.addArgument(Argument(
    tagArg,
    '''The name of a tag that should be deleted from objects matching
    the query. Repeat this argument as many times as needed. All values are
    returned if '*' is specified.''',
    'string',
    None,
    mandatory=True))

usage.addReturn(Return(apiDoc.BAD_REQUEST, 'If no query or tag is given.'))

usage.addReturn(Return(
    apiDoc.BAD_REQUEST,
    'If the query string could not be parsed.'))

# TODO: fix the following description. How large is too large?
usage.addReturn(Return(
    apiDoc.REQUEST_ENTITY_TOO_LARGE,
    """If the query (or any of its sub-parts) results in too many
    matching objects. The current limit is 1 million objects."""))

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the requesting user does not have ' + apiDoc.READ +
    ' permission on a tag whose value is needed to satisfy the query.'))

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the requesting user does not have ' +
    apiDoc.DELETE + ' permission on a tag whose deletion is requested.'))

usage.addReturn(Return(
    apiDoc.NOT_FOUND,
    'If a tag whose deletion is requested does not exist.'))

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'No error occurred.'))

request = ('DELETE /%(toplevel)s?%(query)s=mike%%2Frating>5&'
           '%(tag)s=ntoll/rating&%(tag)s=ntoll/resume HTTP/1.1'
           '\nAuthorization: Basic XXXXXXXX' % {
               'toplevel': httpValueCategoryName,
               'query': queryArg,
               'tag': tagArg})

response = '''HTTP/1.1 204 No Content
Content-Type: text/html
Date: Mon, 02 Aug 2010 13:14:32 GMT
'''

description = '''
Search for objects in Fluidinfo matching mike/rating > 5 and delete
the tags <span class="tag">ntoll/rating</span> and
<span class="tag">ntoll/resume</span> from those objects.'''

usage.addExample(HTTPExample(request, response, description))
