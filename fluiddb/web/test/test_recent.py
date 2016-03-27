from uuid import uuid4
import json

from twisted.internet.defer import inlineCallbacks
from twisted.web import http

from fluiddb.api.facade import Facade
from fluiddb.application import FluidinfoSessionFactory
from fluiddb.common.error import MissingArgument
from fluiddb.common.types_thrift.ttypes import TNoSuchUser
from fluiddb.data.system import createSystemData
from fluiddb.model.object import ObjectAPI
from fluiddb.model.user import UserAPI, getUser
from fluiddb.model.value import TagValueAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.doubles import FakeRequest
from fluiddb.testing.resources import (
    CacheResource, ConfigResource, LoggingResource, DatabaseResource,
    ThreadPoolResource, IndexResource)
from fluiddb.testing.solr import runDataImportHandler
from fluiddb.testing.session import login
from fluiddb.util.transact import Transact
from fluiddb.web.recent import (
    RecentActivityResource, RecentObjectActivityResource,
    RecentAboutActivityResource, RecentUserActivityResource,
    RecentObjectsActivityResource, RecentUsersActivityResource)
from fluiddb.web.resource import NoResource


class RecentActivityResourceTest(FluidinfoTestCase):

    resources = [('log', LoggingResource())]

    def testGetChildForObjects(self):
        """
        L{RecentActivityResource.getChild} returns a
        L{RecentObjectsActivityResource} to handle C{recent/objects} requests.
        """
        resource = RecentActivityResource(None, None)
        objectID = '751ba46f-2f27-4ec3-9271-ff032bd60240'
        request = FakeRequest(postpath=[objectID])
        leafResource = resource.getChild('objects', request)
        self.assertIsInstance(leafResource, RecentObjectsActivityResource)

    def testGetChildForAbout(self):
        """
        L{RecentActivityResource.getChild} returns a
        L{RecentAboutActivityResource} to handle C{recent/about} requests.
        """
        resource = RecentActivityResource(None, None)
        about = 'about'
        request = FakeRequest(postpath=[about])
        leafResource = resource.getChild('about', request)
        self.assertIsInstance(leafResource, RecentAboutActivityResource)
        self.assertEqual(about, leafResource.about)

    def testGetChildForUsers(self):
        """
        L{RecentActivityResource.getChild} returns a
        L{RecentUsersActivityResource} to handle C{recent/users} requests.
        """
        resource = RecentActivityResource(None, None)
        username = 'user'
        request = FakeRequest(postpath=[username])
        leafResource = resource.getChild('users', request)
        self.assertIsInstance(leafResource, RecentUsersActivityResource)

    def testGetChildForItself(self):
        """
        L{RecentActivityResource.getChild} returns itself for requests without
        name.
        """
        resource = RecentActivityResource(None, None)
        request = FakeRequest(postpath=[])
        leafResource = resource.getChild('', request)
        self.assertIsInstance(leafResource, RecentActivityResource)

    def testGetChildForNone(self):
        """
        L{RecentActivityResource.getChild} returns a
        L{NoResource} for any other requests.
        """
        resource = RecentActivityResource(None, None)
        request = FakeRequest(postpath=[])
        leafResource = resource.getChild('invalid', request)
        self.assertIsInstance(leafResource, NoResource)


class RecentObjectsActivityResourceTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('client', IndexResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(RecentObjectsActivityResourceTest, self).setUp()
        createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        factory = FluidinfoSessionFactory('API-9000')
        self.transact = Transact(self.threadPool)
        self.facade = Facade(self.transact, factory)

    @inlineCallbacks
    def testRenderRecentObjectsActivity(self):
        """
        L{RecentObjectsActivityResource.deferred_render_GET} renders a response
        with recent activity data for the objects returned by the given query.
        """
        objectID = ObjectAPI(self.user).create(u'object1')
        self.store.commit()
        TagValueAPI(self.user).set({objectID: {u'username/tag1': u'A'}})
        runDataImportHandler(self.client.url)
        request = FakeRequest(args={'query': ['has username/tag1']})
        with login(u'username', self.user.objectID, self.transact) as session:
            resource = RecentObjectsActivityResource(self.facade, session)
            body = yield resource.deferred_render_GET(request)
            body = json.loads(body)
            expected = [{u'username': u'username',
                         u'about': u'object1',
                         u'id': str(objectID),
                         u'tag': u'username/tag1',
                         u'value': u'A'},
                        {u'username': u'fluiddb',
                         u'about': u'object1',
                         u'id': str(objectID),
                         u'tag': u'fluiddb/about',
                         u'value': u'object1'}]
            # Clean up timestamps.
            for item in body:
                del item['updated-at']
            self.assertEqual(expected, body)
            self.assertEqual(http.OK, request.code)

    @inlineCallbacks
    def testRenderRecentObjectsActivityWithNoQuery(self):
        """
        L{RecentObjectsActivityResource.deferred_render_GET} raises
        L{MissingArgument} if the C{query} argument is not given.
        """
        objectID = ObjectAPI(self.user).create(u'object1')
        self.store.commit()
        TagValueAPI(self.user).set({objectID: {u'username/tag1': u'A'}})
        runDataImportHandler(self.client.url)
        request = FakeRequest()
        with login(u'username', self.user.objectID, self.transact) as session:
            resource = RecentObjectsActivityResource(self.facade, session)
            deferred = resource.deferred_render_GET(request)
            yield self.assertFailure(deferred, MissingArgument)

    def testGetChildForObjects(self):
        """
        L{RecentObjectsActivityResource.getChild} returns a
        L{RecentObjectActivityResource} to handle C{recent/objects/id}
        requests.
        """
        resource = RecentObjectsActivityResource(None, None)
        objectID = '751ba46f-2f27-4ec3-9271-ff032bd60240'
        request = FakeRequest(postpath=[objectID])
        leafResource = resource.getChild('objects', request)
        self.assertIsInstance(leafResource, RecentObjectActivityResource)

    def testGetChildForItself(self):
        """
        L{RecentObjetsActivityResource.getChild} returns itself for requests
        without name.
        """
        resource = RecentObjectsActivityResource(None, None)
        request = FakeRequest(postpath=[])
        leafResource = resource.getChild('', request)
        self.assertIsInstance(leafResource, RecentObjectsActivityResource)


class RecentObjectActivityResourceTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(RecentObjectActivityResourceTest, self).setUp()
        createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        factory = FluidinfoSessionFactory('API-9000')
        self.transact = Transact(self.threadPool)
        self.facade = Facade(self.transact, factory)

    @inlineCallbacks
    def testRenderRecentObjectActivity(self):
        """
        L{RecentObjectActivityResource.deferred_render_GET} renders a response
        with recent activity data for the given object.
        """
        objectID = ObjectAPI(self.user).create(u'object1')
        self.store.commit()
        TagValueAPI(self.user).set({objectID: {u'username/tag1': u'A'}})
        self.store.commit()
        request = FakeRequest()
        with login(u'username', self.user.objectID, self.transact) as session:
            resource = RecentObjectActivityResource(self.facade, session,
                                                    str(objectID))
            body = yield resource.deferred_render_GET(request)
            body = json.loads(body)
            expected = [{u'username': u'username',
                         u'about': u'object1',
                         u'id': str(objectID),
                         u'tag': u'username/tag1',
                         u'value': u'A'},
                        {u'username': u'fluiddb',
                         u'about': u'object1',
                         u'id': str(objectID),
                         u'tag': u'fluiddb/about',
                         u'value': u'object1'}]
            # Clean up timestamps.
            for item in body:
                del item['updated-at']
            self.assertEqual(expected, body)
            self.assertEqual(http.OK, request.code)

    @inlineCallbacks
    def testRenderRecentObjectActivityWithUnknownObject(self):
        """
        L{RecentObjectActivityResource.deferred_render_GET} renders an empty
        list if the given object doesn't exist.
        """
        self.store.commit()
        request = FakeRequest()
        with login(u'username', self.user.objectID, self.transact) as session:
            resource = RecentObjectActivityResource(self.facade, session,
                                                    str(uuid4()))
            body = yield resource.deferred_render_GET(request)
            body = json.loads(body)
            self.assertEqual([], body)
            self.assertEqual(http.OK, request.code)


class RecentAboutActivityResourceTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(RecentAboutActivityResourceTest, self).setUp()
        createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        factory = FluidinfoSessionFactory('API-9000')
        self.transact = Transact(self.threadPool)
        self.facade = Facade(self.transact, factory)

    @inlineCallbacks
    def testRenderRecentAboutActivity(self):
        """
        L{RecentAboutActivityResource.deferred_render_GET} renders a response
        with recent activity data for the given object.
        """
        objectID = ObjectAPI(self.user).create(u'object1')
        self.store.commit()
        TagValueAPI(self.user).set({objectID: {u'username/tag1': u'A'}})
        self.store.commit()
        request = FakeRequest()
        with login(u'username', self.user.objectID, self.transact) as session:
            resource = RecentAboutActivityResource(self.facade, session,
                                                   u'object1')
            body = yield resource.deferred_render_GET(request)
            body = json.loads(body)
            expected = [{u'username': u'username',
                         u'about': u'object1',
                         u'id': str(objectID),
                         u'tag': u'username/tag1',
                         u'value': u'A'},
                        {u'username': u'fluiddb',
                         u'about': u'object1',
                         u'id': str(objectID),
                         u'tag': u'fluiddb/about',
                         u'value': u'object1'}]
            # Clean up timestamps.
            for item in body:
                del item['updated-at']
            self.assertEqual(expected, body)
            self.assertEqual(http.OK, request.code)

    @inlineCallbacks
    def testRenderRecentAboutActivityWithNonexistentAboutValue(self):
        """
        L{RecentAboutActivityResource.deferred_render_GET} renders an empty
        list if the given object doesn't exist.
        """
        self.store.commit()
        request = FakeRequest()
        with login(u'username', self.user.objectID, self.transact) as session:
            resource = RecentAboutActivityResource(self.facade, session,
                                                   u'unknown')
            body = yield resource.deferred_render_GET(request)
            body = json.loads(body)
            self.assertEqual([], body)
            self.assertEqual(http.OK, request.code)


class RecentUsersActivityResourceTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('client', IndexResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(RecentUsersActivityResourceTest, self).setUp()
        createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        factory = FluidinfoSessionFactory('API-9000')
        self.transact = Transact(self.threadPool)
        self.facade = Facade(self.transact, factory)

    @inlineCallbacks
    def testRenderRecentUsersActivity(self):
        """
        L{RecentUsersActivityResource.deferred_render_GET} renders a response
        with recent activity data by the users returned by the given query.
        """
        objectID = ObjectAPI(self.user).create(u'object1')
        self.store.commit()
        TagValueAPI(self.user).set({objectID: {u'username/tag1': u'A'}})
        runDataImportHandler(self.client.url)
        request = FakeRequest(
            args={'query': ['fluiddb/users/username = "username"']})
        with login(u'username', self.user.objectID, self.transact) as session:
            resource = RecentUsersActivityResource(self.facade, session)
            body = yield resource.deferred_render_GET(request)
            body = json.loads(body)
            expected = [{u'about': u'object1',
                         u'id': str(objectID),
                         u'tag': u'username/tag1',
                         u'username': u'username',
                         u'value': u'A'}]
            # Clean up timestamps.
            for item in body:
                del item['updated-at']
            self.assertEqual(expected, body)
            self.assertEqual(http.OK, request.code)

    @inlineCallbacks
    def testRenderRecentObjectActivityWithNoQuery(self):
        """
        L{RecentUsersActivityResource.deferred_render_GET} raises
        L{MissingArgument} if the C{query} argument is not given.
        """
        objectID = ObjectAPI(self.user).create(u'object1')
        self.store.commit()
        TagValueAPI(self.user).set({objectID: {u'username/tag1': u'A'}})
        runDataImportHandler(self.client.url)
        request = FakeRequest()
        with login(u'username', self.user.objectID, self.transact) as session:
            resource = RecentUsersActivityResource(self.facade, session)
            deferred = resource.deferred_render_GET(request)
            yield self.assertFailure(deferred, MissingArgument)

    def testGetChildForUsers(self):
        """
        L{RecentUsersActivityResource.getChild} returns a
        L{RecentUserActivityResource} to handle C{recent/objects/id}
        requests.
        """
        resource = RecentUsersActivityResource(None, None)
        objectID = '751ba46f-2f27-4ec3-9271-ff032bd60240'
        request = FakeRequest(postpath=[objectID])
        leafResource = resource.getChild('users', request)
        self.assertIsInstance(leafResource, RecentUserActivityResource)

    def testGetChildForItself(self):
        """
        L{RecentUsersActivityResource.getChild} returns itself for requests
        without name.
        """
        resource = RecentUsersActivityResource(None, None)
        request = FakeRequest(postpath=[])
        leafResource = resource.getChild('', request)
        self.assertIsInstance(leafResource, RecentUsersActivityResource)


class RecentUserActivityResourceTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(RecentUserActivityResourceTest, self).setUp()
        createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        factory = FluidinfoSessionFactory('API-9000')
        self.transact = Transact(self.threadPool)
        self.facade = Facade(self.transact, factory)

    @inlineCallbacks
    def testRenderRecentUserActivity(self):
        """
        L{RecentUserActivityResource.deferred_render_GET} renders a response
        with recent activity data for the given user.
        """
        objectID = ObjectAPI(self.user).create(u'object1')
        TagValueAPI(self.user).set({objectID: {u'username/tag1': u'A'}})
        self.store.commit()
        TagValueAPI(self.user).set({objectID: {u'username/tag2': u'B'}})
        self.store.commit()
        request = FakeRequest()
        with login(u'username', self.user.objectID, self.transact) as session:
            resource = RecentUserActivityResource(self.facade, session,
                                                  u'username')
            body = yield resource.deferred_render_GET(request)
            body = json.loads(body)
            expected = [{u'username': u'username',
                         u'about': u'object1',
                         u'id': str(objectID),
                         u'tag': u'username/tag2',
                         u'value': u'B'},
                        {u'username': u'username',
                         u'about': u'object1',
                         u'id': str(objectID),
                         u'tag': u'username/tag1',
                         u'value': u'A'}]
            # Clean up timestamps.
            for item in body:
                del item['updated-at']
            self.assertEqual(expected, body)
            self.assertEqual(http.OK, request.code)

    @inlineCallbacks
    def testRenderRecentAboutActivityWithUnknownAbout(self):
        """
        L{RecentUserActivityResource.deferred_render_GET} raises L{TNoSuchUser}
        if the given user doesn't exist.
        """
        self.store.commit()
        request = FakeRequest()
        with login(u'username', self.user.objectID, self.transact) as session:
            resource = RecentUserActivityResource(self.facade, session,
                                                  u'unknown')
            deferred = resource.deferred_render_GET(request)
            yield self.assertFailure(deferred, TNoSuchUser)
