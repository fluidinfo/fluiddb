from twisted.web import http

from fluiddb.doc.api.http.registry import Return
from fluiddb.common.defaults import sep, httpObjectCategoryName, aboutTagName
from fluiddb.common import paths


def spanWrap(klass, what):
    return '<span class="%s">%s</span>' % (klass, what)


def httpCode(code):
    n = code if isinstance(code, int) else getattr(http, code)
    text = http.RESPONSES[n]
    return spanWrap('httpError', '%d (%s)' % (n, text))

OK = httpCode('OK')
CREATED = httpCode('CREATED')
NO_CONTENT = httpCode('NO_CONTENT')
BAD_REQUEST = httpCode('BAD_REQUEST')
UNAUTHORIZED = httpCode('UNAUTHORIZED')
NOT_FOUND = httpCode('NOT_FOUND')
PRECONDITION_FAILED = httpCode('PRECONDITION_FAILED')
REQUEST_ENTITY_TOO_LARGE = httpCode('REQUEST_ENTITY_TOO_LARGE')
NOT_ACCEPTABLE = httpCode('NOT_ACCEPTABLE')
UNSUPPORTED_MEDIA_TYPE = httpCode('UNSUPPORTED_MEDIA_TYPE')

LIST = spanWrap('perm', 'LIST')
CREATE = spanWrap('perm', 'CREATE')
READ = spanWrap('perm', 'READ')
UPDATE = spanWrap('perm', 'UPDATE')
DELETE = spanWrap('perm', 'DELETE')
CONTROL = spanWrap('perm', 'CONTROL')

ADMIN_ATTR = spanWrap('tag', sep.join(paths.usernamePath()))
ABOUT = spanWrap('tag', aboutTagName)
ABOUT_TAG = spanWrap('tag', sep.join(paths.aboutPath()))
LOCATION = spanWrap('httpHeader', 'Location')
ACCEPT = spanWrap('httpHeader', 'Accept')
CONTENT_ENCODING = spanWrap('httpHeader', 'Content-Encoding')
CONTENT_TYPE = spanWrap('httpHeader', 'Content-type')
ABOUTSTR = spanWrap('var', 'aboutstr')
ID = spanWrap('var', 'id')
NS1 = spanWrap('var', 'namespace1')
NS2 = spanWrap('var', 'namespace2')
TAG = spanWrap('var', 'tag')
USERNAME = spanWrap('var', 'username')
PROFILE = spanWrap('var', 'profile')
CATEGORY = spanWrap('var', 'category')
ACTION = spanWrap('var', 'action')
NS_NS = '/' + NS1 + '/' + NS2
NS_NS_TAG = NS_NS + '/' + TAG
ID_NS_NS_TAG = '/' + ID + NS_NS + '/' + TAG
ABOUTSTR_NS_NS_TAG = '/' + ABOUTSTR + NS_NS + '/' + TAG
URI_OBJECTS = spanWrap('URI', '/' + httpObjectCategoryName)
URI_OBJECTS_ID_NS_NS_TAG = spanWrap(
    'URI', '/' + httpObjectCategoryName + ID_NS_NS_TAG)


def addNeedBeUserOrAdmin(usage, perm):
    usage.addReturn(
        Return(UNAUTHORIZED,
               "If the requesting user is not the user in the URI "
               "and does not have " + perm + """ permission on the
               relevant system tag."""))


def addNeedAdmin(usage, perm):
    usage.addReturn(
        Return(UNAUTHORIZED,
               """If the requesting user does not have """ + perm +
               """ permission on the relevant system tag."""))


def addNeedTagOrNsPermOrAdmin(usage, perm):
    usage.addReturn(
        Return(UNAUTHORIZED,
               "If the requesting user does not have " + perm +
               " permission on the tag or namespace."))


def addNeedNsPermOrAdmin(usage, perm):
    usage.addReturn(
        Return(UNAUTHORIZED,
               "If the requesting user does not have " + perm +
               " permission on the namespace."))


def addNeedTagPermOrAdmin(usage, perm):
    usage.addReturn(
        Return(UNAUTHORIZED,
               "If the requesting user does not have " + perm +
               " permission on the tag."))


def addUserNotFound(usage):
    usage.addReturn(
        Return(NOT_FOUND,
               "If the user does not exist."))


def addNonExistentUser(usage):
    usage.addReturn(
        Return(PRECONDITION_FAILED,
               "The user named in the URI does not exist."))


def addUnknownExceptionUser(usage):
    usage.addReturn(
        Return(PRECONDITION_FAILED,
               "The user named in the exceptions list does not exist."))


def addMissingIntermediateNs(usage):
    usage.addReturn(
        Return(NOT_FOUND,
               "If an intermediate namespace does not exist."))


def addNoSuchNs(usage):
    usage.addReturn(
        Return(NOT_FOUND,
               "If the namespace does not exist."))


def addNoSuchTag(usage):
    usage.addReturn(
        Return(NOT_FOUND,
               "If the tag does not exist."))


def addNoSuchProfile(usage):
    usage.addReturn(
        Return(NOT_FOUND,
               "If the requested profile does not exist."))


def addOkOtherwise(usage):
    usage.addReturn(Return(OK, "No error."))


def addBadRequestPayload(usage):
    usage.addReturn(Return(BAD_REQUEST,
                           '''An error with the request payload. <a
                           href="http://doc.fluidinfo.com/fluidDB/api/'''
                           '''http.html#bad-request">More details</a>.'''))


def addCannotRespondWithPayload(usage):
    usage.addReturn(Return(
        BAD_REQUEST,
        '''An error with the request makes it impossible to respond. <a
        href="http://doc.fluidinfo.com/fluidDB/api/'''
        '''http.html#bad-request">More details</a>.'''))
