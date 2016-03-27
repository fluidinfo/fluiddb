import json

from twisted.internet import defer

from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.doubles import FakeRequest, FakeSession
from fluiddb.web.query import createThriftValue
from fluiddb.web.objects import TagInstanceResource
from fluiddb.web.util import buildHeader


class FakeFacade(object):
    """
    Simple dummy version of the L{FacadeHandler}. It implements only one
    method: C{getTagInstance} which return an item from a pre-defined values
    dict.
    """
    def __init__(self):
        self.values = {}

    def getTagInstance(self, session, path, objectId):
        """
        Returns an object previously stored in C{values}.
        """
        tvalue = createThriftValue(self.values[objectId][path])
        return defer.succeed((tvalue, None))

    def resolveQuery(self, session, query):
        """
        Resolves a simple tag = "..." query.
        """
        path, value = query.split('=')
        path = path.strip()
        value = value.strip().strip('"')
        objectIds = [k for k, v in self.values.items()
                     if v[path] == value]
        return defer.succeed(objectIds)


class TagInstanceResourceTest(FluidinfoTestCase):

    @defer.inlineCallbacks
    def assertXFluidDBHeaderForType(self, method, value, expectedTypeString):
        """
        Helper method to check if a resource is returning the appropriate
        C{X-FluidDB-Type} header for a given HTTP method.

        @param method: The HTTP method to use. Should be 'GET' or 'HEAD'.
        @param value: The value to test.
        @param expectedTypeString: The expected string that should be returned
            by C{X-FluidDB-Type}.
        """
        facadeClient = FakeFacade()
        session = FakeSession()

        # Tell our FakeFacade to preload some data for a given tag.
        facadeClient.values = {
            'fe2f50c8-997f-4049-a180-9a37543d001d': {
                'tag/test': value}}

        resource = TagInstanceResource(facadeClient, session,
                                       'fe2f50c8-997f-4049-a180-9a37543d001d',
                                       'tag/test')

        request = FakeRequest(method=method)
        yield getattr(resource, 'render_' + method)(request)
        typeValue = request.getResponseHeader(buildHeader('Type'))
        self.assertEqual(expectedTypeString, typeValue)

    @defer.inlineCallbacks
    def testGETListValuesPreserveOrder(self):
        """
        List values get via GET on /objects preserve the same order of the
        original value.
        """
        facadeClient = FakeFacade()
        session = FakeSession()

        # Tell our FakeFacade to preload some data for a given tag.
        facadeClient.values = {
            'fe2f50c8-997f-4049-a180-9a37543d001d': {
                'tag/test': ['x', 'y', 'z', 'a', 'b', 'c']}}

        resource = TagInstanceResource(facadeClient, session,
                                       'fe2f50c8-997f-4049-a180-9a37543d001d',
                                       'tag/test')

        request = FakeRequest(method='GET')
        body = yield resource.deferred_render_GET(request)
        value = json.loads(body)
        self.assertEqual(['x', 'y', 'z', 'a', 'b', 'c'], value)

    def testRequestReturnsTypeHeaderFloat(self):
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
        return self.assertXFluidDBHeaderForType('HEAD', 13, 'int')

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
        return self.assertXFluidDBHeaderForType('GET', 'hello', 'string')

    def testGETRequestReturnsTypeHeaderInt(self):
        """
        L{TagInstanceResource.render_GET} should put an X-FluidDB-Type header
        indicating the type of the value that it's returning. This tests
        checks the int type.
        """
        return self.assertXFluidDBHeaderForType('GET', 22, 'int')

    def testGETRequestReturnsTypeHeaderList(self):
        """
        L{TagInstanceResource.render_GET} should put an X-FluidDB-Type header
        indicating the type of the value that it's returning. This tests
        checks the set type.
        """
        return self.assertXFluidDBHeaderForType('GET', ['three', 'four'],
                                                'list-of-strings')
