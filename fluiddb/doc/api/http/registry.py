import copy
import logging
import operator

from twisted.web import http

from fluiddb.common import error, util
from fluiddb.web import payloads, mimeparse


class Registry(object):
    """
    Provide a registry of HTTP API functions.

    The HTTPTopLevel class holds details of a particular HTTP API function. It
    has a description, a top-level URI (like 'namespaces', 'objects', etc), a
    verb (GET, PUT, etc), an optional set of notes, and a set of HTTPUsages to
    illustrate use.

    Each HTTPUsage has a sub-URI (which follows the URI of the HTTPTopLevel in
    HTTP requests), optional Arguments, Notes, and Examples.  Arguments, Notes
    and Examples have a description.

    In glorious ASCII art (note: this picture doesn't show any Examples).

                                   self._toplevels
                            ___________________________
                           /            |              \
                          /             |               \
              HTTPTopLevel         HTTPTopLevel          HTTPTopLevel
               /     |               /    \                   |
        HTTPUsage HTTPUsage    HTTPUsage   HTTPUsage      HTTPUsage
                                /    \                      /   \
                             Note   Argument              Note  Argument
                             Note   Argument                    Argument
                             Note   Argument                    Argument
                                    Argument


    The Registry class allows you to do two main things: 1) register API
    functions and 2) selectively extract them via the get() method, based
    on things like whether they are implemented, whether we're displaying
    unimplemented things, or whether they are only available to admin user.

    For usage, see test/test_APIRegistry.py or the files providing the
    top-level HTTP resources in fluiddb.web/*.py
    """

    def __init__(self):
        # Keys of self._toplevels are (string) top-level URI path
        # components, like 'namespaces', 'tags', etc.  Values are
        # dictionaries whose keys are (string) HTTP verbs, like 'GET' and
        # 'PUT', and whose values are HTTPTopLevel instances applicable to
        # that top-level / verb combination. self._toplevels is populated
        # by passing instances of HTTPTopLevel to self.register.
        self._toplevels = {}

    def _verbKey(self, verb):
        """
        A convenience comparison function used to sort HTTP verbs into CRUD
        order, so the ordering of verbs in documentation is always identical.
        """
        return {
            'POST': 0, 'GET': 1, 'HEAD': 2, 'PUT': 3, 'DELETE': 4}[verb]

    def get(self, toplevels='*', verbs='*',
            usageResourceClass=None, showUnimplemented=False, showAdmin=False):
        """
        Retrieve and filter HTTPTopLevel instances.  Return a list of
        lists, each of whose elements is of the form

          [ 'toplevel', verbDict ]

        where toplevel is a string, like 'tags' or 'namespaces', and
        verbDict is a dictionary whose keys are verb strings like 'GET' and
        'PUT' and whose values are instances of HTTPTopLevel that were
        registered via self.register.

        The toplevels and verbs arguments are strings indicating which
        toplevels and verbs are wanted. They can be either: a single string
        value, like 'namespaces', a list of values separated by comma, like
        'GET,HEAD', or the special value '*'.

        A value of '*' for toplevel requests that information about all
        known top-level URI components be returned. A value of '*' for verb
        indicates that information about all supported verbs (for each
        requested top-level) be returned.
        """
        foundMatchingVerb = False

        if toplevels == '*':
            toplevels = sorted(self._toplevels.keys())
            if not toplevels:
                raise error.EmptyRegistry()
        else:
            toplevels = toplevels.split(',')
            for toplevel in toplevels:
                if toplevel not in self._toplevels:
                    raise error.NoSuchToplevel(
                        'Unknown API top-level category %r.' % toplevel)

        # We now have a non-empty list of matching top-level names to
        # examine (i.e., to see if they allow the requested verb(s)).
        # Find the requested verbs within each top-level.

        toplevelResults = []

        for toplevel in toplevels:
            if verbs == '*':
                # Sort the supported verbs for this toplevel into CRUD order.
                theseVerbs = sorted(self._toplevels[toplevel].keys(),
                                    key=self._verbKey)
                if not theseVerbs:
                    # This top-level doesn't support *any* verbs, as far as
                    # we've been told. That probably indicates an error: by
                    # the time we start using self.get, the registry should
                    # be populated.
                    raise error.EmptyToplevel(
                        'API registry top-level %r is empty' % toplevel)
            else:
                theseVerbs = verbs.split(',')

            foundMatchingVerbThisTopLevel = False
            matchingVerbList = []

            # Filter the available verbs for this top-level according to
            # whether they're implemented, only available to the admin, etc.

            for verb in theseVerbs:
                if verb in self._toplevels[toplevel]:
                    httpTopLevel = self._toplevels[toplevel][verb]
                    if ((showAdmin or not httpTopLevel.adminOnly) and
                            (httpTopLevel.implemented or showUnimplemented)):

                        matchingVerbList.append(
                            (verb,
                             httpTopLevel.filter(
                                 usageResourceClass=usageResourceClass,
                                 showUnimplemented=showUnimplemented,
                                 showAdmin=showAdmin)))
                        foundMatchingVerbThisTopLevel = True

            if foundMatchingVerbThisTopLevel:
                # We have some matching verbs for this toplevel, so we can
                # add to the toplevel result list.
                foundMatchingVerb = True
                toplevelResults.append([toplevel, matchingVerbList])

        if verbs != '*' and not foundMatchingVerb:
            raise error.NoSuchVerb(
                'Unknown HTTP verb(s) %r for toplevel(s) %r.' %
                (verbs, toplevels))

        return toplevelResults

    def register(self, httpToplevel):
        "Add a new HTTPTopLevel instance to the registry."
        verbDict = self._toplevels.setdefault(httpToplevel.toplevel, {})
        if httpToplevel.verb in verbDict:
            raise error.AlreadyExists(
                'The API registry already contains an entry for (%s, %s).' %
                (httpToplevel.toplevel, httpToplevel.verb))
        else:
            verbDict[httpToplevel.verb] = httpToplevel

    def findUsage(self, toplevels, verbs, usageResourceClass,
                  showUnimplemented=False, showAdmin=True):
        toplevelList = self.get(toplevels, verbs,
                                usageResourceClass=usageResourceClass,
                                showUnimplemented=showUnimplemented,
                                showAdmin=showAdmin)

        if len(toplevelList) != 1:
            raise error.InternalInconsistency(
                'Got toplevel list %r not of length one.' % toplevelList)
        tLevel, verbList = toplevelList[0]
        if tLevel != toplevels:
            raise error.InternalInconsistency(
                'Retrieved toplevel (%r) was not the one wanted (%r).' % (
                    tLevel, toplevels))
        if len(verbList) != 1:
            raise error.InternalInconsistency(
                'Got verb list %r not of length one.' % verbList)
        v, httpTopLevel = verbList[0]
        if v != verbs:
            raise error.InternalInconsistency(
                'Retrieved verb (%r) was not the one wanted (%r).' % (
                    v, verbs))
        nUsages = len(httpTopLevel.usages)
        if nUsages == 0:
            raise error.NoSuchUsage()
        elif nUsages > 1:
            raise error.NoSuchUsage(
                'Got HTTPTopLevel with usages (%r) not of length one.' %
                httpTopLevel.usages)
        usage = httpTopLevel.usages[0]
        if usage.resourceClass != usageResourceClass:
            raise error.InternalInconsistency(
                'Retrieved a usage whose resource class (%r) was not '
                'the one wanted (%r).' % (
                    usage.resourceClass.__class__.__name__,
                    usageResourceClass.__name__))

        # OK, we're finally assured we have the usage we wanted.
        return usage

    def checkRequest(self, usage, request):
        """Do as many standard checks on the request as we can. Return the
        payload of the request - either as a parsed dictionary or else as
        the raw bytes if a formatted payload wasn't expected (according to
        the passed usage).

        TODO: This method would be cleaner if we had the wsfe resource
        method extract the payload and pass it in."""
        payload = payloads.extractPayload(request)

        if usage.requestPayloads:
            if not payload:
                if usage.requestPayloadMandatory():
                    if payload is None:
                        raise error.NoContentLengthHeader()
                    else:
                        raise error.MissingPayload()
                dictionary = {}
            else:
                parsedPayload = payloads.parsePayload(usage, request, payload)
                dictionary = parsedPayload.dictionary
                usagePayload = parsedPayload.usagePayload
                if 'password' in dictionary:
                    loggedDictionary = dictionary.copy()
                    loggedDictionary['password'] = '*******'
                else:
                    loggedDictionary = dictionary

                logging.info('Request %s: payload dictionary %r' % (
                    request._fluidDB_reqid, loggedDictionary,))

                # Check that mandatory usage payload fields are present in
                # the request.
                for field in usagePayload.fields():
                    if field.mandatory:
                        if field.name not in dictionary:
                            # Just tell them about the first error, not all
                            # missing fields.
                            raise error.PayloadFieldMissing(field.name)

                # Check that all payload fields given in the request are
                # mentioned in the usage and that they all have the correct
                # type.
                for field in dictionary:
                    if field not in usagePayload:
                        # XXX Since the unknown arg limit was removed, should
                        # unknown payload fields be allowed?
                        raise error.UnknownPayloadField(field)
                    if not payloads.checkPayloadFieldType(
                            dictionary[field], usagePayload[field]):
                        raise error.InvalidPayloadField(field)

            result = dictionary
        else:
            if payload and not usage.unformattedPayloadPermitted:
                raise error.UnexpectedContentLengthHeader()
            result = payload

        # Check if the usage has any mandatory arguments, and, if so,
        # make sure they are present in the request args.
        for name, argument in usage.arguments.items():
            if argument.mandatory and name not in request.args:
                raise error.MissingArgument(name)

        return result

    def checkResponse(self, responseType, responseDict, usage, request):
        if not usage.responsePayloads:
            raise error.InternalError('Usage has no response payloads.')

        try:
            usagePayload = usage.responsePayloads[responseType]
        except KeyError:
            raise error.InternalError('Usage has no %r response payloads.' %
                                      responseType)

        # Check that mandatory usage payload fields are present in the
        # response.
        for field in usagePayload.fields():
            if field.mandatory:
                if field.name not in responseDict:
                    # Complain about the first error, not all missing fields.
                    logging.error('Request %s: mandatory response payload '
                                  'field %r missing' %
                                  (request._fluidDB_reqid, field.name))
                    raise error.ResponsePayloadFieldMissing(field.name)

        # Check that all payload fields given in the response are
        # mentioned in the usage.
        for field in responseDict:
            if field not in usagePayload:
                logging.error('Request %s: unknown response payload field %r' %
                              (request._fluidDB_reqid, field))
                # XXX raise error.UnknownResponsePayloadField(field)
                continue
            if not payloads.checkPayloadFieldType(
                    responseDict[field], usagePayload[field],
                    strCountsAsUnicode=(responseType == 'application/json')):
                logging.error('Request %s: response payload field '
                              '%r has incorrect type (%r instead of %r).' %
                              (request._fluidDB_reqid, field,
                               type(responseDict[field]),
                               usagePayload[field].typeAsStr()))
                raise error.InvalidResponsePayloadField(field)


# Create a singleton instance of the Registry class.
registry = Registry()

_fieldTypeToStr = {
    bool: 'boolean',
    dict: 'dictionary',
    int: 'integer',
    float: 'float',
    unicode: 'unicode string',
}

_fieldTypeToStrPlural = {
    dict: 'dictionaries',
}


class PayloadField(object):

    def __init__(self, name, type, description, mandatory=True, listType=None,
                 mayBeNone=False):
        self.name = name
        self.type = type
        self.description = description
        self.mandatory = mandatory
        self.listType = listType
        self.mayBeNone = mayBeNone

    def typeAsStr(self):
        if type(self.type) is str:
            # Some types are still given as strings.
            return self.type
        elif self.type in _fieldTypeToStr:
            return _fieldTypeToStr[self.type]
        elif self.type is list:
            if self.listType in _fieldTypeToStr:
                return (
                    'list of %s' %
                    _fieldTypeToStrPlural.get(
                        self.listType,
                        _fieldTypeToStr[self.listType] + 's'))

        raise error.InternalInconsistency(
            'Unexpected payload field type %r. Field name %r, desc %r.' %
            (self.type, self.name, self.description))


class Payload(object):
    format = None

    def __init__(self):
        self._fields = {}
        self.mandatory = False

    def addField(self, field):
        assert field.name not in self._fields
        self._fields[field.name] = field
        if field.mandatory:
            self.mandatory = True

    def fields(self):
        return [self._fields[f] for f in sorted(self._fields.keys())]

    def __contains__(self, field):
        return field in self._fields

    def __getitem__(self, name):
        return self._fields[name]


class JSONPayload(Payload):
    format = 'application/json'


class Return(object):

    def __init__(self, code, condition):
        self.code = code
        self.condition = condition


class Note(object):

    def __init__(self, description):
        self.description = description


class Argument(object):

    def __init__(self, name, description, type_, default=None, mandatory=False,
                 implemented=True):
        self.name = name
        self.description = description
        self.mandatory = mandatory
        self.type = type_
        self.default = default
        self.implemented = implemented


class HTTPExample(object):
    """
    Represents an example HTTP request/response pair used to demonstrate how
    an API call is made as raw HTTP
    """

    def __init__(self, request, response, description=None):
        super(HTTPExample, self).__init__()
        self.request = request
        self.response = response
        self.description = description


class HTTPUsage(object):

    filterArgsKey = operator.attrgetter('name')

    def __init__(self, subURIs, description):
        super(HTTPUsage, self).__init__()
        if isinstance(subURIs, basestring):
            subURIs = [subURIs]
        self.subURIs = subURIs
        self.description = description
        self.arguments = {}
        self.notes = []
        self.returns = []
        self.implemented = True
        self.adminOnly = False
        # The payloads are stored in a dict keyed on payload format (e.g.,
        # 'application/json'). If there are multiple payloads, they are
        # alternates. E.g., we might offer the possibility of sending a
        # JSON payload or an XML payload.
        self.requestPayloads = {}
        self.responsePayloads = {}
        self.resourceClass = None
        self.successCode = http.OK
        # PUT on /objects/ID/ns/tag sends a payload that we don't want the
        # registry's checkRequest method to complain about. Setting
        # unformattedPayloadPermitted will disable the check.
        self.unformattedPayloadPermitted = False
        # The examples list contains instances of HTTPExample.
        self.examples = []

    def addRequestPayload(self, payload):
        assert payload.format not in self.requestPayloads
        self.requestPayloads[payload.format] = payload

    def addResponsePayload(self, payload):
        assert payload.format not in self.responsePayloads
        self.responsePayloads[payload.format] = payload

    def addExample(self, example):
        assert example not in self.examples
        self.examples.append(example)

    def getResponsePayloadTypeFromAcceptHeader(self, request):
        if not self.responsePayloads:
            raise error.InternalError('Usage with no response payloads.')
        accept = request.getHeader('accept') or '*/*'
        responseType = mimeparse.best_match(
            self.responsePayloads.keys(), accept)
        try:
            payload = self.responsePayloads[responseType]
        except KeyError:
            raise error.NotAcceptable()
        else:
            return payload.format

    def requestPayloadMandatory(self):
        return any([p.mandatory for p in self.requestPayloads.values()])

    def addArgument(self, argument):
        assert argument.name not in self.arguments
        self.arguments[argument.name] = argument

    def sortedArguments(self):
        return sorted(self.arguments.values(), key=self.filterArgsKey)

    def addNote(self, note):
        self.notes.append(note)

    def addReturn(self, r):
        self.returns.append(r)

    def filter(self, showUnimplemented=False):
        new = copy.copy(self)
        new.arguments = util.dictSubset(
            self.arguments,
            [a.name for a in self.arguments.values() if
             (a.implemented or showUnimplemented)])
        return new


class HTTPTopLevel(object):

    def __init__(self, toplevel, verb):
        super(HTTPTopLevel, self).__init__()
        self.toplevel = toplevel
        self.verb = verb
        self.description = None
        self.usages = []
        self.notes = []
        self.adminOnly = False
        self.implemented = True

    def __repr__(self):
        return '<%s %s/%s>' % (
            self.__class__.__name__, self.toplevel, self.verb)

    def __eq__(self, other):
        return self.toplevel == other.toplevel and self.verb == other.verb

    def addUsage(self, usage):
        self.usages.append(usage)

    def addNote(self, note):
        self.notes.append(note)

    def filter(self, usageResourceClass=None,
               showUnimplemented=False, showAdmin=False):
        new = copy.copy(self)
        new.usages = [u.filter(showUnimplemented) for u in self.usages if

                      (u.implemented or showUnimplemented) and

                      (usageResourceClass is None or
                       usageResourceClass is u.resourceClass) and

                      (not u.adminOnly or showAdmin)]
        return new
