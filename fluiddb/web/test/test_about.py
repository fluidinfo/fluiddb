import cStringIO as StringIO
from collections import defaultdict
import json

from twisted.web import http
from twisted.trial import unittest
from twisted.internet import defer
from twisted.web.http_headers import Headers

from fluiddb.common import error, util
from fluiddb.common.defaults import sep, contentTypeForPrimitiveJSON
from fluiddb.common import paths
from fluiddb.common.types_thrift.ttypes import (
    TObjectInfo, TNoInstanceOnObject)
from fluiddb.web.query import createThriftValue, guessValue
from fluiddb.web import objects
from fluiddb.web.about import (
    AboutResource, AboutObjectResource, AboutTagInstanceResource)
from fluiddb.web.resource import ErrorResource
from fluiddb.web.test.test_objects import FakeFacade as SimpleFakeFacade
from fluiddb.testing.doubles import FakeSession
from fluiddb.web.util import buildHeader
from fluiddb.testing.basic import FluidinfoTestCase


_aboutPath = sep.join(paths.aboutPath())


class FakeRequest(object):
    """
    I pretend to be an HTTP request, with a handful of required methods
    used by Twisted resource classes (e.g., write, finish,
    setResponseCode).
    """

    _fluidDB_reqid = None
    body = ''

    def __init__(self, method, d=None, headers=None, hostname=None):
        """
        Initialize. d (if not None) is a deferred that will fire with the
        body of the response when request.finish is called.

        @param d: A C{Deferred} instance to fire when the request is finished.
        @param headers: a C{dict} of headers and values for the request.
        """
        self.method = method
        self.d = d
        self.uri = None
        self.requestHeaders = Headers(headers)
        self.responseHeaders = Headers()
        self.args = {'verb': [method]}
        self.hostname = hostname
        self.content = StringIO.StringIO()

    def isSecure(self):
        """
        Mark the request as not being secure (i.e., not HTTPS). The
        isSecure is used by the FluidDB wsfe to construct the Location
        header in the response to a POST.

        @return: A constant, C{False}, seeing as we don't care about
                 the return value, only that we provide the method.
        """
        return False

    def finish(self):
        """
        Indicate that the request has been fully serviced. Send the
        response body (as accumulated by self.write) back to the deferred
        (if any) we were passed in __init__.

        @return: C{None}.
        """
        if self.d:
            self.d.callback(self.body)

    def write(self, data):
        """
        Fake the writing of data back to the client. Instead, we
        accumuluate it so as to deliver it to our test client when
        self.finish is called.

        @param data: A C{str} of response payload data.

        @return: C{None}.
        """
        self.body += data

    def getHeader(self, key):
        """
        Get a header from the request. This is copied from Twisted's
        twisted.web.http.Request class.

        @param key: A C{str} indicating the header to return.

        @return: The C{str} header value from the request if it exists,
                 else C{None}.
        """
        value = self.requestHeaders.getRawHeaders(key)
        if value is not None:
            return value[-1]

    def getResponseHeader(self, key):
        """
        Get a header from the response.

        @param key: A C{str} indicating the header to return.

        @return: The C{str} header value from the response if it exists,
                 else C{None}.
        """
        value = self.responseHeaders.getRawHeaders(key)
        if value is not None:
            return value[-1]

    def setHeader(self, name, value):
        """
        Set a header for the HTTP response. This is copied from Twisted's
        twisted.web.http.Request class.

        @param name: A C{str} indicating the header to set.
        @param value: A C{str} values for the header.

        @return: C{None}.
        """
        self.responseHeaders.setRawHeaders(name, [value])

    def getAllHeaders(self):
        """
        Get all the request headers. This is copied from Twisted's
        twisted.web.http.Request class.

        @return: A C{dict} of request header name -> value.
        """
        headers = {}
        for k, v in self.requestHeaders.getAllRawHeaders():
            headers[k.lower()] = v[-1]
        return headers

    def setResponseCode(self, code):
        """
        Set the response status code.

        @param code: An HTTP status code.

        @return: C{None}.
        """
        self.status = code

    def notifyFinish(self):
        """
        Return a C{twisted.internet.Deferred} that fires when the request
        finishes or errors if the client disconnects. Note that this method
        is needed as resource.py calls it, but we do not need to actually
        fire the returned deferred for our tests (which cause synchronous
        exceptions to immediately be returned to the request errback).

        @return: C{twisted.internet.Deferred}
        """
        return defer.succeed(None)

    def getRequestHostname(self):
        """
        Return the hostname that was used for issuing this request.
        """
        return self.hostname


class FakeTagsClient(object):
    """
    A fake tags service client supporting set, get and delete operations
    on tags on objects. State is maintained in a dictionary (self.values).
    """

    def __init__(self):
        """
        Initialize.

        self.values is keyed on path. Its values are dicts keyed on
        objectId, with tag values (as Thrift values) as values.
        """
        self.values = defaultdict(dict)

    def getTagInstance(self, session, path, objectId):
        """
        Get a tag instance from an object.

        @param session: a L{FakeSession} instance.
        @param path: the C{str} path to the tag.
        @param objectId: the id of the object in question.

        @return: A C{Deferred} that fires with the value of the tag on the
                 object on an object, if known. If we don't have a value for
                 the tag on the object, fire the Deferred with a
                 TNoInstanceOnObject failure.
        """
        try:
            return defer.succeed((self.values[path][objectId], None))
        except KeyError:
            fail = TNoInstanceOnObject(path, objectId)
            return defer.fail(fail)

    def setTagInstance(self, session, path, objectId, value):
        """
        Return a Deferred (fired with None) after setting the value of a
        tag (path) on an object.

        @param session: a L{FakeSession} instance.
        @param path: the C{str} path to the tag.
        @param objectId: the id of the object in question.
        @param value: The value to set the tag to.
        """
        self.values[path][objectId] = value
        return defer.succeed(None)

    def deleteTagInstance(self, session, path, objectId):
        """
        Return a Deferred (fired with None) after deleting the value of a
        tag (path) off an object.

        @param session: a L{FakeSession} instance.
        @param path: the C{str} path to the tag.
        @param objectId: the id of the object in question.
        """
        try:
            del self.values[path][objectId]
        except KeyError:
            fail = TNoInstanceOnObject(path, objectId)
            return defer.fail(fail)
        return defer.succeed(None)


class FakeQueryResolver(object):

    def __init__(self, about, results, testsuite):
        """
        I am a class that pretends to be able to resolve a query for
        fluiddb/about equal to the about value we're initialized with. The
        result of the fake query will be the results we are passed (which
        should be a list of object ids) converted to a set.

        @param about: The C{fluiddb/about} value specifying an object.
        @param results: A C{set} of object id query results.
        @param testsuite: The instance of a L{unittest.TestCase} that is
                          running a test.
        """
        self.about = about
        self.results = results
        self.testsuite = testsuite

    def resolveQuery(self, session, query):
        """
        Pretend to resolve a fluiddb/about query. Make sure we got the
        query we were expecting, return the results we were given in
        advance.

        @param session: a L{FakeSession} instance.
        @param query: a L{str} FluidDB query.

        @return: The set of object id results we were initialized with.
        """
        expectedQuery = '%s = "%s"' % (_aboutPath, self.about)
        self.testsuite.assertEqual(query, expectedQuery)
        return defer.succeed(set(self.results))

    def updateResults(self, results):
        """
        Alter the result that should be returned by the query.

        @param results: A C{set} of object id query results.

        @return: C{None}.
        """
        self.results = results


class FakeFacadeClient(object):
    """
    I pretend to be a facade client that wsfe resources can use to get
    their work done.
    """

    def __init__(self, fakeTagsClient=None, fakeQueryResolver=None):
        """
        Set up a fake tags client and a fake query resolver, if given.

        @param fakeTagsClient: A L{FakeTagsClient} instance.
        @param fakeQueryResolver: A L{FakeQueryResolver} instance.
        """
        if fakeTagsClient:
            self.getTagInstance = fakeTagsClient.getTagInstance
            self.setTagInstance = fakeTagsClient.setTagInstance
            self.deleteTagInstance = fakeTagsClient.deleteTagInstance

        if fakeQueryResolver:
            self.fakeQueryResolver = fakeQueryResolver
            self.resolveQuery = fakeQueryResolver.resolveQuery

    def getObject(self, session, objectId, showAbout):
        """
        If anyone asks for information about an object, just return a
        TObjectInfo instance with no tags on it.

        @param session: a L{FakeSession} instance.
        @param objectId: the object id to get.
        @param showAbout: A C{bool} indicating whether to return the about tag.

        @return: A C{Deferred} that fires with an insance of L{TObjectInfo}.
        """
        return defer.succeed(TObjectInfo(tagPaths=[]))

    @defer.inlineCallbacks
    def createObject(self, session, about):
        """
        Pretend to create an object. If an about value is passed, check
        with our query resolver to see if the about value is known. If not
        (or if no about value was passed) return a random new object id.
        If we get an about value that the query resolver doesn't know
        about, we adjust our query resolver and tags client so that next
        time they do. This is to simulate PUT correctly, which creates the
        object with the about value in the case it doesn't already exist.

        @param session: a L{FakeSession} instance.
        @param about: A C{str} value for the about tag.

        @return: A C{Deferred} that fires with the object id of the new
                 object.
        """
        if about:
            results = yield self.resolveQuery(
                None, '%s = "%s"' % (_aboutPath, about))
            if results:
                objectId = results.pop()
            else:
                objectId = util.generateObjectId()
                # Make sure the query resolver now knows how to correctly
                # resolve this about value.
                self.fakeQueryResolver.updateResults([objectId])
                # And add an instance of the about tag to the object.
                self.setTagInstance(session, _aboutPath, object, about)
        else:
            objectId = util.generateObjectId()
        defer.returnValue(objectId)


class TestAboutResource(FluidinfoTestCase):
    """
    I test the wsfe.service.web.about.AboutResource class, which only has a
    getChild method which twisted.web.server calls with the first component
    of all /about requests.
    """

    def testGetChildWithEmptyStringReturnsSelf(self):
        """
        If the about value is empty, the resource class should return
        itself.
        """
        resource = AboutResource(None, None)
        child = resource.getChild('', None)
        self.assertTrue(resource is child)

    def testGetChildWithBadUTF8(self):
        """
        If the about value is not valid UTF-8, check we return a
        BAD_REQUEST status.
        """
        resource = AboutResource(None, None)
        child = resource.getChild('\xFF', None)
        self.assertTrue(isinstance(child, ErrorResource))
        self.assertEqual(child.status, http.BAD_REQUEST)
        self.assertTrue(child.errorClass is error.BadArgument)

    def testGetChildNormalOperation(self):
        """
        When the about value is a regular string, we should get back a
        child resource that's an instance of AboutObjectResource and whose
        'about' tag is the string we called getChild with.
        """
        about = 'barcelona'
        resource = AboutResource(None, None)
        child = resource.getChild(about, None)
        self.assertTrue(isinstance(child, AboutObjectResource))
        self.assertEqual(child.about, about)


class TestAboutObjectResource(unittest.TestCase):
    """
    These are tests on an object that's about something. E.g., a request
    for /about/barcelona.  I.e., they are about an object itself, not about
    tag values on the object.
    """

    def testAllowedMethods(self):
        """L{AboutObjectResource} allows the correct methods"""
        resource = AboutObjectResource(None, None, None)
        self.assertEqual(('GET', 'OPTIONS', 'POST'), resource.allowedMethods)

    def testGetChildEmptyStringReturnsSelf(self):
        """
        If the next component in the URI is empty, the resource should
        consume it (i.e., return itself).
        """
        resource = AboutObjectResource(None, None, None)
        child = resource.getChild('', None)
        self.assertTrue(resource is child)

    def testGetAboutTagInstanceResource(self):
        """
        Check that when getChild is passed a name (ntoll) and the request
        has additional components (a tag path) that we receive a child
        object that has the right about value and path.
        """
        about = 'barcelona'
        resource = AboutObjectResource(None, None, about)
        request = FakeRequest('GET')
        request.postpath = ['books', 'rating']
        child = resource.getChild('ntoll', request)
        self.assertEqual(child.about, about)
        self.assertEqual(child.path, 'ntoll/books/rating')

    @defer.inlineCallbacks
    def testPOSTObjectAboutChickenSoup(self):
        """
        Test that a POST to /about/chicken%20soup results in a CREATED
        status and that we get back the id of the object that already
        existed (as will be supplied by the fake query resolver).
        """
        about = 'chicken soup'
        objectId = util.generateObjectId()
        fakeQueryResolver = FakeQueryResolver(about, [objectId], self)
        facadeClient = FakeFacadeClient(fakeQueryResolver=fakeQueryResolver)
        session = FakeSession()
        resource = AboutObjectResource(facadeClient, session, about)
        d = defer.Deferred()
        request = FakeRequest('POST', d)
        request.content = StringIO.StringIO()
        resource.render(request)
        body = yield d
        self.assertEqual(request.status, http.CREATED)
        responseDict = json.loads(body)
        self.assertEqual(responseDict['id'], objectId)

    @defer.inlineCallbacks
    def testGETAboutWithDoubleQuotes(self):
        '''
        Test that a GET to /about/chicken%20"soup"%20taste results in an OK
        status and that we get back the id of the object that already
        existed (as will be supplied by the fake query resolver).
        '''
        about = 'chicken "soup" taste'
        aboutQuoted = r'chicken \"soup\" taste'
        objectId = util.generateObjectId()
        fakeQueryResolver = FakeQueryResolver(aboutQuoted, [objectId], self)
        facadeClient = FakeFacadeClient(fakeQueryResolver=fakeQueryResolver)
        session = FakeSession()
        resource = AboutObjectResource(facadeClient, session, about)
        d = defer.Deferred()
        request = FakeRequest('GET', d)
        request.args = {objects.showAboutArg: ['False']}
        request.content = StringIO.StringIO()
        resource.render(request)
        yield d
        self.assertEqual(request.status, http.OK)

    @defer.inlineCallbacks
    def testGETObjectAboutBarcelona(self):
        """
        Test that a GET of /about/barcelona results in an OK status and
        that we get back the id of the object that already existed (as will
        be supplied by the fake query resolver), and that it has no tags on
        it.
        """
        about = 'barcelona'
        objectId = util.generateObjectId()
        fakeQueryResolver = FakeQueryResolver(about, [objectId], self)
        facadeClient = FakeFacadeClient(fakeQueryResolver=fakeQueryResolver)
        session = FakeSession()
        resource = AboutObjectResource(facadeClient, session, about)
        d = defer.Deferred()
        request = FakeRequest('GET', d)
        request.args = {objects.showAboutArg: ['False']}
        request.content = StringIO.StringIO()
        resource.render(request)
        body = yield d
        self.assertEqual(request.status, http.OK)
        responseDict = json.loads(body)
        self.assertEqual(responseDict[objects.tagPathsArg], [])
        self.assertEqual(responseDict['id'], objectId)

    @defer.inlineCallbacks
    def testGETNonExistentObjectAboutParis(self):
        """
        Set up a fake query resolver that will give no results for
        fluiddb/about = \"paris\" and then make sure that doing a GET on
        /about/paris results in a NOT_FOUND status.
        """
        about = 'paris'
        fakeQueryResolver = FakeQueryResolver(about, [], self)
        facadeClient = FakeFacadeClient(fakeQueryResolver=fakeQueryResolver)
        session = FakeSession()
        resource = AboutObjectResource(facadeClient, session, about)
        d = defer.Deferred()
        request = FakeRequest('GET', d)
        request.args = {objects.showAboutArg: ['False']}
        request.content = StringIO.StringIO()
        resource.render(request)
        yield d
        self.assertEqual(request.status, http.NOT_FOUND)

    @defer.inlineCallbacks
    def testPOSTNonExistentObjectAboutParis(self):
        """
        Set up a fake query resolver that will give no results for
        fluiddb/about = \"paris\" and then make sure that doing a POST on
        /about/paris results in a CREATED status.
        """
        about = 'paris'
        fakeQueryResolver = FakeQueryResolver(about, [], self)
        fakeTagsClient = FakeTagsClient()
        facadeClient = FakeFacadeClient(fakeQueryResolver=fakeQueryResolver,
                                        fakeTagsClient=fakeTagsClient)
        session = FakeSession()
        resource = AboutObjectResource(facadeClient, session, about)
        d = defer.Deferred()
        request = FakeRequest('POST', d)
        request.args = {objects.aboutArg: [about]}
        request.content = StringIO.StringIO()
        resource.render(request)
        yield d
        self.assertEqual(request.status, http.CREATED)


class TestAboutObjectTagResource(unittest.TestCase):
    """
    These are tests that check tags on objects (as specified by about
    values).
    """

    @defer.inlineCallbacks
    def testRatingForObjectAboutBarcelona(self):
        """
        Run a series of tests on the ntoll/rating tag on the object about
        barcelona:

          - the tag should initially not be present.
          - we should successfully be able to do a PUT.
          - we should then be able to do a GET, HEAD, and DELETE in that order.
          - a final GET should then indicate the tag is gone.
        """
        about = 'barcelona'
        tag = 'ntoll/rating'
        rating = 6
        objectIdAboutBarcelona = util.generateObjectId()

        fakeQueryResolver = FakeQueryResolver(
            about, [objectIdAboutBarcelona], self)
        fakeTagsClient = FakeTagsClient()
        facadeClient = FakeFacadeClient(fakeTagsClient=fakeTagsClient,
                                        fakeQueryResolver=fakeQueryResolver)
        session = FakeSession()
        resource = AboutTagInstanceResource(facadeClient, session, about, tag)

        # Test GET when there is no instance on the object.
        d = defer.Deferred()
        request = FakeRequest('GET', d)
        request.content = StringIO.StringIO()
        resource.render(request)
        yield d
        self.assertEqual(request.status, http.NOT_FOUND)

        # Test PUT.
        payload = json.dumps(rating)
        headers = {
            'Content-Length': [str(len(payload))],
            'Content-Type': [contentTypeForPrimitiveJSON],
        }
        d = defer.Deferred()
        request = FakeRequest('PUT', d, headers)
        request.content = StringIO.StringIO(payload)
        resource.render(request)
        yield d
        self.assertEqual(request.status, http.NO_CONTENT)
        self.assertEqual(
            guessValue(fakeTagsClient.values[tag][objectIdAboutBarcelona]),
            rating)

        # Check that the right path, objectId, and value was passed to the
        # fake tags client.
        self.assertEqual(fakeTagsClient.values, {
            tag: {objectIdAboutBarcelona: createThriftValue(rating)},
        })

        # Test GET.
        d = defer.Deferred()
        request = FakeRequest('GET', d)
        request.content = StringIO.StringIO()
        resource.render(request)
        body = yield d
        self.assertEqual(request.status, http.OK)
        self.assertEqual(request.getResponseHeader('Content-Type'),
                         contentTypeForPrimitiveJSON)
        receivedRating = json.loads(body)
        self.assertEqual(receivedRating, rating)

        # Test HEAD
        d = defer.Deferred()
        request = FakeRequest('HEAD', d)
        request.content = StringIO.StringIO()
        resource.render(request)
        body = yield d
        self.assertEqual(request.status, http.OK)
        self.assertEqual(body, '')

        # Test DELETE
        d = defer.Deferred()
        request = FakeRequest('DELETE', d)
        request.content = StringIO.StringIO()
        resource.render(request)
        body = yield d
        self.assertEqual(request.status, http.NO_CONTENT)

        # Test GET when, finally, there is no instance on the object.
        d = defer.Deferred()
        request = FakeRequest('GET', d)
        request.content = StringIO.StringIO()
        resource.render(request)
        yield d
        self.assertEqual(request.status, http.NOT_FOUND)

        # Check that the value really was deleted.
        self.assertEqual(fakeTagsClient.values, {tag: {}})

    @defer.inlineCallbacks
    def testRatingForAboutContainingDoubleQuotes(self):
        """
        Run GET requests against a non-existent object about a string with
        embedded double quotes.  Check that it returns NOT_FOUND.
        """
        about = 'chicken "soup" taste'
        aboutQuoted = r'chicken \"soup\" taste'
        tag = 'ntoll/rating'
        fakeQueryResolver = FakeQueryResolver(aboutQuoted, [], self)
        facadeClient = FakeFacadeClient(fakeQueryResolver=fakeQueryResolver)
        session = FakeSession()
        resource = AboutTagInstanceResource(facadeClient, session, about, tag)
        d = defer.Deferred()
        request = FakeRequest('GET', d)
        request.content = StringIO.StringIO()
        resource.render(request)
        yield d
        self.assertEqual(request.status, http.NOT_FOUND)

    @defer.inlineCallbacks
    def testRatingForNonexistentObjectAboutParis(self):
        """
        Run GET and HEAD requests against a non-existent object about paris,
        check that both return NOT_FOUND.
        """
        about = 'paris'
        tag = 'ntoll/rating'
        fakeQueryResolver = FakeQueryResolver(about, [], self)
        facadeClient = FakeFacadeClient(fakeQueryResolver=fakeQueryResolver)
        session = FakeSession()
        resource = AboutTagInstanceResource(facadeClient, session, about, tag)

        # Test GET.
        d = defer.Deferred()
        request = FakeRequest('GET', d)
        request.content = StringIO.StringIO()
        resource.render(request)
        yield d
        self.assertEqual(request.status, http.NOT_FOUND)

        # Test HEAD.
        d = defer.Deferred()
        request = FakeRequest('HEAD', d)
        request.content = StringIO.StringIO()
        resource.render(request)
        yield d
        self.assertEqual(request.status, http.NOT_FOUND)

    @defer.inlineCallbacks
    def testPUTOnNonexistentObjectAboutAfrica(self):
        """
        PUT a value for ntoll/keywords onto the object about africa, even
        though no such object exists.  This should succeed with a CREATED
        status.  We then do a GET to make sure we can retrieve the value.
        BTW, I use a set of strings as a value to increase code coverage of
        about.py

        We want /about to be identical in semantics to /objects/id and so
        this behavior mirrors that of /objects/id/tag/path which does not
        require that the object id exists in order to put a value onto it.
        """
        about = 'africa'
        tag = 'ntoll/keywords'
        value = ['hot', 'dry', 'dusty']
        fakeQueryResolver = FakeQueryResolver(about, [], self)
        fakeTagsClient = FakeTagsClient()
        facadeClient = FakeFacadeClient(fakeTagsClient=fakeTagsClient,
                                        fakeQueryResolver=fakeQueryResolver)
        session = FakeSession()
        resource = AboutTagInstanceResource(facadeClient, session, about, tag)

        # Test PUT.
        payload = json.dumps(value)
        headers = {
            'Content-Length': [str(len(payload))],
            'Content-Type': [contentTypeForPrimitiveJSON],
        }
        d = defer.Deferred()
        request = FakeRequest('PUT', d, headers)
        request.content = StringIO.StringIO(payload)
        resource.render(request)
        self.assertEqual(request.status, http.NO_CONTENT)
        yield d

        # Pull the object id out of the fake tags client and tell the fake
        # query resolver to now give a different answer for the query on
        # africa.
        keys = fakeTagsClient.values[_aboutPath].keys()
        self.assertEqual(len(keys), 1)

        # Test GET.
        d = defer.Deferred()
        request = FakeRequest('GET', d)
        request.content = StringIO.StringIO()
        resource.render(request)
        body = yield d
        self.assertEqual(request.status, http.OK)
        self.assertEqual(request.getResponseHeader('Content-Type'),
                         contentTypeForPrimitiveJSON)
        receivedValue = json.loads(body)
        self.assertEqual(set(value), set(receivedValue))

    @defer.inlineCallbacks
    def testPUTGETBinaryValueOnObjectAboutAfrica(self):
        """
        PUT a binary value for ntoll/rating onto the object about
        africa. Then do two GET requests:

          - A GET with no Accept header (which means we accept anything)
            and check the result is what we set.
          - Do a GET with an Accept header that prevents FluidDB from
            delivering, and check we get a NOT_ACCEPTABLE status.
        """
        about = 'africa'
        tag = 'ntoll/binary'
        value = '\x00\x01'
        mimetype = 'ntoll/personalbinary'
        objectIdAboutAfrica = util.generateObjectId()
        fakeQueryResolver = FakeQueryResolver(
            about, [objectIdAboutAfrica], self)
        fakeTagsClient = FakeTagsClient()
        facadeClient = FakeFacadeClient(fakeTagsClient=fakeTagsClient,
                                        fakeQueryResolver=fakeQueryResolver)
        session = FakeSession()
        resource = AboutTagInstanceResource(facadeClient, session, about, tag)

        # Test PUT.
        payload = value
        headers = {
            'Content-Length': [str(len(payload))],
            'Content-Type': [mimetype],
        }
        d = defer.Deferred()
        request = FakeRequest('PUT', d, headers)
        request.content = StringIO.StringIO(payload)
        resource.render(request)
        yield d
        self.assertEqual(request.status, http.NO_CONTENT)

        # Test GET.
        d = defer.Deferred()
        request = FakeRequest('GET', d)
        request.content = StringIO.StringIO()
        resource.render(request)
        body = yield d
        self.assertEqual(request.status, http.OK)
        self.assertEqual(request.getResponseHeader('Content-Type'),
                         mimetype)
        self.assertEqual(body, value)

        # Test GET when no acceptable Accept header value.
        headers = {'Accept': ['italian/lira, chewing/gum']}
        request = FakeRequest('GET', None, headers)
        request.content = StringIO.StringIO()
        resource.render(request)
        self.assertEqual(request.status, http.NOT_ACCEPTABLE)

    @defer.inlineCallbacks
    def testPUTGETNonBinaryWithNoAcceptableType(self):
        """
        PUT a primitive (non-binary) value for ntoll/rating onto the object
        about africa. Then do a GET with an Accept header that prevents
        FluidDB from delivering, and check we get a NOT_ACCEPTABLE status.
        """
        about = 'africa'
        tag = 'ntoll/binary'
        value = 5
        objectIdAboutAfrica = util.generateObjectId()
        fakeQueryResolver = FakeQueryResolver(
            about, [objectIdAboutAfrica], self)
        fakeTagsClient = FakeTagsClient()
        facadeClient = FakeFacadeClient(fakeTagsClient=fakeTagsClient,
                                        fakeQueryResolver=fakeQueryResolver)
        session = FakeSession()
        resource = AboutTagInstanceResource(facadeClient, session, about, tag)

        # Test PUT.
        payload = json.dumps(value)
        headers = {
            'Content-Length': [str(len(payload))],
            'Content-Type': [contentTypeForPrimitiveJSON],
        }
        d = defer.Deferred()
        request = FakeRequest('PUT', d, headers)
        request.content = StringIO.StringIO(payload)
        resource.render(request)
        yield d
        self.assertEqual(request.status, http.NO_CONTENT)

        # Test GET when no acceptable Accept header value.
        headers = {'Accept': ['italian/lira, chewing/gum']}
        request = FakeRequest('GET', None, headers)
        request.content = StringIO.StringIO()
        resource.render(request)
        self.assertEqual(request.status, http.NOT_ACCEPTABLE)

    @defer.inlineCallbacks
    def testPUTWithNoContentTypeButWithPayload(self):
        """
        Check that if we attempt a PUT with a payload but don't send a
        Content-Type, we get a BAD_REQUEST response and a
        NoContentTypeHeader response error-class header.
        """
        about = 'africa'
        tag = 'ntoll/binary'
        payload = 'random payload'
        objectIdAboutAfrica = util.generateObjectId()
        fakeQueryResolver = FakeQueryResolver(
            about, [objectIdAboutAfrica], self)
        fakeTagsClient = FakeTagsClient()
        facadeClient = FakeFacadeClient(fakeTagsClient=fakeTagsClient,
                                        fakeQueryResolver=fakeQueryResolver)
        session = FakeSession()
        resource = AboutTagInstanceResource(facadeClient, session, about, tag)

        # Test PUT.
        headers = {
            'Content-Length': [str(len(payload))],
        }
        d = defer.Deferred()
        request = FakeRequest('PUT', d, headers)
        request.content = StringIO.StringIO(payload)
        resource.render(request)
        yield d
        self.assertEqual(request.status, http.BAD_REQUEST)
        self.assertEqual(
            request.getResponseHeader(buildHeader('Error-Class')),
            error.NoContentTypeHeader.__name__)

    @defer.inlineCallbacks
    def testPUTWithNoContentTypeNoPayload(self):
        """
        Check that if we attempt a PUT with no payload and no Content-Type,
        we get an (ok) NO_CONTENT status (this is putting a None as the
        value).
        """
        about = 'africa'
        tag = 'ntoll/binary'
        objectIdAboutAfrica = util.generateObjectId()
        fakeQueryResolver = FakeQueryResolver(
            about, [objectIdAboutAfrica], self)
        fakeTagsClient = FakeTagsClient()
        facadeClient = FakeFacadeClient(fakeTagsClient=fakeTagsClient,
                                        fakeQueryResolver=fakeQueryResolver)
        session = FakeSession()
        resource = AboutTagInstanceResource(facadeClient, session, about, tag)

        # Test PUT.
        d = defer.Deferred()
        request = FakeRequest('PUT', d)
        request.content = StringIO.StringIO()
        resource.render(request)
        yield d
        self.assertEqual(request.status, http.NO_CONTENT)

    @defer.inlineCallbacks
    def testPUTSetOfStringsNotAllStrings(self):
        """
        PUT a set of strings (that are in fact not all strings) value for
        ntoll/rating onto the object about africa. This should result in a
        BAD_REQUEST status and an UnsupportedJSONType error class.
        """
        about = 'africa'
        tag = 'ntoll/rating'
        tagset = ['good', 'bad', 6]
        objectIdAboutAfrica = util.generateObjectId()
        fakeQueryResolver = FakeQueryResolver(
            about, [objectIdAboutAfrica], self)
        fakeTagsClient = FakeTagsClient()
        facadeClient = FakeFacadeClient(fakeTagsClient=fakeTagsClient,
                                        fakeQueryResolver=fakeQueryResolver)
        session = FakeSession()
        resource = AboutTagInstanceResource(facadeClient, session, about, tag)

        # Test PUT.
        payload = json.dumps(tagset)
        headers = {
            'Content-Length': [str(len(payload))],
            'Content-Type': [contentTypeForPrimitiveJSON],
        }
        d = defer.Deferred()
        request = FakeRequest('PUT', d, headers)
        request.content = StringIO.StringIO(payload)
        resource.render(request)
        yield d
        self.assertEqual(request.status, http.BAD_REQUEST)
        self.assertEqual(
            request.getResponseHeader(buildHeader('Error-Class')),
            error.UnsupportedJSONType.__name__)

    @defer.inlineCallbacks
    def testGETListValuesPreserveOrder(self):
        """
        List values get via GET on /about preserve the same order of the
        original value.
        """
        facadeClient = SimpleFakeFacade()
        session = FakeSession()

        # Tell our FakeFacade to preload some data for a given tag.
        facadeClient.values = {
            'fe2f50c8-997f-4049-a180-9a37543d001d': {
                'tag/test': ['x', 'y', 'z', 'a', 'b', 'c'],
                'fluiddb/about': 'about tag'}}

        resource = AboutTagInstanceResource(facadeClient, session,
                                            'about tag',
                                            'tag/test')

        request = FakeRequest('GET', {}, {}, '')
        body = yield resource.deferred_render_GET(request)
        value = json.loads(body)
        self.assertEqual(['x', 'y', 'z', 'a', 'b', 'c'], value)


class AboutTagsResourceXFluidDBTypeHeaderTest(FluidinfoTestCase):

    @defer.inlineCallbacks
    def assertXFluidDBHeaderForType(self, method, value, expectedTypeString):
        """
        L{TagInstanceResource.render_HEAD} should put an X-FluidDB-Type header
        indicating the type of the value that it's returning. This tests
        checks float types.
        """
        facadeClient = SimpleFakeFacade()
        session = FakeSession()
        # Tell our FakeFacade to preload some data for a given tag.
        facadeClient.values = {
            'fe2f50c8-997f-4049-a180-9a37543d001d': {
                'tag/test': value,
                'fluiddb/about': 'about tag'}}

        resource = AboutTagInstanceResource(facadeClient, session,
                                            'about tag',
                                            'tag/test')

        request = FakeRequest(method, {}, {}, '')
        yield getattr(resource, 'render_' + method)(request)
        typeValue = request.getResponseHeader(buildHeader('Type'))
        self.assertEqual(expectedTypeString, typeValue)

    def testHEADRequestReturnsTypeHeaderFloat(self):
        """
        L{TagInstanceResource.render_HEAD} should put an X-FluidDB-Type header
        indicating the type of the value that it's returning. This tests
        checks float types.
        """
        return self.assertXFluidDBHeaderForType('HEAD', 5.5, 'float')

    def testHEADRequestReturnsTypeHeaderNull(self):
        """
        L{TagInstanceResource.render_HEAD} should put an X-FluidDB-Type header
        indicating the type of the value that it's returning. This tests
        checks the none type.
        """
        return self.assertXFluidDBHeaderForType('HEAD', None, 'null')

    def testHEADRequestReturnsTypeHeaderBool(self):
        """
        L{TagInstanceResource.render_HEAD} should put an X-FluidDB-Type header
        indicating the type of the value that it's returning. This tests
        checks the bool type.
        """
        return self.assertXFluidDBHeaderForType('HEAD', True, 'boolean')

    def testHEADRequestReturnsTypeHeaderString(self):
        """
        L{TagInstanceResource.render_HEAD} should put an X-FluidDB-Type header
        indicating the type of the value that it's returning. This tests
        checks the string type.
        """
        return self.assertXFluidDBHeaderForType('HEAD', 'hello', 'string')

    def testHEADRequestReturnsTypeHeaderInt(self):
        """
        L{TagInstanceResource.render_HEAD} should put an X-FluidDB-Type header
        indicating the type of the value that it's returning. This tests
        checks the int type.
        """
        return self.assertXFluidDBHeaderForType('HEAD', 34, 'int')

    def testHEADRequestReturnsTypeHeaderList(self):
        """
        L{TagInstanceResource.render_HEAD} should put an X-FluidDB-Type header
        indicating the type of the value that it's returning. This tests
        checks the set type.
        """
        return self.assertXFluidDBHeaderForType('HEAD', ['one', 'two'],
                                                'list-of-strings')

    def testGETRequestReturnsTypeHeaderFloat(self):
        """
        L{TagInstanceResource.render_GET} should put an X-FluidDB-Type header
        indicating the type of the value that it's returning. This tests
        checks the set type.
        """
        return self.assertXFluidDBHeaderForType('GET', 5.5, 'float')

    def testGETRequestReturnsTypeHeaderNull(self):
        """
        L{TagInstanceResource.render_GET} should put an X-FluidDB-Type header
        indicating the type of the value that it's returning. This tests
        checks the none type.
        """
        return self.assertXFluidDBHeaderForType('GET', None, 'null')

    def testGETRequestReturnsTypeHeaderBool(self):
        """
        L{TagInstanceResource.render_GET} should put an X-FluidDB-Type header
        indicating the type of the value that it's returning. This tests
        checks the bool type.
        """
        return self.assertXFluidDBHeaderForType('GET', True, 'boolean')

    def testGETRequestReturnsTypeHeaderString(self):
        """
        L{TagInstanceResource.render_GET} should put an X-FluidDB-Type header
        indicating the type of the value that it's returning. This tests
        checks the string type.
        """
        return self.assertXFluidDBHeaderForType('GET', 'hey', 'string')

    def testGETRequestReturnsTypeHeaderInt(self):
        """
        L{TagInstanceResource.render_GET} should put an X-FluidDB-Type header
        indicating the type of the value that it's returning. This tests
        checks the int type.
        """
        return self.assertXFluidDBHeaderForType('GET', 12, 'int')

    def testGETRequestReturnsTypeHeaderList(self):
        """
        L{TagInstanceResource.render_GET} should put an X-FluidDB-Type header
        indicating the type of the value that it's returning. This tests
        checks the set type.
        """
        return self.assertXFluidDBHeaderForType('GET', ['three', 'four'],
                                                'list-of-strings')
