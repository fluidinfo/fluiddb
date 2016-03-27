import urllib

from twisted.web import http
from twisted.internet import defer

from fluiddb.application import getDevelopmentMode
from fluiddb.cache.user import cachingGetUser
from fluiddb.common import users
from fluiddb.common.defaults import httpUserCategoryName
from fluiddb.common.types_thrift.ttypes import (
    TBadRequest, TNoSuchUser, TUserUpdate)
from fluiddb.doc.api.http import apiDoc
from fluiddb.doc.api.http.registry import (
    registry, HTTPTopLevel, HTTPUsage, JSONPayload, PayloadField, Note, Return,
    HTTPExample)
from fluiddb.model.oauth import OAuthConsumerAPI
from fluiddb.model.user import checkPassword
from fluiddb.web import payloads
from fluiddb.web.resource import NoResource, WSFEResource


class VerifyUserPasswordResource(WSFEResource):
    """
    Handle requests attempting to validate a user's password without
    receiving a 401 since some browsers suck.. A POST to
    /users/ntoll/verify will end up here.
    """

    allowedMethods = ('POST', 'OPTIONS')
    isLeaf = True

    def __init__(self, facadeClient, session, username):
        # Can't use super: old-style twisted.web.resource.Resource ancestor.
        WSFEResource.__init__(self, facadeClient, session)
        self.username = username

    def deferred_render_POST(self, request):
        # TODO: usages should be cached locally; lookup is expensive.
        usage = registry.findUsage(httpUserCategoryName, 'POST',
                                   VerifyUserPasswordResource)
        responseType = usage.getResponsePayloadTypeFromAcceptHeader(request)

        def run():
            if not request.isSecure() and not getDevelopmentMode():
                raise TBadRequest(
                    '/users/<username>/verify requests must use HTTPS')
            dictionary = registry.checkRequest(usage, request)
            user = cachingGetUser(self.username.decode('utf-8'))
            if not user:
                raise TNoSuchUser(self.username)
            password = dictionary['password']

            if checkPassword(password, user.passwordHash):
                # FIXME Hard-coding the 'anon' consumer here isn't great,
                # but for now it means we don't have to change the public
                # API. -jkakar
                api = OAuthConsumerAPI()
                consumer = cachingGetUser(u'anon')
                accessToken = api.getAccessToken(consumer, user)
                renewalToken = api.getRenewalToken(consumer, user)
                return {'accessToken': accessToken.encrypt(),
                        'fullname': user.fullname,
                        'renewalToken': renewalToken.encrypt(),
                        'role': str(user.role),
                        'valid': True}
            else:
                return {'valid': False}

        def success(responseDict):
            registry.checkResponse(responseType, responseDict, usage, request)
            body = payloads.buildPayload(responseType, responseDict)
            request.setHeader('Content-length', str(len(body)))
            request.setHeader('Content-type', responseType)
            request.setResponseCode(usage.successCode)
            return body

        # save the deferred for testing purposes
        self.deferred = self.session.transact.run(run)
        self.deferred.addCallback(success)
        return self.deferred


class ConcreteUserResource(WSFEResource):

    allowedMethods = ('GET', 'PUT', 'DELETE', 'OPTIONS')

    def getChild(self, name, request):
        if name == '':
            return self
        elif name == 'verify':
            return VerifyUserPasswordResource(
                self.facadeClient, self.session, self.username)
        else:
            return NoResource()

    def __init__(self, facadeClient, session, username):
        # Can't use super: old-style twisted.web.resource.Resource ancestor.
        WSFEResource.__init__(self, facadeClient, session)
        self.username = username

    @defer.inlineCallbacks
    def deferred_render_GET(self, request):
        # TODO: usages should be cached locally; lookup is expensive.
        usage = registry.findUsage(httpUserCategoryName, 'GET',
                                   ConcreteUserResource)
        registry.checkRequest(usage, request)
        responseType = usage.getResponsePayloadTypeFromAcceptHeader(request)
        tuser = yield self.facadeClient.getUser(self.session, self.username)
        responseDict = {
            'name': tuser.name,
            'role': tuser.role,
            'id': tuser.objectId,
        }
        registry.checkResponse(responseType, responseDict, usage, request)
        body = payloads.buildPayload(responseType, responseDict)
        request.setHeader('Content-length', str(len(body)))
        request.setHeader('Content-type', responseType)
        request.setResponseCode(usage.successCode)
        defer.returnValue(body)

    @defer.inlineCallbacks
    def deferred_render_PUT(self, request):
        usage = registry.findUsage(httpUserCategoryName, 'PUT',
                                   ConcreteUserResource)
        dictionary = registry.checkRequest(usage, request)

        name = dictionary.get('name')
        email = dictionary.get('email')
        password = dictionary.get('password')
        role = dictionary.get('role')

        # All args are optional. Don't bother the facade if there's nothing
        # to do.
        if name or email or password or role:
            update = TUserUpdate(username=self.username, name=name,
                                 email=email, password=password, role=role)

            yield self.facadeClient.updateUser(self.session, update)

        request.setResponseCode(usage.successCode)

    @defer.inlineCallbacks
    def deferred_render_DELETE(self, request):
        usage = registry.findUsage(httpUserCategoryName, 'DELETE',
                                   ConcreteUserResource)
        registry.checkRequest(usage, request)
        yield self.facadeClient.deleteUser(self.session, self.username)
        request.setResponseCode(usage.successCode)


class UsersResource(WSFEResource):

    allowedMethods = ('POST', 'OPTIONS')

    def getChild(self, name, request):
        if name == '':
            return self
        else:
            return ConcreteUserResource(self.facadeClient, self.session, name)

    @defer.inlineCallbacks
    def deferred_render_POST(self, request):
        usage = registry.findUsage(httpUserCategoryName, 'POST', UsersResource)
        dictionary = registry.checkRequest(usage, request)
        responseType = usage.getResponsePayloadTypeFromAcceptHeader(request)

        username = dictionary['username']
        name = dictionary.get('name', username)
        password = dictionary['password']
        email = dictionary['email']

        objectId = yield self.facadeClient.createUserWithPassword(
            session=self.session,
            username=username.encode('utf-8'),
            password=password.encode('utf-8'),
            name=name.encode('utf-8'),
            email=email.encode('utf-8'))

        if request.isSecure():
            proto = "https"
        else:
            proto = "http"
        hostname = request.getRequestHostname()

        location = '%s://%s/%s/%s' % (
            proto, hostname, httpUserCategoryName,
            urllib.quote(username.encode('utf-8')))

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


# ------------------------------ Users POST -------------------------------
topLevel = HTTPTopLevel(httpUserCategoryName, 'POST')
topLevel.adminOnly = True
registry.register(topLevel)

# --- POST /users ---------------------------------------------------------

usage = HTTPUsage('', 'Create a new user.')
usage.adminOnly = True
usage.resourceClass = UsersResource
usage.successCode = http.CREATED
topLevel.addUsage(usage)

apiDoc.addNeedAdmin(usage, apiDoc.CREATE)

usage.addReturn(Return(
    apiDoc.PRECONDITION_FAILED,
    'If the user already exists.'))

usage.addReturn(Return(
    apiDoc.BAD_REQUEST,
    """If the username is unacceptable due to syntax. Usernames may
    contain only letters (according to the Unicode standard), digits,
    underscores, hyphens, colons, and periods."""))

usage.addReturn(Return(
    apiDoc.BAD_REQUEST,
    'If the username is too long. The maximum length of a username is ' +
    str(users.maxUsernameLength) + ' characters.'))

apiDoc.addBadRequestPayload(usage)

apiDoc.addCannotRespondWithPayload(usage)

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    'If the user is created successfully.'))

requestPayload = JSONPayload()
requestPayload.addField(PayloadField(
    'username', unicode, 'The Fluidinfo username for the new user.'))
requestPayload.addField(PayloadField(
    'name', unicode, 'The real-world name of the new user.', False))
requestPayload.addField(PayloadField(
    'password', unicode, 'The password for the new user.'))
requestPayload.addField(PayloadField(
    'email', unicode, 'The email address of the new user.'))
usage.addRequestPayload(requestPayload)

responsePayload = JSONPayload()
responsePayload.addField(PayloadField(
    'id', unicode,
    'The id of the object corresponding to the new user.'))
responsePayload.addField(PayloadField(
    'URI', unicode,
    'The URI of the new user.'))
usage.addResponsePayload(responsePayload)


usage.addNote(Note(
    'A ' + apiDoc.LOCATION +
    ' header will be returned containing the URI of the new user.'))


# --- POST /users/USERNAME/verify ------------------------------------------

usage = HTTPUsage('/' + apiDoc.USERNAME + '/verify',
                  "Verify a user's password for useless browsers like Safari. "
                  "Should only ever be used via https.")
usage.adminOnly = True
usage.resourceClass = VerifyUserPasswordResource

requestPayload = JSONPayload()
requestPayload.addField(PayloadField(
    'password', unicode, 'The password for the user.'))
usage.addRequestPayload(requestPayload)

topLevel.addUsage(usage)

apiDoc.addUserNotFound(usage)

apiDoc.addCannotRespondWithPayload(usage)

apiDoc.addOkOtherwise(usage)

# Note that all the fields except for 'valid' in the response payload below
# are marked as non-mandatory because if the call fails that's the only
# field returned.

responsePayload = JSONPayload()
responsePayload.addField(PayloadField(
    'accessToken', unicode,
    'A token for making OAuth2 API calls on behalf of the user.',
    mandatory=False))
responsePayload.addField(PayloadField(
    'fullname', unicode,
    "The user's real name", mandatory=False))
responsePayload.addField(PayloadField(
    'renewalToken', unicode,
    'An token for renewing an expired OAuth2 token.', mandatory=False))
responsePayload.addField(PayloadField(
    'valid', bool,
    "Whether the user's password is valid."))
responsePayload.addField(PayloadField(
    'role', unicode,
    "The user's role, one of ANONYMOUS, SUPERUSER, USER, or USER_MANAGER.",
    mandatory=False))

usage.addResponsePayload(responsePayload)


# ------------------------------ Users GET --------------------------------
topLevel = HTTPTopLevel(httpUserCategoryName, 'GET')
registry.register(topLevel)

# --- GET /users ---------------------------------------------------

usage = HTTPUsage('', 'Return a list of all users.')
usage.adminOnly = True
usage.resourceClass = UsersResource
usage.implemented = False
topLevel.addUsage(usage)

apiDoc.addNeedAdmin(usage, apiDoc.READ)

apiDoc.addCannotRespondWithPayload(usage)

apiDoc.addOkOtherwise(usage)

responsePayload = JSONPayload()

responsePayload.addField(PayloadField(
    'names', list,
    'The names of all Fluidinfo users.',
    listType=unicode))

usage.addResponsePayload(responsePayload)


# --- GET /users/USERNAME ------------------------------------------

usage = HTTPUsage('/' + apiDoc.USERNAME,
                  'Return information about a particular user.')
usage.resourceClass = ConcreteUserResource
topLevel.addUsage(usage)

apiDoc.addUserNotFound(usage)

apiDoc.addCannotRespondWithPayload(usage)

apiDoc.addOkOtherwise(usage)

responsePayload = JSONPayload()
responsePayload.addField(PayloadField(
    'id', unicode,
    'The id of the object corresponding to the user.'))
responsePayload.addField(PayloadField('name', unicode, "The user's name."))
responsePayload.addField(PayloadField('role', unicode, "The user's role."))
usage.addResponsePayload(responsePayload)

request = """GET /users/nto%CE%BB%CE%BB HTTP/1.1"""
response = '''HTTP/1.1 200 OK
Content-Length: 62
Date: Mon, 02 Aug 2010 15:18:17 GMT
Content-Type: application/json

{"name": "Nicholas To\\u03bb\\u03bbervey",
 "id": "42909deb-9854-47ae-a8f8-3f59d4fbe5a5"}'''
description = """Retrieve information about the user 'nto&lambda;&lambda;'.
Note that to specify unicode '&lambda;' characters in the request URI,
you must first convert them to UTF-8 and then URL-encode them.
Unicode is returned in the response, in the manner specified by the
JSON specification."""

usage.addExample(HTTPExample(request, response, description))


# ------------------------------ Users PUT --------------------------------
topLevel = HTTPTopLevel(httpUserCategoryName, 'PUT')
topLevel.adminOnly = True
registry.register(topLevel)

# --- PUT /users/USERNAME ------------------------------------------

usage = HTTPUsage('/' + apiDoc.USERNAME, 'Update a user.')
usage.adminOnly = True
usage.resourceClass = ConcreteUserResource
usage.successCode = http.NO_CONTENT
topLevel.addUsage(usage)

apiDoc.addNeedBeUserOrAdmin(usage, apiDoc.CREATE)

apiDoc.addUserNotFound(usage)

apiDoc.addBadRequestPayload(usage)

usage.addReturn(Return(apiDoc.httpCode(usage.successCode),
                       "If the user is updated successfully."))

requestPayload = JSONPayload()
requestPayload.addField(PayloadField(
    'name', unicode, """The real-world name of the new user. Omit this field
    if the user's name should remain unchanged.""", False))
requestPayload.addField(PayloadField(
    'password', unicode, """The password for the new user. Omit this field
    if the user's password should remain unchanged.""", False))
requestPayload.addField(PayloadField(
    'email', unicode, """The email address of the new user. Omit this field
    if the user's email should remain unchanged.""", False))
requestPayload.addField(PayloadField(
    'role', unicode, """The new role for the user. It can be: "USER",
    "USER_MANAGER", "ANONYMOUS" or "SUPERUSER". Omit this field
    if the user's role should remain unchanged.""", False))
usage.addRequestPayload(requestPayload)


# ------------------------------ Users DELETE -----------------------------
topLevel = HTTPTopLevel(httpUserCategoryName, 'DELETE')
topLevel.adminOnly = True
registry.register(topLevel)

# --- DELETE /users/USERNAME ---------------------------------------

usage = HTTPUsage('/' + apiDoc.USERNAME, 'Delete a user.')
usage.adminOnly = True
usage.resourceClass = ConcreteUserResource
usage.successCode = http.NO_CONTENT
topLevel.addUsage(usage)

apiDoc.addNeedAdmin(usage, apiDoc.DELETE)

apiDoc.addUserNotFound(usage)

usage.addReturn(Return(
    apiDoc.BAD_REQUEST,
    "If an attempt is made to delete the Fluidinfo system user."))

usage.addReturn(Return(
    apiDoc.httpCode(usage.successCode),
    "If the user is deleted successfully."))
