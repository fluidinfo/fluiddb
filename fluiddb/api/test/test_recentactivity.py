from fluiddb.api.facade import Facade
from fluiddb.application import FluidinfoSessionFactory
from uuid import uuid4

from twisted.internet.defer import inlineCallbacks

from fluiddb.cache.permission import CachingPermissionAPI
from fluiddb.common.types_thrift.ttypes import (
    TNoSuchUser, TParseError, TBadRequest)
from fluiddb.data.system import createSystemData
from fluiddb.model.object import ObjectAPI
from fluiddb.model.user import UserAPI, getUser
from fluiddb.model.value import TagValueAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    CacheResource, ConfigResource, LoggingResource, DatabaseResource,
    ThreadPoolResource, IndexResource)
from fluiddb.testing.session import login
from fluiddb.testing.solr import runDataImportHandler
from fluiddb.util.transact import Transact


class FacadeRecentActivityMixinTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('client', IndexResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(FacadeRecentActivityMixinTest, self).setUp()
        self.system = createSystemData()
        self.transact = Transact(self.threadPool)
        factory = FluidinfoSessionFactory('API-9000')
        self.facade = Facade(self.transact, factory)
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.permissions = CachingPermissionAPI(self.user)

    @inlineCallbacks
    def testGetRecentObjectActivity(self):
        """
        L{FacadeRecentActivityMixin.getRecentObjectActivity} returns a C{dict}
        with information about the recent tag values on the given object.
        """
        tagValues = TagValueAPI(self.user)
        objectID1 = ObjectAPI(self.user).create(u'object1')
        objectID2 = uuid4()

        # Use commit() frequently to have different timestamps on each value.
        self.store.commit()
        tagValues.set({objectID1: {u'user/tag1': u'A'}})
        self.store.commit()
        tagValues.set({objectID1: {u'user/tag2': u'B'}})
        self.store.commit()
        tagValues.set({objectID2: {u'user/tag1': u'C'}})
        self.store.commit()
        tagValues.set({objectID2: {u'user/tag2': u'D'}})
        self.store.commit()
        tagValues.set({uuid4(): {u'user/tag1': u'E'}})
        self.store.commit()
        tagValues.set({uuid4(): {u'user/tag2': u'F'}})
        self.store.commit()

        expected = [
            {'tag': u'user/tag2',
             'id': str(objectID1),
             'about': u'object1',
             'value': u'B',
             'username': u'username'},

            {'tag': u'user/tag1',
             'id': str(objectID1),
             'about': u'object1',
             'value': u'A',
             'username': u'username'},

            {'tag': u'fluiddb/about',
             'id': str(objectID1),
             'about': u'object1',
             'value': u'object1',
             'username': u'fluiddb'}]

        with login(self.user.username, uuid4(), self.transact) as session:
            result = yield self.facade.getRecentObjectActivity(
                session, str(objectID1))

            # Remove the creation times from the result.
            for item in result:
                del item['updated-at']

            self.assertEqual(expected, result)

    @inlineCallbacks
    def testGetRecentAboutActivity(self):
        """
        L{FacadeRecentActivityMixin.getRecentAboutActivity} returns a C{dict}
        with information about the recent tag values on the given object.
        """
        tagValues = TagValueAPI(self.user)
        objectID1 = ObjectAPI(self.user).create(u'object1')
        objectID2 = uuid4()

        # Use commit() frequently to have different timestamps on each value.
        self.store.commit()
        tagValues.set({objectID1: {u'user/tag1': u'A'}})
        self.store.commit()
        tagValues.set({objectID1: {u'user/tag2': u'B'}})
        self.store.commit()
        tagValues.set({objectID2: {u'user/tag1': u'C'}})
        self.store.commit()
        tagValues.set({objectID2: {u'user/tag2': u'D'}})
        self.store.commit()
        tagValues.set({uuid4(): {u'user/tag1': u'E'}})
        self.store.commit()
        tagValues.set({uuid4(): {u'user/tag2': u'F'}})
        self.store.commit()

        expected = [
            {'tag': u'user/tag2',
             'id': str(objectID1),
             'about': u'object1',
             'value': u'B',
             'username': u'username'},

            {'tag': u'user/tag1',
             'id': str(objectID1),
             'about': u'object1',
             'value': u'A',
             'username': u'username'},

            {'tag': u'fluiddb/about',
             'id': str(objectID1),
             'about': u'object1',
             'value': u'object1',
             'username': u'fluiddb'}]

        with login(self.user.username, uuid4(), self.transact) as session:
            result = yield self.facade.getRecentAboutActivity(
                session, 'object1')

            # Remove the creation times from the result.
            for item in result:
                del item['updated-at']

            self.assertEqual(expected, result)

    @inlineCallbacks
    def testGetRecentAboutActivityWithUnkownAboutValue(self):
        """
        L{FacadeRecentActivityMixin.getRecentAboutActivity} returns an empty
        C{list} if the about value doesn't exist.
        """
        with login(self.user.username, uuid4(), self.transact) as session:
            result = yield self.facade.getRecentAboutActivity(session,
                                                              'unknown')
            self.assertEqual([], result)

    @inlineCallbacks
    def testGetRecentUserActivity(self):
        """
        L{FacadeRecentActivityMixin.getRecentUserActivity} returns a C{dict}
        with information about the recent tag values on the given user.
        """
        tagValues = TagValueAPI(self.user)
        objectID1 = ObjectAPI(self.user).create(u'object1')
        objectID2 = uuid4()

        # Use commit() frequently to have different timestamps on each value.
        self.store.commit()
        tagValues.set({objectID1: {u'user/tag1': u'A'}})
        self.store.commit()
        tagValues.set({objectID1: {u'user/tag2': u'B'}})
        self.store.commit()

        UserAPI().create([(u'user2', u'secret', u'User', u'user@example.com')])
        tagValues = TagValueAPI(getUser(u'user2'))

        tagValues.set({objectID1: {u'user2/tag1': u'C'}})
        self.store.commit()
        tagValues.set({objectID2: {u'user2/tag2': u'D'}})
        self.store.commit()

        UserAPI().create([(u'user3', u'secret', u'User', u'user@example.com')])
        tagValues = TagValueAPI(getUser(u'user3'))

        tagValues.set({objectID1: {u'user3/tag1': u'C'}})
        self.store.commit()
        tagValues.set({objectID2: {u'user3/tag2': u'D'}})
        self.store.commit()

        expected = [
            {'tag': u'user/tag2',
             'id': str(objectID1),
             'about': u'object1',
             'value': u'B',
             'username': u'username'},

            {'tag': u'user/tag1',
             'id': str(objectID1),
             'about': u'object1',
             'value': u'A',
             'username': u'username'}]

        with login(self.user.username, uuid4(), self.transact) as session:
            result = yield self.facade.getRecentUserActivity(
                session, self.user.username.encode('utf-8'))
            # Remove the creation times from the result.
            for item in result:
                del item['updated-at']
            self.assertEqual(expected, result)

    @inlineCallbacks
    def testGetRecentUserActivityWithUnkownUser(self):
        """
        L{FacadeRecentActivityMixin.getRecentUserActivity} raises
        L{TNoSuchUser} if the given user doesn't exist.
        """
        with login(self.user.username, uuid4(), self.transact) as session:
            result = self.facade.getRecentUserActivity(session, 'unknown')
            yield self.assertFailure(result, TNoSuchUser)

    @inlineCallbacks
    def testGetRecentActivityForQuery(self):
        """
        L{FacadeRecentActivityMixin.getRecentActivityForQuery} returns a
        C{dict} with information about the recent tag values on the objects
        returned by the given query.
        """
        tagValues = TagValueAPI(self.user)
        objectID1 = ObjectAPI(self.user).create(u'object1')

        # Use commit() frequently to have different timestamps on each value.
        self.store.commit()
        tagValues.set({objectID1: {u'user/following': u'A'}})
        self.store.commit()

        runDataImportHandler(self.client.url)

        expected = [{'about': u'object1',
                     'id': str(objectID1),
                     'tag': u'user/following',
                     'username': u'username',
                     'value': u'A'},
                    {'about': u'object1',
                     'id': str(objectID1),
                     'tag': u'fluiddb/about',
                     'username': u'fluiddb',
                     'value': u'object1'}]

        with login(self.user.username, uuid4(), self.transact) as session:
            result = yield self.facade.getRecentActivityForQuery(
                session, u'has user/following')

            # Remove the creation times from the result.
            for item in result:
                del item['updated-at']

            self.assertEqual(expected, result)

    @inlineCallbacks
    def testGetRecentActivityForQueryWithBadQuery(self):
        """
        L{FacadeRecentActivityMixin.getRecentActivityForQuery} raises
        L{TParseError} if the given query can't be parsed.
        """
        with login(self.user.username, uuid4(), self.transact) as session:
            result = self.facade.getRecentActivityForQuery(session, 'bad')
            yield self.assertFailure(result, TParseError)

    @inlineCallbacks
    def testGetRecentActivityForQueryWithIllegalQuery(self):
        """
        L{FacadeRecentActivityMixin.getRecentActivityForQuery} raises
        L{TBadRequest} if the given query contains illegal sub queries.
        """
        with login(self.user.username, uuid4(), self.transact) as session:
            result = self.facade.getRecentActivityForQuery(
                session, 'has fluiddb/about')
            yield self.assertFailure(result, TBadRequest)

    @inlineCallbacks
    def testGetRecentUserActivityForQuery(self):
        """
        L{FacadeRecentActivityMixin.getRecentUserActivityForQuery} returns a
        C{dict} with information about the recent tag values by the users whose
        objects are returned by the given query.
        """
        UserAPI().create([(u'user2', u'password', u'User',
                           u'use2r@example.com')])
        user2 = getUser(u'user2')

        objectID1 = uuid4()

        # Use commit() frequently to have different timestamps on each value.
        TagValueAPI(self.user).set({objectID1: {u'username/test': u'A'}})
        self.store.commit()
        TagValueAPI(user2).set({objectID1: {u'user2/test': u'B'}})
        self.store.commit()

        runDataImportHandler(self.client.url)

        expected = [{'about': None,
                     'id': str(objectID1),
                     'tag': u'user2/test',
                     'username': u'user2',
                     'value': u'B'},
                    {'about': None,
                     'id': str(objectID1),
                     'tag': u'username/test',
                     'username': u'username',
                     'value': u'A'}]

        with login(self.user.username, uuid4(), self.transact) as session:
            result = yield self.facade.getRecentUserActivityForQuery(
                session,
                u'fluiddb/users/username = "username" '
                'OR fluiddb/users/username = "user2"')

            # Remove the creation times from the result.
            for item in result:
                del item['updated-at']

            self.assertEqual(expected, result)

    @inlineCallbacks
    def testGetRecentUserActivityForQueryWithBadQuery(self):
        """
        L{FacadeRecentActivityMixin.getRecentUserActivityForQuery} raises
        L{TParseError} if the given query can't be parsed.
        """
        with login(self.user.username, uuid4(), self.transact) as session:
            result = self.facade.getRecentUserActivityForQuery(session, 'bad')
            yield self.assertFailure(result, TParseError)

    @inlineCallbacks
    def testGetRecentUserActivityForQueryWithIllegalQuery(self):
        """
        L{FacadeRecentActivityMixin.getRecentUserActivityForQuery} raises
        L{TBadRequest} if the given query contains illegal sub queries.
        """
        with login(self.user.username, uuid4(), self.transact) as session:
            result = self.facade.getRecentUserActivityForQuery(
                session, 'has fluiddb/about')
            yield self.assertFailure(result, TBadRequest)

    @inlineCallbacks
    def testGetRecentUserActivityForQueryWithObjectsNotUsers(self):
        """
        L{FacadeRecentActivityMixin.getRecentUserActivityForQuery} returns an
        empty result if the objects returned by the query are not users.
        """
        tagValues = TagValueAPI(self.user)
        objectID1 = ObjectAPI(self.user).create(u'object1')

        # Use commit() frequently to have different timestamps on each value.
        self.store.commit()
        tagValues.set({objectID1: {u'user/following': u'A'}})
        self.store.commit()

        runDataImportHandler(self.client.url)

        with login(self.user.username, uuid4(), self.transact) as session:
            result = yield self.facade.getRecentUserActivityForQuery(
                session, u'has user/following')

            # Remove the creation times from the result.
            for item in result:
                del item['updated-at']

            self.assertEqual([], result)
