from twisted.internet import defer
from twisted.web import http

from fluiddb.common import permissions
from fluiddb.web import payloads
from fluiddb.web.resource import (WSFEResource, NoResource)
from fluiddb.doc.api.http import apiDoc
from fluiddb.doc.api.http.registry import (
    registry, HTTPTopLevel, HTTPUsage, JSONPayload, PayloadField, Return,
    Argument, HTTPExample)
from fluiddb.common.defaults import (
    sep, httpPermissionCategoryName, httpNamespaceCategoryName,
    httpTagCategoryName, httpTagInstanceSetCategoryName, namespaceCategoryName,
    tagCategoryName, tagInstanceSetCategoryName)
from fluiddb.common.types_thrift.ttypes import (
    TPolicyAndExceptions)

actionArg = 'action'


class ConcretePermissionResource(WSFEResource):
    allowedMethods = ('GET', 'PUT', 'OPTIONS')
    isLeaf = True

    @defer.inlineCallbacks
    def deferred_render_GET(self, request):
        # TODO: usages should be cached locally; lookup is expensive.
        usage = registry.findUsage(httpPermissionCategoryName, 'GET',
                                   self.__class__)
        registry.checkRequest(usage, request)
        responseType = usage.getResponsePayloadTypeFromAcceptHeader(request)
        action = request.args[actionArg][0].lower()
        result = yield self.facadeClient.getPermission(
            self.session, self.category, action, sep.join(request.postpath))
        responseDict = {
            'policy': result.policy,
            'exceptions': list(result.exceptions),
        }
        registry.checkResponse(responseType, responseDict, usage, request)
        body = payloads.buildPayload(responseType, responseDict)
        request.setHeader('Content-length', str(len(body)))
        request.setHeader('Content-type', responseType)
        request.setResponseCode(usage.successCode)
        defer.returnValue(body)

    @defer.inlineCallbacks
    def deferred_render_PUT(self, request):
        # TODO: usages should be cached locally; lookup is expensive.
        usage = registry.findUsage(httpPermissionCategoryName, 'PUT',
                                   self.__class__)
        dictionary = registry.checkRequest(usage, request)
        action = request.args[actionArg][0].lower()
        policyAndExceptions = TPolicyAndExceptions(
            policy=dictionary['policy'],
            exceptions=set(dictionary['exceptions']))
        yield self.facadeClient.updatePermission(
            self.session, self.category, action, sep.join(request.postpath),
            policyAndExceptions)
        request.setResponseCode(usage.successCode)


class ConcreteNamespacePermissionResource(ConcretePermissionResource):
    category = namespaceCategoryName


class ConcreteTagPermissionResource(ConcretePermissionResource):
    category = tagCategoryName


class ConcreteTagInstancesPermissionResource(ConcretePermissionResource):
    category = tagInstanceSetCategoryName

_classForCategory = {
    namespaceCategoryName: ConcreteNamespacePermissionResource,
    tagCategoryName: ConcreteTagPermissionResource,
    tagInstanceSetCategoryName: ConcreteTagInstancesPermissionResource,
}


class PermissionsResource(WSFEResource):

    def getChild(self, name, request):
        try:
            klass = _classForCategory[name]
        except KeyError:
            return NoResource()
        else:
            return klass(self.facadeClient, self.session)


# ------------------------------ Permissions POST -------------------------
topLevel = HTTPTopLevel(httpPermissionCategoryName, 'POST')
topLevel.description = """
    POST is not supported on permissions, because permissions are
    automatically set from a user's default permissions when a namespace or
    tag is first created. Use PUT to adjust the permissions on a given
    namespace or tag.  """
    # TODO: Finish this sentence and add it to the description:
    # To change a user's defaults, do a PUT on.... what exactly?
registry.register(topLevel)


# ------------------------------ Permissions GET --------------------------
topLevel = HTTPTopLevel('permissions', 'GET')
registry.register(topLevel)


# --- GET /permissions/namespaces/NAMESPACE1/NAMESPACE2 ------------

usage = HTTPUsage(
    '/' + httpNamespaceCategoryName + apiDoc.NS_NS,
    """Get the permissions on a namespace: the open/closed policy,
    and the set of exceptions to the policy.""")
usage.resourceClass = ConcreteNamespacePermissionResource
topLevel.addUsage(usage)

possibleActions = ', '.join(permissions.actionsByCategory[
    namespaceCategoryName])

usage.addArgument(Argument(
    actionArg,
    """The action whose permissions information is
    sought. Possible values are: """ + possibleActions + '.',
    'string',
    mandatory=True))

apiDoc.addMissingIntermediateNs(usage)

apiDoc.addNoSuchNs(usage)

apiDoc.addNeedNsPermOrAdmin(usage, apiDoc.CONTROL)

usage.addReturn(Return(
    apiDoc.BAD_REQUEST,
    'If the %s argument is missing or invalid.' % actionArg))

apiDoc.addCannotRespondWithPayload(usage)

apiDoc.addOkOtherwise(usage)

responsePayload = JSONPayload()
responsePayload.addField(PayloadField(
    'policy', unicode,
    'The policy (either %r or %r).' % (permissions.OPEN, permissions.CLOSED)))
responsePayload.addField(PayloadField(
    'exceptions', list,
    'The names of the users who are exceptions to the policy.',
    listType=unicode))
usage.addResponsePayload(responsePayload)


def _addCommonGetTagProperties(usage, category):
    possibleActions = ', '.join(permissions.actionsByCategory[category])
    usage.addArgument(Argument(
        actionArg,
        """The action whose permissions information is
        sought. Possible values are: """ + possibleActions + '.',
        'string',
        mandatory=True))

    apiDoc.addMissingIntermediateNs(usage)

    apiDoc.addNoSuchTag(usage)

    apiDoc.addNeedTagPermOrAdmin(usage, apiDoc.CONTROL)

    usage.addReturn(Return(
        apiDoc.BAD_REQUEST,
        'If the %s argument is missing or invalid.' % actionArg))

    apiDoc.addCannotRespondWithPayload(usage)

    apiDoc.addOkOtherwise(usage)

    responsePayload = JSONPayload()
    responsePayload.addField(PayloadField(
        'policy', unicode,
        """The policy (either 'open' or 'closed')."""))
    responsePayload.addField(PayloadField(
        'exceptions', list,
        'The names of the users who are exceptions to the policy.',
        listType=unicode))
    usage.addResponsePayload(responsePayload)

request = """GET /permissions/namespaces/test?action=create HTTP/1.1
Authorization: Basic XXXXXXXX"""
response = '''HTTP/1.1 200 OK
Content-Length: 44
Date: Mon, 02 Aug 2010 14:58:28 GMT
Content-Type: application/json

{"policy": "closed", "exceptions": ["test"]}'''
description = "Retrieve the 'create' policy for the test namespace."
usage.addExample(HTTPExample(request, response, description))

# --- GET /permissions/tags/NAMESPACE1/NAMESPACE2/TAG --------------

usage = HTTPUsage(
    '/' + httpTagCategoryName + apiDoc.NS_NS_TAG,
    """Get the permissions on a tag: the open/closed policy,
    and the set of exceptions to the policy.""")
usage.resourceClass = ConcreteTagPermissionResource
topLevel.addUsage(usage)
_addCommonGetTagProperties(usage, tagCategoryName)

request = """GET /permissions/tags/test/quz?action=update HTTP/1.1
Authorization: Basic XXXXXXXX"""
response = """HTTP/1.1 200 OK
Content-Length: 44
Date: Mon, 02 Aug 2010 14:59:22 GMT
Content-Type: application/json

{"policy": "closed", "exceptions": ["test"]}"""
description = "Retrieve the 'update' policy for the test/quz tag."
usage.addExample(HTTPExample(request, response, description))


# --- GET /permissions/tag-instances/NAMESPACE1/NAMESPACE2/TAG --------------

usage = HTTPUsage(
    '/' + httpTagInstanceSetCategoryName + apiDoc.NS_NS_TAG,
    """Get the permissions on the set of tag instances: the open/closed policy,
    and the set of exceptions to the policy.""")
usage.resourceClass = ConcreteTagInstancesPermissionResource
topLevel.addUsage(usage)
_addCommonGetTagProperties(usage, tagInstanceSetCategoryName)

request = """GET /permissions/tag-values/test/quz?action=delete HTTP/1.1
Authorization: Basic XXXXXXXX"""
response = '''HTTP/1.1 200 OK
Content-Length: 36
Date: Mon, 02 Aug 2010 14:59:54 GMT
Content-Type: application/json

{"policy": "open", "exceptions": []}'''
description = """Retrieve the 'delete' policy for values associated with
the test/quz tag."""
usage.addExample(HTTPExample(request, response, description))

# ------------------------------ Permissions PUT --------------------------
topLevel = HTTPTopLevel(httpPermissionCategoryName, 'PUT')
registry.register(topLevel)


# --- PUT /permissions/namespaces/NAMESPACE1/NAMESPACE2 ------------

usage = HTTPUsage('/' + httpNamespaceCategoryName + apiDoc.NS_NS, """
    Update the permissions on a namespace: the open/closed policy,
    and the set of exceptions to the policy.""")
usage.resourceClass = ConcreteNamespacePermissionResource
usage.successCode = http.NO_CONTENT
topLevel.addUsage(usage)

possibleActions = ', '.join(permissions.actionsByCategory[
    namespaceCategoryName])

usage.addArgument(Argument(
    actionArg,
    """The action whose permissions information is
    to be updated. Possible values are: """ + possibleActions + '.',
    'string',
    mandatory=True))

apiDoc.addMissingIntermediateNs(usage)

apiDoc.addNoSuchNs(usage)

apiDoc.addNeedNsPermOrAdmin(usage, apiDoc.CONTROL)

apiDoc.addUnknownExceptionUser(usage)

usage.addReturn(Return(
    apiDoc.BAD_REQUEST,
    'If the policy is not %r or %r.' % (permissions.OPEN, permissions.CLOSED)))

usage.addReturn(Return(
    apiDoc.BAD_REQUEST,
    'If the %s argument is missing or invalid.' % actionArg))

usage.addReturn(Return(
    apiDoc.BAD_REQUEST,
    'If an invalid user is specified in the exceptions list.'))

usage.addReturn(Return(
    apiDoc.NOT_FOUND,
    'If a user in the exceptions list does not exist.'))

apiDoc.addBadRequestPayload(usage)

usage.addReturn(Return(
    apiDoc.NO_CONTENT,
    'If permissions are changed successfully.'))

requestPayload = JSONPayload()
requestPayload.addField(PayloadField(
    'policy', unicode,
    'The policy (either %r or %r).' % (permissions.OPEN, permissions.CLOSED)))
requestPayload.addField(PayloadField(
    'exceptions', list,
    'The names of the users who are exceptions to the policy.',
    listType=unicode))
usage.addRequestPayload(requestPayload)


def _addCommonPutTagProperties(usage, category):
    possibleActions = ', '.join(permissions.actionsByCategory[category])
    usage.addArgument(Argument(
        actionArg,
        """The action whose permissions information is
        to be updated. Possible values are: """ + possibleActions + '.',
        'string',
        mandatory=True))

    apiDoc.addMissingIntermediateNs(usage)

    apiDoc.addNoSuchTag(usage)

    apiDoc.addNeedTagPermOrAdmin(usage, apiDoc.CONTROL)

    apiDoc.addUnknownExceptionUser(usage)

    usage.addReturn(Return(
        apiDoc.BAD_REQUEST,
        'If the policy is not %r or %r.' % (
            permissions.OPEN, permissions.CLOSED)))

    usage.addReturn(Return(
        apiDoc.BAD_REQUEST,
        'If the %s argument is missing or invalid.' % actionArg))

    apiDoc.addBadRequestPayload(usage)

    usage.addReturn(Return(
        apiDoc.NO_CONTENT,
        'If permissions are changed successfully.'))

    requestPayload = JSONPayload()
    requestPayload.addField(PayloadField(
        'policy', unicode,
        'The policy (either %r or %r).' % (
            permissions.OPEN, permissions.CLOSED)))
    requestPayload.addField(PayloadField(
        'exceptions', list,
        'The names of the users who are exceptions to the policy.',
        listType=unicode))
    usage.addRequestPayload(requestPayload)

request = '''PUT /permissions/namespaces/test?action=create HTTP/1.1
Authorization: Basic XXXXXXXX
Content-Length: XXXXXXXX
Content-Type: application/json

{
  "policy": "closed",
  "exceptions": ["test", "ntoll"]
}'''
response = """HTTP/1.1 204 No Content
Date: Mon, 02 Aug 2010 15:03:42 GMT
Content-Type: text/html"""
description = "Update the 'create' policy for the test namespace."
usage.addExample(HTTPExample(request, response, description))

# --- PUT /permissions/tags/NAMESPACE1/NAMESPACE2/TAG --

usage = HTTPUsage('/' + httpTagCategoryName + apiDoc.NS_NS_TAG, """
    Update the permissions on a tag: the open/closed policy,
    and the set of exceptions to the policy.""")
usage.resourceClass = ConcreteTagPermissionResource
usage.successCode = http.NO_CONTENT
topLevel.addUsage(usage)
_addCommonPutTagProperties(usage, tagCategoryName)

request = '''PUT /permissions/tags/test/quz?action=update HTTP/1.1
Authorization: Basic XXXXXXXX
Content-Length: XXXXXXXX
Content-Type: application/json

{
  "policy": "closed",
  "exceptions": ["test", "ntoll"]
}'''
response = """HTTP/1.1 204 No Content
Date: Mon, 02 Aug 2010 15:04:39 GMT
Content-Type: text/html"""
description = "Update the 'update' policy for the test/quz tag."
usage.addExample(HTTPExample(request, response, description))

# --- PUT /permissions/tag-values/NAMESPACE1/NAMESPACE2/TAG --

usage = HTTPUsage('/' + httpTagInstanceSetCategoryName + apiDoc.NS_NS_TAG, """
    Update the permissions on a tag's instances: the open/closed policy,
    and the set of exceptions to the policy.""")
usage.resourceClass = ConcreteTagInstancesPermissionResource
usage.successCode = http.NO_CONTENT
topLevel.addUsage(usage)
_addCommonPutTagProperties(usage, tagInstanceSetCategoryName)

request = '''PUT /permissions/tag-values/test/quz?action=write HTTP/1.1
Authorization: Basic XXXXXXXX
Content-Length: XXXXXXXX
Content-Type: application/json

{
  "policy": "closed",
  "exceptions": ["test", "ntoll"]
}'''
response = """HTTP/1.1 204 No Content
Date: Mon, 02 Aug 2010 15:08:44 GMT
Content-Type: text/html"""
description = """Update the 'write' policy for values associated with
the test/quz tag."""
usage.addExample(HTTPExample(request, response, description))

# ------------------------------ Permissions DELETE -----------------------
topLevel = HTTPTopLevel(httpPermissionCategoryName, 'DELETE')
topLevel.description = """
    DELETE is not supported on permissions because namespaces
    and tags must always have a set of permissions."""
registry.register(topLevel)
