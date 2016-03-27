import urllib
import types
import uuid

from twisted.web import http
from twisted.internet import defer

from fluiddb.common import error
from fluiddb.web import util, payloads, mimeparse
from fluiddb.web.query import (
    guessValue, createThriftValue, createBinaryThriftValue)
from fluiddb.web.resource import (
    WSFEResource, NoResource)
from fluiddb.doc.api.http import apiDoc
from fluiddb.doc.api.http.registry import (
    registry, HTTPTopLevel, HTTPUsage, JSONPayload, PayloadField, Argument,
    Note, Return, HTTPExample)
from fluiddb.common.defaults import (
    sep, httpObjectCategoryName, contentTypeForPrimitiveJSON,
    contentTypesForPrimitiveValue)
from fluiddb.common.types_thrift.ttypes import (
    TInternalError, ThriftValueType)

pathArg = 'path'
tagPathsArg = 'tagPaths'
showAboutArg = 'showAbout'
aboutArg = 'about'


class TagInstanceResource(WSFEResource):

    allowedMethods = ('GET', 'HEAD', 'PUT', 'DELETE', 'OPTIONS')
    isLeaf = True

    def __init__(self, facadeClient, session, objectId, path):
        # Can't use super: old-style twisted.web.resource.Resource ancestor.
        WSFEResource.__init__(self, facadeClient, session)
        self.objectId = objectId
        self.path = path

    @defer.inlineCallbacks
    def _GET_HEAD_common(self, request, verb):
        """
        The following code is reproduced almost verbatim in
        deferred_render_DELETE in about.py. So if you change this code,
        you'll likely need to change that, and vice versa.
        """
        usage = registry.findUsage(httpObjectCategoryName, verb,
                                   TagInstanceResource)

        registry.checkRequest(usage, request)

        # This will raise TNoInstanceOnObject if there's no instance,
        # and that will return a 404 (see util.py).
        tvalue, tagValue = yield self.facadeClient.getTagInstance(
            self.session, self.path, self.objectId)
        value = guessValue(tvalue)
        accept = request.getHeader('accept') or '*/*'

        if tvalue.valueType == ThriftValueType.BINARY_TYPE:
            contentType = tvalue.binaryKeyMimeType
            if mimeparse.best_match([contentType], accept) == '':
                raise error.NotAcceptable()
            body = value
            # Mark this value as unwrappable for JSON
            request._fluiddb_jsonp_unwrappable = None
        else:
            contentType = mimeparse.best_match(
                contentTypesForPrimitiveValue, accept)
            if contentType == '':
                raise error.NotAcceptable()
            try:
                serializer = util.primitiveTypeSerializer[contentType]
            except KeyError:
                raise TInternalError('No serializer for %r.' % contentType)
            else:
                body = serializer(value)

            typeValue = self._getTypeHeader(tvalue.valueType)
            request.setHeader(util.buildHeader('Type'), typeValue)

        request.setHeader('Content-length', str(len(body)))
        request.setHeader('Content-type', contentType)
        # setting the Last-Modified header for fluiddb/id makes no sense
        if tagValue and tagValue.creationTime:
            request.setHeader(
                'Last-modified',
                tagValue.creationTime.strftime('%a, %d %b %Y %H:%M:%S'))
        request.setResponseCode(usage.successCode)
        defer.returnValue(body)

    def deferred_render_GET(self, request):
        return self._GET_HEAD_common(request, 'GET')

    def deferred_render_HEAD(self, request):
        """
        Note that a HEAD response contains everything a GET does, except
        the payload. I.e., content-type and content-length headers are
        sent. That's part of the point of HEAD.
        """
        d = self._GET_HEAD_common(request, 'HEAD')
        d.addCallback(lambda _: '')
        return d

    @defer.inlineCallbacks
    def deferred_render_PUT(self, request):
        """
        The following code is reproduced almost verbatim in
        deferred_render_PUT in about.py. So if you change this code,
        you'll likely need to change that, and vice versa.
        """
        usage = registry.findUsage(httpObjectCategoryName, 'PUT',
                                   TagInstanceResource)
        payload = registry.checkRequest(usage, request)
        contentType = request.getHeader('content-type')

        if contentType is None:
            if payload is None:
                contentTypeFirstComponent = contentTypeForPrimitiveJSON
            else:
                raise error.NoContentTypeHeader()
        else:
            # Get the lowercased first component of the content type, as
            # split by semicolon (the HTTP standard for separating the
            # content type from other tags, such as charset).
            #
            # Doing it this way allows us to ignore any other crud in the
            # content-type, for example a charset, when the content type is
            # our own contentTypeForPrimitiveJSON. See
            # https://oodl.es/trac/fluiddb/ticket/572 and the
            # testPrimitiveTypesWithCharsetAlsoInContentType test in
            # integration/wsfe/test_tagValues.py for more details
            #
            # We only need to rstrip the first component of the content
            # type as twisted.web does a strip on the whole header value
            # (so the left side is already stripped).
            contentTypeFirstComponent = \
                contentType.split(';')[0].lower().rstrip()

        if contentTypeFirstComponent == contentTypeForPrimitiveJSON:
            if payload is None:
                value = None
            else:
                value = payloads.parseJSONPayload(payload)
            tv = type(value)
            if tv in (bool, int, float, unicode, types.NoneType):
                tvalue = createThriftValue(value)
            elif tv is list:
                strlist = []
                for s in value:
                    if isinstance(s, unicode):
                        s = s.encode("utf-8")
                    elif not isinstance(s, str):
                        raise error.UnsupportedJSONType()
                    strlist.append(s)
                tvalue = createThriftValue(strlist)
            else:
                raise error.UnsupportedJSONType()
        else:
            tvalue = createBinaryThriftValue(payload, contentType)

        # log.msg("PUT: tvalue is %r" % tvalue)
        yield self.facadeClient.setTagInstance(
            self.session, self.path, self.objectId, tvalue)
        request.setResponseCode(usage.successCode)
        defer.returnValue(None)

    @defer.inlineCallbacks
    def deferred_render_DELETE(self, request):
        """
        The following code is reproduced almost verbatim in
        deferred_render_DELETE in about.py. So if you change this code,
        you'll likely need to change that, and vice versa.
        """
        usage = registry.findUsage(httpObjectCategoryName, 'DELETE',
                                   TagInstanceResource)
        registry.checkRequest(usage, request)
        yield self.facadeClient.deleteTagInstance(
            self.session, self.path, self.objectId)
        request.setResponseCode(usage.successCode)
        defer.returnValue(None)


class ObjectResource(WSFEResource):

    allowedMethods = ('GET', 'OPTIONS')

    def __init__(self, facadeClient, session, objectId):
        # Can't use super: old-style twisted.web.resource.Resource ancestor.
        WSFEResource.__init__(self, facadeClient, session)
        self.objectId = objectId

    def getChild(self, name, request):
        if name == '':
            return self
        else:
            return TagInstanceResource(
                self.facadeClient, self.session, self.objectId,
                sep.join([name] + request.postpath))

    @defer.inlineCallbacks
    def deferred_render_GET(self, request):
        usage = registry.findUsage(httpObjectCategoryName, 'GET',
                                   ObjectResource)
        registry.checkRequest(usage, request)
        responseType = usage.getResponsePayloadTypeFromAcceptHeader(request)

        showAbout = util.getBooleanArg(
            request, showAboutArg,
            usage.arguments[showAboutArg].default)

        objectInfo = yield self.facadeClient.getObject(
            self.session, self.objectId, showAbout)

        responseDict = {
            tagPathsArg: objectInfo.tagPaths,
        }
        if showAbout:
            if objectInfo.about:
                responseDict[aboutArg] = objectInfo.about.decode('utf-8')
            else:
                responseDict[aboutArg] = None

        registry.checkResponse(responseType, responseDict, usage, request)
        body = payloads.buildPayload(responseType, responseDict)
        request.setHeader('Content-length', str(len(body)))
        request.setHeader('Content-type', responseType)
        request.setResponseCode(usage.successCode)
        defer.returnValue(body)


class ObjectsResource(WSFEResource):

    allowedMethods = ('POST', 'GET', 'OPTIONS')

    def getChild(self, objectId, request):
        if objectId == '':
            return self
        else:
            # Make sure we have something that looks like a UUID. If not,
            # and we're using the Postgres UUID type to hold object ids, a
            # ProgrammingError exceptions occur in the tags service and I'd
            # prefer to catch them all here rather than deal with it all
            # the way down there and pass back the appropriate thing, etc.
            #
            # Note that this test isn't mandatory if we're instead storing
            # UUIDs as strings or we're not using Postgres.
            try:
                uuid.UUID(objectId)
            except ValueError:
                return NoResource('Object id %r is not a uuid.' % objectId)
            else:
                return ObjectResource(self.facadeClient, self.session,
                                      objectId)

    @defer.inlineCallbacks
    def deferred_render_POST(self, request):
        usage = registry.findUsage(httpObjectCategoryName, 'POST',
                                   ObjectsResource)
        dictionary = registry.checkRequest(usage, request)
        responseType = usage.getResponsePayloadTypeFromAcceptHeader(request)
        about = dictionary.get(aboutArg, '')

        objectId = yield self.facadeClient.createObject(
            session=self.session, about=about.encode('utf-8'))

        if request.isSecure():
            proto = "https"
        else:
            proto = "http"
        hostname = request.getRequestHostname()

        # Return the location of the new object by its id.
        location = '%s://%s/%s/%s' % (
            proto, hostname, httpObjectCategoryName,
            # This is probably overkill
            urllib.quote(objectId.encode('utf-8')))

        responseDict = {'id': objectId, 'URI': location}
        registry.checkResponse(responseType, responseDict, usage, request)
        body = payloads.buildPayload(responseType, responseDict)
        request.setHeader('Content-length', str(len(body)))
        request.setHeader('Content-type', responseType)
        request.setHeader('Location', location)
        request.setResponseCode(usage.successCode)
        defer.returnValue(body)

    @defer.inlineCallbacks
    def deferred_render_GET(self, request):
        usage = registry.findUsage(httpObjectCategoryName, 'GET',
                                   ObjectsResource)
        registry.checkRequest(usage, request)
        responseType = usage.getResponsePayloadTypeFromAcceptHeader(request)
        query = request.args['query'][0]
        results = yield self.facadeClient.resolveQuery(self.session, query)
        responseDict = {'ids': list(results)}
        registry.checkResponse(responseType, responseDict, usage, request)
        body = payloads.buildPayload(responseType, responseDict)
        request.setHeader('Content-length', str(len(body)))
        request.setHeader('Content-type', responseType)
        request.setResponseCode(usage.successCode)
        defer.returnValue(body)


# ------------------------------ Objects POST -----------------------------
topLevel = HTTPTopLevel(httpObjectCategoryName, 'POST')
topLevel.description = "Create a new Fluidinfo object."
registry.register(topLevel)

# --- POST /objects -------------------------------------------------------

usage = HTTPUsage('', 'Create a new object. You must provide credentials for '
                      'this call to succeed.')
topLevel.addUsage(usage)
usage.resourceClass = ObjectsResource
usage.successCode = http.CREATED

apiDoc.addBadRequestPayload(usage)

apiDoc.addCannotRespondWithPayload(usage)

usage.addReturn(Return(apiDoc.UNAUTHORIZED,
                       'If valid credentials are not provided.'))

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'A new object was created without error.'))

requestPayload = JSONPayload()
requestPayload.addField(PayloadField(
    aboutArg,
    unicode,
    """The value for the %(about)s tag. If you do not want an
    an %(about)s tag on this object, omit this field.
    """ %
    {'about': apiDoc.ABOUT},
    mandatory=False))

usage.addRequestPayload(requestPayload)

responsePayload = JSONPayload()
responsePayload.addField(PayloadField(
    'id', unicode,
    'The id of the new object.'))
responsePayload.addField(PayloadField(
    'URI', unicode,
    'The URI of the new object.'))
usage.addResponsePayload(responsePayload)

usage.addNote(Note(
    'The response will also contain a ' + apiDoc.LOCATION +
    ' header giving the URI for the new object.'))

usage.addNote(Note(
    """If you pass an %(about)s value and there is already a
    Fluidinfo object whose %(about)s tag has that value, the returned object id
    will be that of the pre-existing object.""" % {'about': apiDoc.ABOUT}))

request = '''POST /objects HTTP/1.1
Authorization: Basic XXXXXXXX
Content-Length: XXXXXXXX
Content-Type: application/json

{
  "about": "book:Dune"
}'''
response = '''HTTP/1.1 201 Created
Content-Length: 134
Location: http://fluiddb.fluidinfo.com/objects/'''
'''9c8e4b12-4b7d-40d2-865b-d5b1945350b1
Date: Mon, 02 Aug 2010 13:00:29 GMT
Content-Type: application/json

{"id": "9c8e4b12-4b7d-40d2-865b-d5b1945350b1",
"URI": "http://fluiddb.fluidinfo.com/objects/'''
'''9c8e4b12-4b7d-40d2-865b-d5b1945350b1"}'''
description = """Create an object with an about tag that indicates the object
                 represents the book 'Dune'."""
usage.addExample(HTTPExample(request, response, description))

request = """POST /objects HTTP/1.1
Authorization: Basic XXXXXXXX
Content-Length: XXXXXXXX
Content-Type: application/json"""
response = '''HTTP/1.1 201 Created
Content-Length: 134
Location: http://fluiddb.fluidinfo.com/objects/'''
'''741fdbcb-a8c5-449f-a3cf-50c89ee63cdb
Date: Mon, 02 Aug 2010 13:01:05 GMT
Content-Type: application/json

{"id": "741fdbcb-a8c5-449f-a3cf-50c89ee63cdb",
"URI": "http://fluiddb.fluidinfo.com/objects/'''
'''741fdbcb-a8c5-449f-a3cf-50c89ee63cdb"}'''
description = "Create a new object without an about tag."
usage.addExample(HTTPExample(request, response, description))

# ------------------------------ Objects GET -----------------------------
topLevel = HTTPTopLevel(httpObjectCategoryName, 'GET')

topLevel.description = """
    The GET method on objects is used to retrieve objects matching a query
    (on object tags), to retrieve information about a particular object, or
    to retrieve the value of a tag on a particular object."""

registry.register(topLevel)


# --- GET /objects --------------------------------------------------------

usage = HTTPUsage('', 'Search for objects that match a query.')
usage.resourceClass = ObjectsResource
topLevel.addUsage(usage)

usage.addArgument(Argument(
    'query',
    '''A query string specifying what sorts of objects to
    return. The query language is described
    <a href="http://doc.fluidinfo.com/fluidDB/queries.html">here</a>.
    You must convert your query to UTF-8 and then
    <a href="http://en.wikipedia.org/wiki/Percent-encoding">
     percent-encode</a> it before adding it to the request URI''',
    'string',
    None,
    mandatory=True))

usage.addArgument(Argument(
    'offset',
    """From what (zero-based) offset in the result set should results
       be returned.""",
    'int',
    0,
    implemented=False))

usage.addArgument(Argument(
    'limit',
    """The maximum number of results to return. Pass -1 (or omit this
       argument) to indicate no limit.""",
    'int',
    -1,
    implemented=False))

usage.addArgument(Argument(
    'sortBy',
    'Give the name of a tag to sort the results by.',
    'string',
    implemented=False))

usage.addArgument(Argument(
    'order',
    """How to order sorted results. Must be one of 'ascending' or
       'descending'.""",
    'string',
    implemented=False))

usage.addReturn(Return(apiDoc.BAD_REQUEST, 'If no query is given.'))

usage.addReturn(Return(
    apiDoc.BAD_REQUEST,
    'The query string was not valid UTF-8.'))

usage.addReturn(Return(
    apiDoc.BAD_REQUEST,
    'If the query string could not be parsed.'))

usage.addReturn(Return(apiDoc.NOT_FOUND,
                       'If one or more of the tags or namespaces present '
                       'in the query do not exist.'))

# TODO: fix the following description. How large is too large?
usage.addReturn(Return(
    apiDoc.REQUEST_ENTITY_TOO_LARGE,
    """If the query (or any of its sub-parts) results in too many
    matching objects. The current limit is 1 million objects."""))

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the user does not have ' + apiDoc.READ +
    ' permission on a tag whose value is needed to satisfy the query.'))

apiDoc.addCannotRespondWithPayload(usage)

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'No error occurred.'))

responsePayload = JSONPayload()
responsePayload.addField(PayloadField(
    'ids', list,
    '''A list of object ids matching the query. Each object id is a UUID
    string (as described
    <a href="http://doc.fluidinfo.com/fluidDB/api/uuids.html">here</a>).''',
    listType=unicode))

usage.addResponsePayload(responsePayload)
request = """GET /objects?query=has%20ntoll/
met%20and%20has%20terrycojones/met HTTP/1.1
Authorization: Basic XXXXXXXX"""
response = '''HTTP/1.1 200 OK
Content-Length: 209
Date: Mon, 02 Aug 2010 13:14:32 GMT
Content-Type: application/json

{"ids": ["5a4823a4-26b4-495c-9a29-a1e830a1b153", '''
'''"8b07a7ec-e5f7-46cd-9cd1-9a40c3137762",
"83f2ad81-43db-421a-adc4-974f3a8bca0d", '''
'''"ac1e937e-dd76-426e-a2b5-06a439a708cc",
"52bc041d-e8f4-4f8d-a66a-a3b5ea5fa156"]}'''
description = """Search for objects in Fluidinfo (note the URL encoded
                 query argument)."""
usage.addExample(HTTPExample(request, response, description))


# --- GET /objects/ID -----------------------------------------------------

usage = HTTPUsage(
    '/' + apiDoc.ID,
    """To request information on a particular object, include the object ID
    in the request URI. The return information will indicate which tags are
    present on the object, though not with the tag values.""")
usage.resourceClass = ObjectResource

topLevel.addUsage(usage)


usage.addReturn(Return(
    apiDoc.NOT_FOUND,
    'If the given ID is not a valid UUID.'))

apiDoc.addBadRequestPayload(usage)

apiDoc.addCannotRespondWithPayload(usage)

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'No error occurred.'))

usage.addNote(Note('''An object ID has the form of a UUID, as described
    <a href="http://doc.fluidinfo.com/fluidDB/api/uuids.html">here</a>.'''))


usage.addArgument(Argument(
    showAboutArg,
    """If True, return the value of the %(about)s tag on the object. If the
    object does not have an %(about)s tag, the response payload will still
    contain an <tt>%(arg)s</tt> key, with, in the case of a JSON payload, a
    <tt>null</tt> value.  If False, the payload will not have an
    <tt>%(arg)s</tt> key.""" % {'about': apiDoc.ABOUT, 'arg': aboutArg},
    'string',
    default=False,
    mandatory=False))

# TODO: perhaps also show things like the date the object was created, last
# changed, etc.?

responsePayload = JSONPayload()
responsePayload.addField(PayloadField(
    aboutArg, unicode,
    """The %(about)s tag on the object, if any.""" %
    {'about': apiDoc.ABOUT},
    mandatory=False,
    mayBeNone=True))

responsePayload.addField(PayloadField(
    tagPathsArg, list,
    """The full path names of the tags on this object (for which
    the user has """ + apiDoc.READ + ' permission), if any.',
    listType=unicode))

usage.addResponsePayload(responsePayload)

request = ("""GET /objects/5a4823a4-26b4-495c-9a29-a1e830a1b153"""
           """?showAbout=True HTTP/1.1
Authorization: Basic XXXXXXXX""")
response = '''HTTP/1.1 200 OK
Content-Length: 1080
Date: Mon, 02 Aug 2010 13:16:09 GMT
Content-Type: application/json

{"about": "twitter.com:uid:5893972",
"tagPaths": ["twitter.com/friends/fxn"]}'''
description = """Retrieve information about a specific object
(the 'tagPaths' list in the response has been truncated)"""
usage.addExample(HTTPExample(request, response, description))


# --- GET /objects/ID/NAMESPACE1/NAMESPACE2/TAG ---------------------

usage = HTTPUsage(
    apiDoc.ID_NS_NS_TAG,
    '''Retrieve the value of a tag from an object.  The value is
    returned in the payload of the response. If the requested value is a
    primitive, an <span class="httpHeader">X-FluidDB-Type</span> header will
    be added to the response indicating the type of the value. Please see
    <a href="http://doc.fluidinfo.com/fluidDB/api/http.html'''
    '''#payloads-containing-tag-values">here</a> for more details.
    ''')
usage.resourceClass = TagInstanceResource
topLevel.addUsage(usage)

apiDoc.addCannotRespondWithPayload(usage)

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the user does not have ' + apiDoc.READ + ' permission for the tag.'))

usage.addReturn(Return(apiDoc.NOT_FOUND,
                       'If the object has no instance of the tag, or if the '
                       'tag or a parent namespace does not exist.'))

usage.addReturn(Return(
    apiDoc.NOT_ACCEPTABLE,
    'If you do not specify an ' + apiDoc.ACCEPT + """ header value that
    allows the tag value to be returned."""))

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'If the object has an instance of the tag.'))

request = """GET /objects/5a4823a4-26b4-495c-9a29-a1e830a1b153/
twitter.com/users/screen_name HTTP/1.1
Authorization: Basic XXXXXXXX"""
response = '''HTTP/1.1 200 OK
Content-Length: 6
Date: Mon, 02 Aug 2010 13:20:31 GMT
Content-Type: application/vnd.fluiddb.value+json
X-FluidDB-Type: string

"HD42"
'''
description = """Return a primitive value type from Fluidinfo.
Note that the Content-Type header in the response is
application/vnd.fluiddb.value+json, as given to Fluidinfo
when the value was PUT."""
usage.addExample(HTTPExample(request, response, description))

request = """GET /objects/366375a5-c811-4c59-a469-0a3efb602411/
ntoll/fluidapp/tweetmeet/index.html HTTP/1.1
Authorization: Basic XXXXXXXX"""
response = """HTTP/1.1 200 OK
Content-Length: 6666
Date: Mon, 02 Aug 2010 13:25:28 GMT
Content-Type: text/html

&lt;html&gt;
   &lt;head&gt;
          &lt;title&gt;Hello&lt;/title&gt;
   &lt;/head&gt;
   &lt;body&gt;
       Hello
   &lt;/body&gt;
&lt;/html&gt;"""
description = """Return an opaque value type from Fluidinfo. Note
that the Content-Type header in the response is text/html,
because the tag value is of that type, as given to Fluidinfo
when the value was PUT."""
usage.addExample(HTTPExample(request, response, description))


# ------------------------------ Objects HEAD ----------------------------
topLevel = HTTPTopLevel(httpObjectCategoryName, 'HEAD')

topLevel.description = """The HEAD method on objects can be used to test
    whether an object has a given tag or not, without retrieving the value of
    the tag."""

registry.register(topLevel)

# --- HEAD /objects/ID/NAMESPACE1/NAMESPACE2/TAG ---------------------

usage = HTTPUsage(
    apiDoc.ID_NS_NS_TAG,
    '''Test for the existence of a tag on an object. If the requested tag
    has a primitive value, an <span class="httpHeader">X-FluidDB-Type</span>
    header will be added to the response indicating the type of the value.
    Please see <a href="http://doc.fluidinfo.com/fluidDB/api/http.html'''
    '''#payloads-containing-tag-values">here</a> for more details.''')
usage.resourceClass = TagInstanceResource

topLevel.addUsage(usage)

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the user does not have ' + apiDoc.READ + ' permission for the tag.'))

usage.addReturn(Return(apiDoc.NOT_FOUND,
                       'If the object has no instance of the tag, or if the '
                       'tag or a parent namespace does not exist.'))

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'The object has an instance of the tag.'))


request = """HEAD /objects/366375a5-c811-4c59-a469-0a3efb602411/
toll/fluidapp/tweetmeet/index.html HTTP/1.1
Authorization: Basic XXXXXXXX"""
response = """HTTP/1.1 200 OK
Content-Length: 28926
Date: Mon, 02 Aug 2010 13:26:25 GMT
Content-Type: text/html"""
description = """Retrieve the headers associated with a tag attached to a
                specific object."""
usage.addExample(HTTPExample(request, response, description))


# ------------------------------ Objects PUT ------------------------------
topLevel = HTTPTopLevel(httpObjectCategoryName, 'PUT')
topLevel.description = (
    'Create or update a tag on an object.  Unknown namespaces and tags are '
    'created automatically.')
registry.register(topLevel)

# --- PUT /objects/ID/NAMESPACE1/NAMESPACE2/TAG ---------------------

usage = HTTPUsage(
    apiDoc.ID_NS_NS_TAG,
    '''Create or update a tag on an object.  The tag value is sent in the
    payload of the request. See <a
    href="http://doc.fluidinfo.com/fluidDB/api/http.html'''
    '''#payloads-containing-tag-values">here</a>
    for more details.''')

usage.resourceClass = TagInstanceResource
usage.successCode = http.NO_CONTENT
usage.unformattedPayloadPermitted = True
topLevel.addUsage(usage)

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the user does not have ' + apiDoc.CREATE + ' permission on the tag.'))

apiDoc.addBadRequestPayload(usage)

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'If the tag is successfully created / updated on the object.'))

request = '''PUT /objects/5a4823a4-26b4-495c-9a29-a1e830a1b153/
test/quz HTTP/1.1
Authorization: Basic XXXXXXXX
Content-Length: XXXXXXXX
Content-Type: application/vnd.fluiddb.value+json

"1.234"
'''
response = """HTTP/1.1 204 No Content
Date: Mon, 02 Aug 2010 14:31:47 GMT
Content-Type: text/html"""
description = """Write a primitive value type to Fluidinfo. Note the
Content-Type header in the request is set to
application/vnd.fluiddb.value+json to indicate to Fluidinfo that
this is a primitive value."""
usage.addExample(HTTPExample(request, response, description))

request = ("""PUT /objects/5a4823a4-26b4-495c-9a29-a1e830a1b153/
test/quz HTTP/1.1
Authorization: Basic XXXXXXXX
Content-Length: XXXXXXXX
Content-Type: application/pdf

%PDF-1.4
1 0 obj
<< /Length 2 0 R
/Filter /FlateDecode
>>
stream
...""")

response = """HTTP/1.1 204 No Content
Date: Mon, 02 Aug 2010 14:33:40 GMT
Content-Type: text/html"""
description = """Write an opaque value type to Fluidinfo. Note that the
Content-Type header in the request is set to application/pdf indicating
to Fluidinfo that this value is opaque. When this value is retrieved the
Content-Type header in the response will be application/pdf.
(Note: the body of the request has been truncated.)"""
usage.addExample(HTTPExample(request, response, description))

# ------------------------------ Objects DELETE ---------------------------
topLevel = HTTPTopLevel(httpObjectCategoryName, 'DELETE')
topLevel.description = ('''
Delete a tag from an object. Note that
<a href="http://doc.fluidinfo.com/fluidDB/objects.html
#objects-are-never-deleted">it is not possible to
delete a Fluidinfo object</a>.''')

registry.register(topLevel)

# --- DELETE /objects/ID/NAMESPACE1/NAMESPACE2/TAG ------------------

usage = HTTPUsage(apiDoc.ID_NS_NS_TAG, 'Delete a tag from an object.')
usage.resourceClass = TagInstanceResource
usage.successCode = http.NO_CONTENT
topLevel.addUsage(usage)

usage.addReturn(Return(
    apiDoc.NOT_FOUND,
    'If the object id is malformed.'))

apiDoc.addMissingIntermediateNs(usage)

apiDoc.addNoSuchTag(usage)

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the user does not have ' + apiDoc.DELETE + ' permission on the tag.'))

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'The tag is successfully deleted from the object.'))

usage.addNote(Note(
    'You will receive a ' + apiDoc.NO_CONTENT +
    ' status even if the object has no instance of the tag.'))

request = """DELETE /objects/5a4823a4-26b4-495c-9a29-a1e830a1b153/
test/quz HTTP/1.1
Authorization: Basic XXXXXXXX"""
response = """HTTP/1.1 204 No Content
Date: Mon, 02 Aug 2010 14:56:52 GMT
Content-Type: text/html"""
description = "Delete the test/quz tag from the referenced object."
usage.addExample(HTTPExample(request, response, description))
