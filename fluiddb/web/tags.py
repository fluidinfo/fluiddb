import urllib

from twisted.web import http
from twisted.internet import defer

from fluiddb.web import util, payloads
from fluiddb.web.resource import WSFEResource
from fluiddb.doc.api.http import apiDoc
from fluiddb.doc.api.http.registry import (
    registry, HTTPTopLevel, HTTPUsage, JSONPayload, PayloadField, Argument,
    Note, Return, HTTPExample)
from fluiddb.common.defaults import sep, httpTagCategoryName
from fluiddb.common.types_thrift.ttypes import TagRangeType
from fluiddb.common import paths

returnDescriptionArg = 'returnDescription'


class TagsResource(WSFEResource):

    allowedMethods = ('POST', 'GET', 'PUT', 'DELETE', 'OPTIONS')
    isLeaf = True

    @defer.inlineCallbacks
    def deferred_render_POST(self, request):
        usage = registry.findUsage(httpTagCategoryName, 'POST', TagsResource)
        dictionary = registry.checkRequest(usage, request)
        responseType = usage.getResponsePayloadTypeFromAcceptHeader(request)

        parentNamespace = sep.join(request.postpath)
        name = dictionary['name']
        description = dictionary['description'] or ''
        indexed = dictionary['indexed']

        path = sep.join([parentNamespace, name.encode('utf-8')])

        objectId = yield self.facadeClient.createTag(
            session=self.session,
            parentNamespace=parentNamespace,
            name=name.encode('utf-8'),
            description=description.encode('utf-8'),
            indexed=indexed,
            # Always request a normal range. We don't let apps do anything
            # else yet.
            rangeType=TagRangeType.NORMAL_TYPE)

        if request.isSecure():
            proto = "https"
        else:
            proto = "http"
        hostname = request.getRequestHostname()

        location = '%s://%s/%s/%s' % (
            proto, hostname, httpTagCategoryName,
            urllib.quote(path))

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
        # TODO: usages should be cached locally; lookup is expensive.
        usage = registry.findUsage(httpTagCategoryName, 'GET', TagsResource)
        registry.checkRequest(usage, request)
        responseType = usage.getResponsePayloadTypeFromAcceptHeader(request)
        args = {
            returnDescriptionArg: util.getBooleanArg(
                request, returnDescriptionArg,
                usage.arguments[returnDescriptionArg].default),
        }

        ttag = yield self.facadeClient.getTag(
            self.session,
            sep.join(request.postpath),
            returnDescription=args[returnDescriptionArg])

        responseDict = {
            'id': ttag.objectId,
            'indexed': ttag.indexed,
        }
        if args[returnDescriptionArg]:
            responseDict['description'] = ttag.description

        registry.checkResponse(responseType, responseDict, usage, request)
        body = payloads.buildPayload(responseType, responseDict)
        request.setHeader('Content-length', str(len(body)))
        request.setHeader('Content-type', responseType)
        request.setResponseCode(usage.successCode)
        defer.returnValue(body)

    @defer.inlineCallbacks
    def deferred_render_PUT(self, request):
        usage = registry.findUsage(httpTagCategoryName, 'PUT', TagsResource)
        dictionary = registry.checkRequest(usage, request)

        description = dictionary.get('description') or ''

        yield self.facadeClient.updateTag(self.session,
                                          sep.join(request.postpath),
                                          description.encode('utf-8'))
        request.setResponseCode(usage.successCode)

    @defer.inlineCallbacks
    def deferred_render_DELETE(self, request):
        usage = registry.findUsage(httpTagCategoryName, 'DELETE', TagsResource)
        registry.checkRequest(usage, request)
        yield self.facadeClient.deleteTag(self.session,
                                          sep.join(request.postpath))
        request.setResponseCode(usage.successCode)


# ------------------------------ Tags POST --------------------------
topLevel = HTTPTopLevel(httpTagCategoryName, 'POST')
registry.register(topLevel)


# --- POST /tags/NAMESPACE1/NAMESPACE2 ------------------------

usage = HTTPUsage(apiDoc.NS_NS,
                  'Add a tag name to a namespace.  Intermediate namespaces '
                  "are created automatically if they don't already exist.")
topLevel.addUsage(usage)
usage.resourceClass = TagsResource
usage.successCode = http.CREATED

requestPayload = JSONPayload()
requestPayload.addField(PayloadField(
    'name', unicode, 'The name of the new tag.'))
requestPayload.addField(PayloadField(
    'description', unicode, 'A description of the tag.', mayBeNone=True))
requestPayload.addField(PayloadField(
    'indexed', bool, 'Whether or not tag values should be indexed.'))

usage.addRequestPayload(requestPayload)

responsePayload = JSONPayload()
responsePayload.addField(PayloadField(
    'id', unicode, 'The id of the object that corresponds to the new tag.'))
responsePayload.addField(PayloadField(
    'URI', unicode, 'The URI of the new object.'))
usage.addResponsePayload(responsePayload)

usage.addReturn(Return(
    apiDoc.NOT_FOUND,
    'If the containing namespace or an intermediate namespace '
    "does not exist and you do not have permission to create it."))

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the user does not have ' + apiDoc.CREATE +
    ' permission on the containing (i.e., deepest) namespace.'))

usage.addReturn(Return(
    apiDoc.PRECONDITION_FAILED,
    "If the tag already exists."))

usage.addReturn(Return(
    apiDoc.BAD_REQUEST,
    'If the full path of the new tag is too long.' +
    ' The current maximum path length is ' +
    str(paths.maxPathLength) + ' characters.'))

apiDoc.addBadRequestPayload(usage)

apiDoc.addCannotRespondWithPayload(usage)

usage.addReturn(Return(apiDoc.CREATED, "If the tag is created successfully."))

usage.addNote(Note(
    'A ' + apiDoc.LOCATION +
    ' header will be returned containing the URI of the new tag.'))

usage.addNote(Note(
    """This method creates a tag itself, <em>not</em>
    the value of a tag on a particular object (for that, use POST on """ +
    apiDoc.URI_OBJECTS_ID_NS_NS_TAG + ")."))

request = '''POST /tags/test HTTP/1.1
Authorization: Basic XXXXXXXX
Content-Length: XXXXXXXX
Content-Type: application/json

{
  "description": "How I rate things on a scale of 1 (worst) to 10 (best).",
  "indexed": false,
  "name": "rating"
}'''
response = '''HTTP/1.1 201 Created
Content-Length: 110
Location: http://fluiddb.fluidinfo.com/tags/test/rating
Date: Mon, 02 Aug 2010 15:15:00 GMT
Content-Type: application/json

{"id": "56e0c31a-1a4c-4091-8a65-b37af769752a",
"URI": "http://fluiddb.fluidinfo.com/tags/test/rating"}'''
description = """Create a new tag called 'rating' in the test
users top-level namespace."""
usage.addExample(HTTPExample(request, response, description))


# ------------------------------ Tags GET ---------------------------
topLevel = HTTPTopLevel(httpTagCategoryName, 'GET')
registry.register(topLevel)


# --- GET /tags/NAMESPACE1/NAMESPACE2/TAG ---------------------

usage = HTTPUsage(
    apiDoc.NS_NS_TAG,
    'Retrieve information about the tag.')
topLevel.addUsage(usage)
usage.resourceClass = TagsResource

usage.addArgument(Argument(
    returnDescriptionArg,
    'If True, return the description of the tag.',
    'Boolean',
    False))

apiDoc.addMissingIntermediateNs(usage)

apiDoc.addNoSuchTag(usage)

apiDoc.addCannotRespondWithPayload(usage)

apiDoc.addOkOtherwise(usage)

usage.addNote(Note(
    """This method retrieves information about the
    tag itself, <em>not</em> the value of a tag on an object
    (to get the value on an object, use GET on """ +
    apiDoc.URI_OBJECTS_ID_NS_NS_TAG + ")."))

responsePayload = JSONPayload()

responsePayload.addField(PayloadField(
    'id',
    unicode,
    'The id of the Fluidinfo object corresponding to the tag.'))

responsePayload.addField(PayloadField(
    'description', unicode,
    'A description of the tag. This field is only present if ' +
    apiDoc.spanWrap('var', returnDescriptionArg) +
    ' is True in the request.',
    mandatory=False,
    mayBeNone=True))

responsePayload.addField(PayloadField(
    'indexed', bool, 'Whether or not tag values are indexed.'))

usage.addResponsePayload(responsePayload)

request = """GET /tags/test/rating?returnDescription=True HTTP/1.1
Authorization: Basic XXXXXXXX"""
response = '''HTTP/1.1 200 OK
Content-Length: 108
Date: Mon, 02 Aug 2010 15:15:59 GMT
Content-Type: application/json

{"indexed": false, "id": "56e0c31a-1a4c-4091-8a65-b37af769752a",
"description": "How I rate things on a scale of 1 (worst) to 10 (best)."}'''
description = "Retrieve information about the test/rating tag."
usage.addExample(HTTPExample(request, response, description))

# ------------------------------ Tags PUT ---------------------------
topLevel = HTTPTopLevel(httpTagCategoryName, 'PUT')
registry.register(topLevel)


# --- PUT /tags/NAMESPACE1/NAMESPACE2/TAG --------------------

usage = HTTPUsage(
    apiDoc.NS_NS_TAG,
    'Update information about a tag in a namespace.')
topLevel.addUsage(usage)
usage.resourceClass = TagsResource
usage.successCode = http.NO_CONTENT

apiDoc.addMissingIntermediateNs(usage)

apiDoc.addNoSuchTag(usage)

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the requesting user does not have ' + apiDoc.UPDATE +
    ' permission on the tag.'))

apiDoc.addBadRequestPayload(usage)

usage.addReturn(Return(
    apiDoc.NO_CONTENT,
    'If the operation completes successfully.'))

requestPayload = JSONPayload()
requestPayload.addField(PayloadField(
    'description', unicode,
    'A description of the tag.',
    mayBeNone=True))

usage.addRequestPayload(requestPayload)

usage.addNote(Note("""Changing whether a tag is indexed after it
has been created is not currently supported."""))

request = '''PUT /tags/test/rating HTTP/1.1
Authorization: Basic XXXXXXXX
Content-Length: XXXXXXXX
Content-Type: application/json

{
  "description": "Indicates rating from 1 (bad) -> 10 (good)"
}'''
response = """HTTP/1.1 204 No Content
Date: Mon, 02 Aug 2010 15:16:59 GMT
Content-Type: text/html"""
description = "Update the description of the test/rating tag."
usage.addExample(HTTPExample(request, response, description))

# ------------------------------ Tags DELETE ------------------------
topLevel = HTTPTopLevel(httpTagCategoryName, 'DELETE')
registry.register(topLevel)


# --- DELETE /tags/NAMESPACE1/NAMESPACE2/TAG ------------------

usage = HTTPUsage(apiDoc.NS_NS_TAG, """Delete a tag. The tag name is
removed from its containing namespace and all occurences of the tag
on objects are deleted.""")
topLevel.addUsage(usage)
usage.resourceClass = TagsResource
usage.successCode = http.NO_CONTENT

apiDoc.addMissingIntermediateNs(usage)

apiDoc.addNoSuchTag(usage)

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the requesting user does not have ' + apiDoc.DELETE +
    ' permission on the tag.'))

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'If the operation completes successfully.'))

request = """DELETE /tags/test/rating HTTP/1.1
Authorization: Basic XXXXXXXX"""
response = """HTTP/1.1 204 No Content
Date: Mon, 02 Aug 2010 15:17:38 GMT
Content-Type: text/html"""
description = "Delete the test/rating tag."
usage.addExample(HTTPExample(request, response, description))
