import urllib

from twisted.web import http
# from twisted.python import log
from twisted.internet import defer

from fluiddb.common import paths
from fluiddb.web import util, payloads
from fluiddb.web.resource import WSFEResource
from fluiddb.doc.api.http import apiDoc
from fluiddb.doc.api.http.registry import (
    registry, HTTPTopLevel, HTTPUsage, JSONPayload, PayloadField, Argument,
    Note, Return, HTTPExample)
from fluiddb.common.defaults import sep, httpNamespaceCategoryName

returnNamespacesArg = 'returnNamespaces'
returnTagsArg = 'returnTags'
returnDescriptionArg = 'returnDescription'


class NamespacesResource(WSFEResource):

    allowedMethods = ('POST', 'GET', 'PUT', 'DELETE', 'OPTIONS')
    isLeaf = True

    @defer.inlineCallbacks
    def deferred_render_POST(self, request):
        usage = registry.findUsage(httpNamespaceCategoryName, 'POST',
                                   NamespacesResource)
        dictionary = registry.checkRequest(usage, request)
        responseType = usage.getResponsePayloadTypeFromAcceptHeader(request)

        parentNamespace = sep.join(request.postpath)
        name = dictionary['name']
        description = dictionary['description'] or ''

        path = sep.join([parentNamespace, name.encode('utf-8')])

        objectId = yield self.facadeClient.createNamespace(
            session=self.session,
            parentNamespace=parentNamespace,
            name=name.encode('utf-8'),
            description=description.encode('utf-8'))

        if request.isSecure():
            proto = "https"
        else:
            proto = "http"
        hostname = request.getRequestHostname()

        location = '%s://%s/%s/%s' % (
            proto, hostname, httpNamespaceCategoryName,
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
        usage = registry.findUsage(httpNamespaceCategoryName, 'GET',
                                   NamespacesResource)
        registry.checkRequest(usage, request)
        responseType = usage.getResponsePayloadTypeFromAcceptHeader(request)
        args = {
            returnNamespacesArg: util.getBooleanArg(
                request, returnNamespacesArg,
                usage.arguments[returnNamespacesArg].default),
            returnTagsArg: util.getBooleanArg(
                request, returnTagsArg,
                usage.arguments[returnTagsArg].default),
            returnDescriptionArg: util.getBooleanArg(
                request, returnDescriptionArg,
                usage.arguments[returnDescriptionArg].default),
        }

        tnamespace = yield self.facadeClient.getNamespace(
            self.session,
            sep.join(request.postpath),
            returnDescription=args[returnDescriptionArg],
            returnNamespaces=args[returnNamespacesArg],
            returnTags=args[returnTagsArg])

        responseDict = {
            'id': tnamespace.objectId,
        }
        if args[returnNamespacesArg]:
            responseDict['namespaceNames'] = tnamespace.namespaces
        if args[returnTagsArg]:
            responseDict['tagNames'] = tnamespace.tags
        if args[returnDescriptionArg]:
            responseDict['description'] = tnamespace.description

        registry.checkResponse(responseType, responseDict, usage, request)
        body = payloads.buildPayload(responseType, responseDict)
        request.setHeader('Content-length', str(len(body)))
        request.setHeader('Content-type', responseType)
        request.setResponseCode(usage.successCode)
        defer.returnValue(body)

    @defer.inlineCallbacks
    def deferred_render_PUT(self, request):
        usage = registry.findUsage(httpNamespaceCategoryName, 'PUT',
                                   NamespacesResource)
        dictionary = registry.checkRequest(usage, request)
        description = dictionary.get('description') or ''

        yield self.facadeClient.updateNamespace(self.session,
                                                sep.join(request.postpath),
                                                description.encode('utf-8'))

        request.setResponseCode(usage.successCode)

    @defer.inlineCallbacks
    def deferred_render_DELETE(self, request):
        usage = registry.findUsage(httpNamespaceCategoryName, 'DELETE',
                                   NamespacesResource)
        registry.checkRequest(usage, request)
        yield self.facadeClient.deleteNamespace(self.session,
                                                sep.join(request.postpath))
        request.setResponseCode(usage.successCode)


# ------------------------------ Namespaces POST --------------------------
topLevel = HTTPTopLevel(httpNamespaceCategoryName, 'POST')
registry.register(topLevel)


# --- POST /namespaces/NAMESPACE1/NAMESPACE2 ------------------------------

usage = HTTPUsage(apiDoc.NS_NS, 'Create a new namespace.  Intermediate '
                  "namespaces are created automatically if they don't already "
                  'exist.')
topLevel.addUsage(usage)
usage.resourceClass = NamespacesResource
usage.successCode = http.CREATED

usage.addNote(Note("""The new namespace will have permissions set
according to the user's defaults. There is no permission inheritance
in Fluidinfo."""))

usage.addReturn(Return(
    apiDoc.PRECONDITION_FAILED,
    'If the namespace already exists.'))

usage.addReturn(Return(
    apiDoc.NOT_FOUND,
    "If a parent namespace does not exist and you do not have permission to "
    'create it.'))

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the requesting user does not have ' + apiDoc.CREATE +
    ' permission on the parent namespace.'))

usage.addReturn(Return(
    apiDoc.BAD_REQUEST,
    'If the full path of the new namespace is too long.' +
    ' The current maximum path length is ' +
    str(paths.maxPathLength) + ' characters.'))

apiDoc.addBadRequestPayload(usage)

apiDoc.addCannotRespondWithPayload(usage)

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'If the namespace is created successfully.'))

requestPayload = JSONPayload()
requestPayload.addField(PayloadField(
    'name', unicode,
    'The name of the new namespace.'))
requestPayload.addField(PayloadField(
    'description', unicode, 'A description of the namespace.', mayBeNone=True))
usage.addRequestPayload(requestPayload)

responsePayload = JSONPayload()
responsePayload.addField(PayloadField(
    'id', unicode,
    'The id of the object that corresponds to the new namespace.'))
responsePayload.addField(PayloadField(
    'URI', unicode,
    'The URI of the new namespace.'))
usage.addResponsePayload(responsePayload)

request = '''POST /namespaces/test HTTP/1.1
Authorization: Basic XXXXXXXX
Content-Length: XXXXXXXX
Content-Type: application/json

{
 "description": "A namespace for tags that I\'m using to add to people",
 "name": "people"
}'''
response = '''HTTP/1.1 201 Created
Content-Length: 110
Location: http://fluiddb.fluidinfo.com/namespaces/test/people
Date: Mon, 02 Aug 2010 12:40:41 GMT
Content-Type: application/json

{"id": "e9c97fa8-05ed-4905-9f72-8d00b7390f9b",
 "URI": "http://fluiddb.fluidinfo.com/namespaces/test/people"}'''
description = """Create a new namespace called 'people' in the test user's
top-level namespace."""
usage.addExample(HTTPExample(request, response, description))


# ------------------------------ Namespaces GET ---------------------------
topLevel = HTTPTopLevel(httpNamespaceCategoryName, 'GET')
registry.register(topLevel)


# --- GET /namespaces/NAMESPACE1/NAMESPACE2 -------------------------------

usage = HTTPUsage(
    apiDoc.NS_NS,
    'Get information about the namespaces contained in a  namespace.')
topLevel.addUsage(usage)
usage.resourceClass = NamespacesResource
usage.successCode = http.OK

usage.addArgument(Argument(
    'match',
    """A string to match namespace names against. Only matching namespaces
       will be returned.""",
    'string',
    implemented=False))

usage.addArgument(Argument(
    'matchBy',
    """What to match on - must be either 'name' or 'description'.""",
    'string',
    implemented=False))

usage.addArgument(Argument(
    returnNamespacesArg,
    """If True, also return the names of the namespaces in this namespace.""",
    'Boolean',
    False))

usage.addArgument(Argument(
    returnTagsArg,
    """If True, also return the names of the tags in this namespace.""",
    'Boolean',
    False))

usage.addArgument(Argument(
    returnDescriptionArg,
    """If True, also return the namespace description.""",
    'Boolean',
    False))

usage.addArgument(Argument(
    'maxDepth',
    """If set to a non-negative value, the depth to which to descend into
       sub-namespaces.""",
    'int',
    -1,
    implemented=False))

usage.addArgument(Argument(
    'sortBy',
    """How to sort the returned names. One of 'name', 'description',
       'creationDate'.""",
    'string',
    implemented=False))

usage.addArgument(Argument(
    'order',
    """The order in which to sort. Either 'ascending' or 'descending'.""",
    'string',
    implemented=False))


responsePayload = JSONPayload()
responsePayload.addField(PayloadField(
    'id',
    unicode,
    'The id of the Fluidinfo object corresponding to the namespace.'))

responsePayload.addField(PayloadField(
    'description',
    unicode,
    'A description of the namespace. This field is only present if ' +
    apiDoc.spanWrap('var', returnDescriptionArg) +
    ' is True in the request.',
    mandatory=False,
    mayBeNone=True))

responsePayload.addField(PayloadField(
    'namespaceNames',
    list,
    'The names of the sub-namespaces in this namespace. ' +
    'This field is only present if ' +
    apiDoc.spanWrap('var', returnNamespacesArg) +
    ' is True in the request.',
    mandatory=False,
    listType=unicode))

responsePayload.addField(PayloadField(
    'tagNames', list,
    'The names of the tags in this namespace (only present if ' +
    apiDoc.spanWrap('var', returnTagsArg) +
    ' is True in the request).',
    mandatory=False,
    listType=unicode))

usage.addResponsePayload(responsePayload)


apiDoc.addNoSuchNs(usage)

apiDoc.addMissingIntermediateNs(usage)

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the requesting user does not have ' + apiDoc.LIST +
    ' permission on the namespace.'))

apiDoc.addCannotRespondWithPayload(usage)

apiDoc.addOkOtherwise(usage)

request = ('''GET /namespaces/test/people?returnDescription=True'''
           '''&returnNamespaces=True&returnTags=True HTTP/1.1
            Authorization: Basic XXXXXXXX''')

response = '''HTTP/1.1 200 OK
Content-Length: 118
Date: Mon, 02 Aug 2010 12:43:05 GMT
Content-Type: application/json

{"tagNames": [], "namespaceNames": [], '''
'''"id": "e9c97fa8-05ed-4905-9f72-8d00b7390f9b",
"description": "A namespace for tags I\'m using to add to people"}'''
description = "Retrieve information about the test/people namespace."
usage.addExample(HTTPExample(request, response, description))


# ------------------------------ Namespaces PUT ---------------------------
topLevel = HTTPTopLevel(httpNamespaceCategoryName, 'PUT')
registry.register(topLevel)


# --- PUT /namespaces/NAMESPACE1/NAMESPACE2 -------------------------------

usage = HTTPUsage(apiDoc.NS_NS, 'Update a namespace.')
topLevel.addUsage(usage)
usage.resourceClass = NamespacesResource
usage.successCode = http.NO_CONTENT

apiDoc.addNoSuchNs(usage)

apiDoc.addMissingIntermediateNs(usage)

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the requesting user does not have ' + apiDoc.UPDATE +
    ' permission on the namespace.'))

apiDoc.addBadRequestPayload(usage)

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'If the namespace is updated successfully.'))

requestPayload = JSONPayload()
requestPayload.addField(PayloadField(
    'description', unicode, 'A description of the namespace.', mayBeNone=True))
usage.addRequestPayload(requestPayload)

request = '''PUT /namespaces/test/people HTTP/1.1
Authorization: Basic XXXXXXXX
Content-Length: XXXXXXXX
Content-Type: application/json

{
  "description": "Contains tags used to annotate objects representing people"
}'''
response = '''HTTP/1.1 204 No Content
Date: Mon, 02 Aug 2010 12:46:38 GMT
Content-Type: text/html'''
description = "Update the description of the test/people namespace."
usage.addExample(HTTPExample(request, response, description))


# ------------------------------ Namespaces DELETE ------------------------
topLevel = HTTPTopLevel(httpNamespaceCategoryName, 'DELETE')
registry.register(topLevel)


# --- DELETE /namespaces/NAMESPACE1/NAMESPACE2 ----------------------------

usage = HTTPUsage(apiDoc.NS_NS, 'Delete a namespace.')
topLevel.addUsage(usage)
usage.resourceClass = NamespacesResource
usage.successCode = http.NO_CONTENT

usage.addNote(Note("""A namespace can only be deleted if it is empty.
I.e., it must not contain any sub-namespaces or any tags."""))

apiDoc.addNoSuchNs(usage)

apiDoc.addMissingIntermediateNs(usage)

usage.addReturn(Return(
    apiDoc.UNAUTHORIZED,
    'If the requesting user does not have ' + apiDoc.DELETE +
    ' permission on the namespace.'))

usage.addReturn(Return(
    apiDoc.PRECONDITION_FAILED,
    """If the namespace is not empty. A namespace is empty if it contains no
other namespaces or tags."""))

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'If the namespace is deleted successfully.'))

request = '''DELETE /namespaces/test/people HTTP/1.1
Authorization: Basic XXXXXXXX'''
response = '''HTTP/1.1 204 No Content
Date: Mon, 02 Aug 2010 12:47:25 GMT
Content-Type: text/html'''
description = "Delete the test/people namespace."
usage.addExample(HTTPExample(request, response, description))
