import json
import os
import uuid
import urllib
from base64 import b64encode

# from urllib import urlencode

from twisted.web import http
from twisted.internet import defer, reactor
from twisted.web.client import Agent, ResponseDone
from twisted.internet.protocol import Protocol
from twisted.web.http_headers import Headers
from twisted.trial import unittest

from txfluiddb.client import Endpoint, Object, Tag, BasicCreds

from fluiddb.common import defaults
from fluiddb.web import objects


def _setEndpoint():
    """
    Get the FluidDB endpoint in use from the user's environment.
    """
    return os.environ.get('FLUIDDB_ENDPOINT', 'http://localhost:9000')


def _getCreds():
    username = os.environ.get('FLUIDDB_ADMIN_USERNAME', 'fluiddb')
    password = os.environ.get('FLUIDDB_ADMIN_PASSWORD', 'secret')

    return BasicCreds(username, password)


class SimpleBodyProducer(object):
    """
    I write the body of an HTTP request to a consumer.
    """

    def __init__(self, data):
        """
        Store the data of the body away until we get a consumer.
        """
        self.data = data
        self.length = len(data)

    def startProducing(self, consumer):
        """
        Deliver the body of the request to the consumer and return a
        Deferred that has already fired to indicate that the entire body
        has been delivered.
        """
        consumer.write(self.data)
        return defer.succeed(None)


class ResponseGetter(Protocol):
    """
    I receive the body of a response to an HTTP request.
    """
    _buffer = ''

    def __init__(self, finished):
        """
        finished is a Deferred that I will fire when the entire body
        has been received and connectionLost is called.
        """
        self._finished = finished

    def dataReceived(self, bytes):
        """
        Ooh! More data. Store it away for a rainy day.
        """
        self._buffer += bytes

    def connectionLost(self, reason):
        """
        The connection went away. Check that it was simply because the
        response was finished, and fire the Deferred we were given
        initially with the accumulated body of the response.
        """
        reason.trap(ResponseDone)
        self._finished.callback(self._buffer)


class TestPOST(unittest.TestCase):
    """
    Tests that send POST requests to the /about URI.
    """

    def setUp(self):
        """
        Get the endpoint to use for all requests.
        """
        self._endpoint = _setEndpoint()

    @defer.inlineCallbacks
    def testNotAllowed(self):
        """
        Posting to /about is not allowed.
        """
        URI = '%s/%s' % (self._endpoint, defaults.httpAboutCategoryName)
        agent = Agent(reactor)
        response = yield agent.request('POST', URI)
        self.assertEqual(http.NOT_ALLOWED, response.code)


class TestGET(unittest.TestCase):

    def setUp(self):
        """
        Get the endpoint to use for all requests.
        """
        self._endpoint = _setEndpoint()

    @defer.inlineCallbacks
    def testRandomAboutNotFound(self):
        """
        A GET on /about/random-uuid-string will almost certainly receive a
        404.
        """
        URI = '%s/%s/%s' % (self._endpoint,
                            defaults.httpAboutCategoryName,
                            uuid.uuid4().hex)
        agent = Agent(reactor)
        response = yield agent.request('GET', URI)
        self.assertEqual(http.NOT_FOUND, response.code)

    @defer.inlineCallbacks
    def testMalformedUTF8(self):
        """
        A GET on /about/xxx where xxx is malformed UTF-8 should get a
        BAD_REQUEST.
        """
        about = '\xFF\xFF'
        URI = '%s/%s/%s' % (self._endpoint,
                            defaults.httpAboutCategoryName,
                            urllib.quote(about))
        agent = Agent(reactor)
        response = yield agent.request('GET', URI)
        self.assertEqual(http.BAD_REQUEST, response.code)

    @defer.inlineCallbacks
    def testSlashInAbout(self):
        """
        A GET on /about/xxx where xxx is a URI-quoted string containing a
        slash should work.
        """
        about = 'hey/you'
        # First create an object with that about value, and get its id.
        URI = '%s/%s' % (self._endpoint, defaults.httpObjectCategoryName)
        bodyProducer = SimpleBodyProducer(
            json.dumps({objects.aboutArg: about}))
        basicAuth = 'Basic %s' % b64encode('%s:%s' % ('testuser1', 'secret'))
        headers = Headers({'accept': ['application/json'],
                           'content-type': ['application/json'],
                           'authorization': [basicAuth]})
        agent = Agent(reactor)
        response = yield agent.request('POST', URI, headers, bodyProducer)
        self.assertEqual(http.CREATED, response.code)
        d = defer.Deferred()
        bodyGetter = ResponseGetter(d)
        response.deliverBody(bodyGetter)
        body = yield d
        j = json.loads(body)
        objectId1 = j['id']

        # Do a GET on /about/hey%2Fyou and make sure its id is the same as
        # the one of the object we just created. Note that we need to pass
        # safe='' to urllib.quote here to make sure it quotes the slash.
        URI = '%s/%s/%s' % (self._endpoint,
                            defaults.httpAboutCategoryName,
                            urllib.quote(about, safe=''))
        headers = Headers({'accept': ['application/json']})
        agent = Agent(reactor)
        response = yield agent.request('GET', URI, headers)
        self.assertEqual(http.OK, response.code)
        d = defer.Deferred()
        bodyGetter = ResponseGetter(d)
        response.deliverBody(bodyGetter)
        body = yield d
        j = json.loads(body)
        objectId2 = j['id']

        self.assertEqual(objectId1, objectId2)

    @defer.inlineCallbacks
    def testTagValueFromAbout(self):
        """
        A GET on /about/xxx/namespace/tag where xxx is the fluiddb/about tag of
        an object and namespace/tag is the path of the tag we want to get its
        value.
        """

        creds = _getCreds()
        endpoint = Endpoint(self._endpoint, creds=creds)

        about = 'testTagValueFromAbout'
        value = 'value'

        # First, we create an object and attach a tag to it.
        object = yield Object.create(endpoint, about)
        tag = Tag(u'fluiddb', u'testing', u'test1')
        yield object.set(endpoint, tag, value)

        try:
            URI = '{endpoint}/about/{value}/{tag}'
            URI = URI.format(endpoint=self._endpoint, value=about,
                             tag='fluiddb/testing/test1')
            headers = Headers({'authorization': [creds.encode()]})
            agent = Agent(reactor)
            response = yield agent.request('GET', URI, headers)
            self.assertEqual(response.code, http.OK)
            d = defer.Deferred()
            bodyGetter = ResponseGetter(d)
            response.deliverBody(bodyGetter)
            body = yield d
            self.assertEqual(json.loads(body), value)
        finally:
            yield object.delete(endpoint, tag)
