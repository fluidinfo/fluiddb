import urllib
import types

from twisted.web import http
from twisted.internet import defer
# from twisted.python import log

from fluiddb.common import error, defaults
from fluiddb.common import paths
from fluiddb.web import util, payloads, mimeparse
from fluiddb.web.query import (
    guessValue, createThriftValue, createBinaryThriftValue)
from fluiddb.web.resource import (
    WSFEResource, ErrorResource)
from fluiddb.doc.api.http import apiDoc
from fluiddb.doc.api.http.registry import (
    registry, HTTPTopLevel, HTTPUsage, JSONPayload, PayloadField, Return,
    HTTPExample)
from fluiddb.common.defaults import (
    sep, httpAboutCategoryName, httpObjectCategoryName,
    contentTypeForPrimitiveJSON, contentTypesForPrimitiveValue)
from fluiddb.common.types_thrift.ttypes import (
    TInternalError, ThriftValueType)

_tagPathsArg = 'tagPaths'
_aboutPath = sep.join(paths.aboutPath())


class AboutTagInstanceResource(WSFEResource):
    """
    I am a resource that can handle requests dealing with the values of
    tags on object that have been specified by an about value in the
    request URI. E.g., a request for /about/barcelona/ntoll/rating will
    wind up here.
    """

    allowedMethods = ('GET', 'HEAD', 'PUT', 'DELETE', 'OPTIONS')
    isLeaf = True

    def __init__(self, facadeClient, session, about, path):
        """
        A resource that allows callers to act on tag values on an object
        that has been specified by the C{about} value in the request URI.

        @param facadeClient: a client for talking to the facade service.
        @param session: a L{AuthenticatedSession} instance.
        @param about: A UTF-8 about value.
        @param path: The path to a tag.
        """
        # Can't use super: old-style twisted.web.resource.Resource ancestor.
        WSFEResource.__init__(self, facadeClient, session)
        self.about = about
        self.path = path

    def _setObjectId(self):
        """
        All request methods for this resource need to fetch the object id
        of the object whose fluiddb/about value was given in the URI. This
        helper function does that by sending a query to the facade. It
        returns a Deferred that fires when the request to the facade has
        returned. The Deferred returns None if the object was found (in
        which case its id is set in self.objectId) or fires a NoSuchObject
        error if there is no object with the given about value.

        Note: we need to escape any double quotes in the about value so
        that the query parser doesn't raise a syntax error.  See
        https://bugs.edge.launchpad.net/fluiddb/+bug/802783

        @return: A C{Deferred} that fires with C{None} once the object id
                 for the object with an about value of self.about has been
                 found, or which errbacks with L{NoSuchObject} if there is
                 no such object.
        """
        def finish(objectIds):
            if objectIds:
                self.objectId = objectIds.pop()
            else:
                raise error.NoSuchObject()
        query = '%s = "%s"' % (_aboutPath, self.about.replace('"', r'\"'))
        d = self.facadeClient.resolveQuery(self.session, query)
        return d.addCallback(finish)

    @defer.inlineCallbacks
    def _GET_HEAD_common(self, request, verb):
        """
        I handle the common actions taken by GET and HEAD requests, which
        are virtually identical, except HEAD drops the body.

        This code, apart from the yield self._setObjectId(), is taken
        verbatim from _GET_HEAD_common in objects.py. So if you change this
        code, you'll likely need to change that, and vice versa.

        @param request: The HTTP request.
        @param verb: A C{str}, either 'GET' or 'HEAD'.

        @return: A C{Deferred} which fires with the body of a GET request,
                 having set all the response headers that are common to GET
                 and HEAD.  (The body will be dropped (below) for HEAD
                 requests.)
        """
        usage = registry.findUsage(httpAboutCategoryName, verb,
                                   AboutTagInstanceResource)

        registry.checkRequest(usage, request)
        yield self._setObjectId()

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
        """
        Perform a GET request, and return a Deferred that fires with the
        tag value when the request has been serviced.

        @param request: The HTTP request.

        @return: A C{Deferred} that fires with the body of the response
                 once the request has completed.
        """
        return self._GET_HEAD_common(request, 'GET')

    def deferred_render_HEAD(self, request):
        """
        Perform a HEAD request, and return a Deferred that fires when the
        request has been serviced.

        Note that a HEAD response contains everything a GET does, except
        the payload. I.e., content-type and content-length headers are
        sent. That's part of the point of HEAD. To achieve this, we just do
        what a GET does, and the callback drops the response body (i.e.,
        the tag value).

        @param request: The HTTP request.

        @return: A C{Deferred} that fires with C{''} (the body of a HEAD
                 response is always empty) once the request has completed.
        """
        d = self._GET_HEAD_common(request, 'HEAD')
        d.addCallback(lambda _: '')
        return d

    @defer.inlineCallbacks
    def deferred_render_PUT(self, request):
        """
        PUT a tag value onto an object. Return a Deferred that fires with
        None when the tag value has been set by the facade.

        This code, apart from the yield self._setObjectId(), is taken
        verbatim from deferred_render_PUT in objects.py. So if you change
        this code, you'll likely need to change that, and vice versa.

        @param request: The HTTP request.

        @return: A C{Deferred} that fires with C{None} once the request has
                 completed.
        """
        usage = registry.findUsage(httpAboutCategoryName, 'PUT',
                                   AboutTagInstanceResource)
        payload = registry.checkRequest(usage, request)
        contentType = request.getHeader('content-type')

        if contentType is None:
            if payload is None:
                contentType = contentTypeForPrimitiveJSON
            else:
                raise error.NoContentTypeHeader()
        else:
            contentType = contentType.lower()

        if contentType == contentTypeForPrimitiveJSON:
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

        try:
            yield self._setObjectId()
        except error.NoSuchObject:
            # There is no object with this about value. So we create it.
            # This is consistent with /objects, which doesn't require an
            # object id to have been returned from createObject in order
            # for people to PUT tag values onto it.
            self.objectId = yield self.facadeClient.createObject(
                session=self.session, about=self.about)

        yield self.facadeClient.setTagInstance(
            self.session, self.path, self.objectId, tvalue)
        request.setResponseCode(usage.successCode)
        defer.returnValue(None)

    @defer.inlineCallbacks
    def deferred_render_DELETE(self, request):
        """
        Delete a tag from an object. Return a Deferred that fires with None
        once the facade has done the deletion.

        The following code, apart from the yield self._setObjectId(), is
        taken verbatim from deferred_render_DELETE in objects.py. So if
        you change this code, you'll likely need to change that, and vice
        versa.

        @param request: The HTTP request.

        @return: A C{Deferred} that fires with C{None} once the request has
                 completed.
        """
        usage = registry.findUsage(httpAboutCategoryName, 'DELETE',
                                   AboutTagInstanceResource)
        registry.checkRequest(usage, request)
        yield self._setObjectId()
        yield self.facadeClient.deleteTagInstance(
            self.session, self.path, self.objectId)
        request.setResponseCode(usage.successCode)
        defer.returnValue(None)


class AboutObjectResource(WSFEResource):
    """
    I am a resource that concerns a particular FluidDB object, as specified
    by an about value in a request URI.
    """

    allowedMethods = ('GET', 'OPTIONS', 'POST')

    def __init__(self, facadeClient, session, about):
        """
        Initialize and store the about value found in the URI.

        @param facadeClient: a client to talk to the facade service.
        @param session: a L{AuthenticatedSession} instance.
        @param about: A UTF-8 about value.
        """
        # Can't use super: old-style twisted.web.resource.Resource ancestor.
        WSFEResource.__init__(self, facadeClient, session)
        self.about = about  # UTF-8

    def getChild(self, name, request):
        """
        Return an L{AboutTagInstanceResource} instance initialized with the
        about value we were given and the rest of the URI path converted
        into a tag path.

        @param request: The HTTP request.

        @return: An L{AboutTagInstanceResource} instance or C{self} if we
                 are absorbing an empty URI path component.
        """
        if name == '':
            return self
        else:
            return AboutTagInstanceResource(
                self.facadeClient, self.session, self.about,
                sep.join([name] + request.postpath))

    @defer.inlineCallbacks
    def deferred_render_POST(self, request):
        """
        Create an object whose about value is the one given in the URI
        and return information about its object id and location.

        @param request: The HTTP request.

        @return: A C{Deferred} that fires with the body of the response.
        """
        usage = registry.findUsage(httpAboutCategoryName, 'POST',
                                   AboutObjectResource)
        registry.checkRequest(usage, request)
        responseType = usage.getResponsePayloadTypeFromAcceptHeader(request)

        objectId = yield self.facadeClient.createObject(
            session=self.session, about=self.about)

        if request.isSecure():
            proto = "https"
        else:
            proto = "http"
        hostname = request.getRequestHostname()

        # Return the location of the new object by its id.
        location = '%s://%s/%s/%s' % (
            proto, hostname, httpObjectCategoryName,
            urllib.quote(objectId.encode('utf-8')))

        responseDict = {
            'id': objectId,
            'URI': location,
        }

        registry.checkResponse(responseType, responseDict, usage, request)
        body = payloads.buildPayload(responseType, responseDict)
        request.setHeader('Content-length', str(len(body)))
        request.setHeader('Content-type', responseType)
        request.setHeader('Location', location)
        request.setResponseCode(usage.successCode)
        defer.returnValue(body)

    @defer.inlineCallbacks
    def deferred_render_GET(self, request):
        """
        Return information about the object whose about value is given in the
        URI.

        @param request: The HTTP request.
        @return: A C{Deferred} that fires with the body of the response.
        """
        usage = registry.findUsage(httpAboutCategoryName, 'GET',
                                   AboutObjectResource)
        registry.checkRequest(usage, request)
        responseType = usage.getResponsePayloadTypeFromAcceptHeader(request)

        # Note: we need to escape any double quotes in the about value so
        # that the query parser doesn't raise a syntax error.  See
        # https://bugs.edge.launchpad.net/fluiddb/+bug/802783
        query = '%s = "%s"' % (_aboutPath, self.about.replace('"', r'\"'))
        objectIds = yield self.facadeClient.resolveQuery(self.session, query)
        if objectIds:
            objectId = objectIds.pop()
        else:
            raise error.NoSuchObject()
        objectInfo = yield self.facadeClient.getObject(
            self.session, objectId, showAbout=False)
        responseDict = {
            _tagPathsArg: objectInfo.tagPaths,
            'id': objectId,
        }
        registry.checkResponse(responseType, responseDict, usage, request)
        body = payloads.buildPayload(responseType, responseDict)
        request.setHeader('Content-length', str(len(body)))
        request.setHeader('Content-type', responseType)
        request.setResponseCode(usage.successCode)
        defer.returnValue(body)


class AboutResource(WSFEResource):
    """
    I am the top level of the /about URI hierarchy. I don't do anything
    except check for errors and hand out AboutObjectResource resources.
    """

    def getChild(self, about, request):
        """
        Create a child AboutObjectResource resource for this C{about} value
        after Verifying the about value is valid UTF-8.

        @param about: The %-encoded UTF-8 about value, specifying an object.
        @param request: The HTTP request.

        @return: an L{AboutObjectResource} instance initialized with the
                 C{about} value.
        """
        if about == '':
            # If a request has an empty component, absorb it.
            return self
        else:
            try:
                # Make sure we have valid UTF-8 in the about value.
                about.decode('utf-8')
            except UnicodeDecodeError:
                return ErrorResource(
                    http.BAD_REQUEST, error.BadArgument,
                    {'Error-Message': 'About value in URI was not UTF-8'})
            else:
                return AboutObjectResource(
                    self.facadeClient, self.session, about)


# ------------------------------ About POST -----------------------------
topLevel = HTTPTopLevel(httpAboutCategoryName, 'POST')
topLevel.description = "Create a new object."
registry.register(topLevel)

# --- POST /about -------------------------------------------------------

usage = HTTPUsage('/' + apiDoc.ABOUTSTR, ('''Create a new object with the
    given about value. If there is already a Fluidinfo object whose
    ''' + apiDoc.ABOUT_TAG + ''' tag has the given value, the returned
    object id will be that of the pre-existing object. In this call, and
    all others with an about value in the URI, you must convert
    your about value to UTF-8 and then
    <a href="http://en.wikipedia.org/wiki/Percent-encoding">
    percent-encode</a> it before adding it to the request URI. You must
    provide valid credentials for this call to succeed.
    For an example see the PUT request, below.'''))

topLevel.addUsage(usage)
usage.resourceClass = AboutObjectResource
usage.successCode = http.CREATED

usage.addReturn(Return(
    apiDoc.BAD_REQUEST,
    'The ' + apiDoc.ABOUTSTR + ' argument was not valid UTF-8.'))

apiDoc.addBadRequestPayload(usage)

apiDoc.addCannotRespondWithPayload(usage)

usage.addReturn(Return(apiDoc.UNAUTHORIZED,
                       'If valid credentials are not provided.'))

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'A new object was created without error.'))

responsePayload = JSONPayload()
responsePayload.addField(PayloadField(
    'id', unicode,
    'The id of the new object.'))
responsePayload.addField(PayloadField(
    'URI', unicode,
    'The URI of the new object.'))
usage.addResponsePayload(responsePayload)

request = """POST /about/chewing-gum HTTP/1.1
Authorization: Basic XXXXXXXX
Content-Type: application/json"""

response = '''HTTP/1.1 201 Created
Content-Length: 134
Location: http://fluiddb.fluidinfo.com/%(about)s/chewing-gum
Date: Mon, 02 Aug 2010 13:00:29 GMT
Content-Type: application/json

{"id": "9c8e4b12-4b7d-40d2-865b-d5b1945350b1",
"URI": "http://fluiddb.fluidinfo.com/%(about)s/chewing-gum"}''' % {
    'about': httpAboutCategoryName}
description = "Create an object with an about tag of 'chewing-gum'."
usage.addExample(HTTPExample(request, response, description))


# ------------------------------ About GET -----------------------------
topLevel = HTTPTopLevel(httpAboutCategoryName, 'GET')
topLevel.description = (
    """The GET method for /""" + httpAboutCategoryName + """ retrieves
    information about the Fluidinfo object (if any) with a particular """ +
    apiDoc.ABOUT_TAG + """ value, or retrieves the value of a tag on the
    object with a given about tag value.""")
registry.register(topLevel)

# --- GET /about/aboutstr -------------------------------------------------

usage = HTTPUsage(
    '/' + apiDoc.ABOUTSTR,
    """To request information on the object whose """ + apiDoc.ABOUT_TAG +
    """ tag is """ + apiDoc.ABOUTSTR +
    """, specify the about value in the request URI.""")
usage.resourceClass = AboutObjectResource
topLevel.addUsage(usage)

usage.addReturn(Return(
    apiDoc.BAD_REQUEST,
    'The ' + apiDoc.ABOUTSTR + ' argument was not valid UTF-8.'))

usage.addReturn(Return(
    apiDoc.NOT_FOUND,
    'No object with the given about value exists.'))

apiDoc.addCannotRespondWithPayload(usage)

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'No error occurred.'))

# TODO: perhaps also show things like the date the object was created, last
# changed, etc.?

responsePayload = JSONPayload()
responsePayload.addField(PayloadField(
    'id', unicode,
    'The id of the object.'))

responsePayload.addField(PayloadField(
    _tagPathsArg, list,
    """The full path names of the tags on this object (for which
    the user has """ + apiDoc.READ + ' permission), if any.',
    listType=unicode))

usage.addResponsePayload(responsePayload)

request = """GET /about/Barcelona HTTP/1.1
Authorization: Basic XXXXXXXX"""
response = '''HTTP/1.1 200 OK
Content-Length: 1080
Date: Mon, 02 Aug 2010 13:16:09 GMT
Content-Type: application/json

{"tagPaths": ["esteve/opinion", "terrycojones/favorite-cities"]}'''
description = ("""Retrieve information about the Fluidinfo object whose """ +
               apiDoc.ABOUT_TAG + """ value is 'Barcelona'.""")
usage.addExample(HTTPExample(request, response, description))


# --- GET /about/aboutstr/NAMESPACE1/NAMESPACE2/TAG ---------------------

usage = HTTPUsage(
    apiDoc.ABOUTSTR_NS_NS_TAG,
    '''Retrieve the value of a tag from the object (if any) whose ''' +
    apiDoc.ABOUT_TAG + ''' is ''' + apiDoc.ABOUTSTR +
    '''.  The value is returned in the payload of the response.
     Please see
    <a href="http://doc.fluidinfo.com/fluidDB/api/'''
    '''http.html#payloads-containing-tag-values">here</a>
    for more details.''')
usage.resourceClass = AboutTagInstanceResource
topLevel.addUsage(usage)

usage.addReturn(Return(
    apiDoc.BAD_REQUEST,
    'The ' + apiDoc.ABOUTSTR + ' argument was not valid UTF-8.'))

usage.addReturn(Return(
    apiDoc.NOT_FOUND,
    'No object with the given about value exists.'))

usage.addReturn(Return(apiDoc.NOT_FOUND,
                       'If the object has no instance of the tag, or if the '
                       'tag or a parent namespace does not exist.'))

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the user does not have ' + apiDoc.READ + ' permission on the tag.'))

apiDoc.addCannotRespondWithPayload(usage)

usage.addReturn(Return(
    apiDoc.NOT_ACCEPTABLE,
    'If you do not specify an ' + apiDoc.ACCEPT + """ header value that
    allows the tag value to be returned."""))

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'If the object has an instance of the tag and the requesting user has ' +
    apiDoc.READ + ' permission for the tag.'))

request = """GET /about/London/geo/latitude HTTP/1.1
Authorization: Basic XXXXXXXX"""
response = """HTTP/1.1 200 OK
Content-Length: 4
Date: Mon, 02 Aug 2010 13:20:31 GMT
Content-Type: """ + defaults.contentTypeForPrimitiveJSON + """

51.5
"""
description = ("""Return a primitive value type from Fluidinfo. Note that the
                  Content-Type header in the response is """ +
               defaults.contentTypeForPrimitiveJSON +
               " as given to Fluidinfo when the value was originally PUT.")
usage.addExample(HTTPExample(request, response, description))

request = """GET /about/Barcelona/lonelyplanet.com/outline HTTP/1.1
Authorization: Basic XXXXXXXX"""
response = """HTTP/1.1 200 OK
Content-Length: 6666
Date: Mon, 02 Aug 2010 13:25:28 GMT
Content-Type: application/pdf

%PDF-1.4
1 0 obj
<< /Length 2 0 R
/Filter /FlateDecode
>>
stream
...
"""
description = """Return an opaque value type from Fluidinfo. Note that the
Content-Type header in the response is application/pdf, because the tag value
is of that type, as given to Fluidinfo when the value was originally PUT."""

usage.addExample(HTTPExample(request, response, description))


# ------------------------------ About HEAD ----------------------------
topLevel = HTTPTopLevel(httpAboutCategoryName, 'HEAD')

topLevel.description = """The HEAD method on about can be used to test
    whether an object has a given tag or not, without retrieving the value of
    the tag."""

registry.register(topLevel)

# --- HEAD /about/aboutstr/NAMESPACE1/NAMESPACE2/TAG ---------------------

usage = HTTPUsage(
    apiDoc.ABOUTSTR_NS_NS_TAG,
    """Test for the existence of a tag on the object (if any)
    whose """ + apiDoc.ABOUT_TAG + ''' is ''' + apiDoc.ABOUTSTR + '.')
usage.resourceClass = AboutTagInstanceResource

topLevel.addUsage(usage)

usage.addReturn(Return(
    apiDoc.BAD_REQUEST,
    'The ' + apiDoc.ABOUTSTR + ' argument was not valid UTF-8.'))

usage.addReturn(Return(
    apiDoc.NOT_FOUND,
    'No object with the given about value exists.'))

usage.addReturn(Return(apiDoc.NOT_FOUND,
                       'If the object has no instance of the tag, or if the '
                       'tag or a parent namespace does not exist.'))

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the user does not have ' + apiDoc.READ + ' permission on the tag.'))

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'The object has an instance of the tag.'))

request = """HEAD /about/Barcelona/ntoll/review HTTP/1.1
Authorization: Basic XXXXXXXX"""
response = """HTTP/1.1 200 OK
Content-Length: 31288
Date: Mon, 02 Aug 2010 13:26:25 GMT
Content-Type: text/html"""
description = """Retrieve information about a tag attached to a
specific object."""
usage.addExample(HTTPExample(request, response, description))


# ------------------------------ About PUT ------------------------------
topLevel = HTTPTopLevel(httpAboutCategoryName, 'PUT')
topLevel.description = 'Create or update a tag on an object.'
registry.register(topLevel)

# --- PUT /about/aboutstr/NAMESPACE1/NAMESPACE2/TAG ---------------------

usage = HTTPUsage(
    apiDoc.ABOUTSTR_NS_NS_TAG,
    ("""Create or update a tag on the object whose """ +
     apiDoc.ABOUT_TAG + ''' is ''' + apiDoc.ABOUTSTR +
     """. If no object with """ +
     apiDoc.ABOUT_TAG + ''' = ''' + apiDoc.ABOUTSTR +
     ''' exists, it will be created. The tag value is sent in
     the payload of the request. See <a
     href="http://doc.fluidinfo.com/fluidDB/api/''' +
     '''http.html#payloads-containing-tag-values">here</a>
    for more details.'''))

usage.resourceClass = AboutTagInstanceResource
usage.successCode = http.NO_CONTENT
usage.unformattedPayloadPermitted = True
topLevel.addUsage(usage)

usage.addReturn(Return(
    apiDoc.BAD_REQUEST,
    'The ' + apiDoc.ABOUTSTR + ' argument was not valid UTF-8.'))

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the user does not have ' + apiDoc.CREATE + ' permission on the tag.'))

apiDoc.addBadRequestPayload(usage)

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'If the tag is successfully created / updated on the object.'))

request = ("""PUT /about/%E5%8F%B0%E5%8C%97/ntoll/cities/visited HTTP/1.1
Authorization: Basic XXXXXXXX
Content-Length: XXXXXXXX
Content-Type: """ + defaults.contentTypeForPrimitiveJSON + """

true
""")
response = """HTTP/1.1 204 No Content
Date: Mon, 02 Aug 2010 14:31:47 GMT
Content-Type: text/html"""
description = ("""Write a primitive value (in this case 'true') to the
               Fluidinfo object whose """ + apiDoc.ABOUT_TAG +
               """ value is &#21488;&#21271; (Taipei).
               &#21488;&#21271; are the two unicode codepoints U+53F0 and
               U+5317, each of which is a 3-byte sequence in UTF-8
               (0xE5 0x8F 0xB0 and 0xE5 0x8C 0x97 respectively).
               Note the Content-Type header in the request is set to """ +
               defaults.contentTypeForPrimitiveJSON +
               """ to indicate to Fluidinfo that this is a primitive value.""")
usage.addExample(HTTPExample(request, response, description))

request = """PUT /about/Barcelona/lonelyplanet.com/outline HTTP/1.1
Authorization: Basic XXXXXXXX
Content-Length: XXXXXXXX
Content-Type: application/pdf

%PDF-1.4
1 0 obj
<< /Length 2 0 R
/Filter /FlateDecode
>>
stream
..."""

response = """HTTP/1.1 204 No Content
Date: Mon, 02 Aug 2010 14:33:40 GMT
Content-Type: text/html"""
description = """Write an opaque value type to Fluidinfo. Note that the
                 Content-Type header in the request is set to application/pdf
                 indicating to Fluidinfo that this value is opaque. When this
                 value is retrieved the Content-Type header in the response
                 will be application/pdf. (The body of the request has been
                 truncated.)"""
usage.addExample(HTTPExample(request, response, description))

# ------------------------------ About DELETE ---------------------------
topLevel = HTTPTopLevel(httpAboutCategoryName, 'DELETE')
topLevel.description = ('''
    Delete a tag from an object. Note that
    <a href="http://doc.fluidinfo.com/fluidDB/
    objects.html#objects-are-never-deleted">
    it is not possible to delete a Fluidinfo object</a>.''')


registry.register(topLevel)

# --- DELETE /about/aboutstr/NAMESPACE1/NAMESPACE2/TAG ------------------

usage = HTTPUsage(apiDoc.ABOUTSTR_NS_NS_TAG, 'Delete a tag from an object.')
usage.resourceClass = AboutTagInstanceResource
usage.successCode = http.NO_CONTENT
topLevel.addUsage(usage)

apiDoc.addMissingIntermediateNs(usage)

apiDoc.addNoSuchTag(usage)

usage.addReturn(Return(
    apiDoc.BAD_REQUEST,
    'The ' + apiDoc.ABOUTSTR + ' argument was not valid UTF-8.'))

usage.addReturn(Return(
    apiDoc.NOT_FOUND,
    'No object with the given about value exists.'))

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the user does not have ' + apiDoc.DELETE + ' permission on the tag.'))

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'The tag is successfully deleted from the object.'))

request = """DELETE /about/Barcelona/ntoll/rating HTTP/1.1
Authorization: Basic XXXXXXXX"""
response = """HTTP/1.1 204 No Content
Date: Mon, 02 Aug 2010 14:56:52 GMT
Content-Type: text/html"""
description = "Delete the ntoll/rating tag from the object about Barcelona."
usage.addExample(HTTPExample(request, response, description))
