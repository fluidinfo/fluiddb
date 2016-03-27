from uuid import uuid4

from twisted.internet.defer import inlineCallbacks

from fluiddb.cache.permission import CachingPermissionAPI
from fluiddb.cache.test.test_object import CachingObjectAPITestMixin
from fluiddb.data.permission import Operation, Policy
from fluiddb.data.system import createSystemData
from fluiddb.model.exceptions import UnknownPathError
from fluiddb.model.object import ObjectIndex
from fluiddb.model.tag import TagAPI
from fluiddb.model.test.test_object import ObjectAPITestMixin
from fluiddb.model.user import UserAPI, getUser
from fluiddb.query.parser import parseQuery
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.security.object import SecureObjectAPI
from fluiddb.security.value import SecureTagValueAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    BrokenCacheResource, CacheResource, ConfigResource, DatabaseResource,
    IndexResource, LoggingResource)


class SecureObjectAPITestMixin(object):

    def testSearchWithUnknownPaths(self):
        """
        L{ObjectAPI.set} raises an L{UnknownPathError} if a path for unknown
        L{Tag}s is in the Query.
        """
        query = parseQuery(u'unknown/path = "hello world"')
        error = self.assertRaises(UnknownPathError,
                                  self.objects.search, [query])
        self.assertEqual([u'unknown/path'], error.paths)


class SecureObjectAPITest(ObjectAPITestMixin, CachingObjectAPITestMixin,
                          SecureObjectAPITestMixin, FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('client', IndexResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureObjectAPITest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'user', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'user')
        self.objects = SecureObjectAPI(self.user)


class SecureObjectAPIWithBrokenCacheTest(ObjectAPITestMixin,
                                         SecureObjectAPITestMixin,
                                         FluidinfoTestCase):

    resources = [('cache', BrokenCacheResource()),
                 ('client', IndexResource()),
                 ('config', ConfigResource()),
                 ('log', LoggingResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureObjectAPIWithBrokenCacheTest, self).setUp()
        self.system = createSystemData()
        UserAPI().create([(u'user', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'user')
        self.objects = SecureObjectAPI(self.user)


class SecureObjectAPIWithAnonymousRoleTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('client', IndexResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureObjectAPIWithAnonymousRoleTest, self).setUp()
        system = createSystemData()
        self.anon = system.users[u'anon']
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        self.tags = TagAPI(self.user)
        self.tags.create([(u'username/tag', u'description')])
        self.permissions = CachingPermissionAPI(self.user)
        self.objects = SecureObjectAPI(self.anon)

    def testCreateIsDenied(self):
        """
        L{SecureObjectAPI.create} raises a L{PermissionDeniedError} if it's
        invoked by a L{User} with the L{Role.ANONYMOUS}.
        """
        objects = SecureObjectAPI(self.anon)
        error = self.assertRaises(PermissionDeniedError, objects.create)
        self.assertEqual(self.anon.username, error.username)
        self.assertEqual([(None, Operation.CREATE_OBJECT)],
                         error.pathsAndOperations)

    def testGetTagsByObjectsPathIsAllowed(self):
        """
        L{SecureObjectAPI.getTagsByObjects} will return all the tags for
        which the anonymous user has C{Operation.READ_TAG_VALUE} permissions.
        """
        objectID = uuid4()
        values = {objectID: {u'username/tag': 16}}
        SecureTagValueAPI(self.user).set(values)
        self.permissions.set([(u'username/tag', Operation.READ_TAG_VALUE,
                               Policy.OPEN, [])])
        self.assertEqual({objectID: [u'username/tag']},
                         self.objects.getTagsByObjects([objectID]))

    def testGetTagsByObjectsReturnsOnlyAllowedTags(self):
        """
        L{SecureObjectAPI.getTagsByObjects} will return all the tags for
        which the anonymous user has C{Operation.READ_TAG_VALUE} permissions,
        but not those for which the user doesn't have.
        """
        self.tags.create([(u'username/tag1', u'description'),
                          (u'username/tag2', u'description')])
        objectID = uuid4()

        values = {objectID: {u'username/tag1': 16,
                             u'username/tag2': 16}}
        SecureTagValueAPI(self.user).set(values)

        self.permissions.set([(u'username/tag1', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, []),
                              (u'username/tag2', Operation.READ_TAG_VALUE,
                               Policy.OPEN, [])])

        result = self.objects.getTagsByObjects([objectID])
        expected = {objectID: [u'username/tag2']}
        self.assertEqual(expected, result)

    def testGetTagsByObjectsReturnsNoneIfDenied(self):
        """
        L{SecureObjectAPI.getTagsByObjects} will return an empty C{dict} if
        the L{User} does not have C{Operation.READ_TAG_VALUE} permission on
        none of the L{Tag}s an object has.
        """
        self.tags.create([(u'username/tag1', u'description'),
                          (u'username/tag2', u'description')])
        objectID = uuid4()

        values = {objectID: {u'username/tag1': 16,
                             u'username/tag2': 16}}
        SecureTagValueAPI(self.user).set(values)

        self.permissions.set([(u'username/tag1', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, []),
                              (u'username/tag2', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, [])])

        result = self.objects.getTagsByObjects([objectID])
        self.assertEqual({}, result)

    def testGetTagsByObjectsWithCustomPermission(self):
        """
        L{SecureObjectAPI.getTagsByObjects} optionally accepts a permission
        type to check for instead of L{Operation.READ_TAG_VALUE}).
        """
        TagAPI(self.user).create([(u'username/open', u'An accessible tag'),
                                  (u'username/closed', u'A denied tag')])
        objectID = uuid4()
        SecureTagValueAPI(self.user).set({objectID: {u'username/open': 13,
                                                     u'username/closed': 17}})
        self.permissions.set([(u'username/closed', Operation.DELETE_TAG_VALUE,
                               Policy.CLOSED, [])])
        result = self.objects.getTagsByObjects(
            [objectID], permission=Operation.DELETE_TAG_VALUE)
        # Result is empty because anonymous users are never allowed to delete
        # values.
        self.assertEqual({}, result)

    def testGetTagsForObjectsOnlyReturnsAccessibleTags(self):
        """
        L{SecureObjectAPI.getTagsForObjects} only returns L{Tag.path}s that
        the user has C{Operation.READ_TAG_VALUE} permissions for.
        """
        TagAPI(self.user).create([(u'username/tag1', u'description'),
                                  (u'username/tag2', u'description')])
        objectID = uuid4()
        SecureTagValueAPI(self.user).set({objectID: {u'username/tag1': 13,
                                                     u'username/tag2': 17}})
        self.permissions.set([(u'username/tag2', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, [])])
        self.assertEqual([u'username/tag1'],
                         self.objects.getTagsForObjects([objectID]))

    @inlineCallbacks
    def testSearch(self):
        """
        L{SecureObjectAPI.search} resolves the specified L{Query}s if the
        anonymous user has C{Operation.READ_TAG_VALUE} permissions on the
        requested L{Tag.path}s.
        """
        objectID = uuid4()
        index = ObjectIndex(self.client)
        yield index.update({objectID: {u'username/tag': 42}})
        yield self.client.commit()
        query = parseQuery(u'username/tag = 42')
        result = self.objects.search([query])
        result = yield result.get()
        self.assertEqual({query: set([objectID])}, result)

    @inlineCallbacks
    def testSearchWithoutPermission(self):
        """
        L{SecureObjectAPI.search} raises a L{PermissionDeniedError} if the
        anonymous user doesn't have C{Operation.READ_TAG_VALUE} permissions on
        the requested L{Tag.path}s.
        """
        objectID = uuid4()
        index = ObjectIndex(self.client)
        yield index.update({objectID: {u'username/tag': 42}})
        yield self.client.commit()
        self.permissions.set([(u'username/tag', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, [])])
        query = parseQuery(u'username/tag = 42')
        error = self.assertRaises(PermissionDeniedError, self.objects.search,
                                  [query])
        self.assertEqual(u'anon', error.username)
        self.assertEqual([('username/tag', Operation.READ_TAG_VALUE)],
                         error.pathsAndOperations)

    @inlineCallbacks
    def testSearchWithImplicitObjectCreation(self):
        """
        L{SecureObjectAPI.search} doesn't raise a L{PermissionDeniedError} if
        the anonymous user tries to create new objects using C{fluiddb/about}
        queries, instead an empty result is returned.
        """
        query = parseQuery(u'fluiddb/about = "TestObject"')
        result = self.objects.search([query], True)
        result = yield result.get()
        self.assertEqual({query: set()}, result)


class SecureObjectAPIWithUserRoleTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureObjectAPIWithUserRoleTest, self).setUp()
        createSystemData()
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])
        self.user = getUser(u'username')
        TagAPI(self.user).create([(u'username/tag', u'description')])
        self.permissions = CachingPermissionAPI(self.user)
        self.objects = SecureObjectAPI(self.user)

    def testGetTagsByObjectsPathIsAllowed(self):
        """
        L{SecureObjectAPI.getTagsByObjects} will return all the tags for
        which the user has C{Operation.READ_TAG_VALUE} permissions.
        """
        objectID = uuid4()
        values = {objectID: {u'username/tag': 16}}
        SecureTagValueAPI(self.user).set(values)
        self.permissions.set([(u'username/tag', Operation.READ_TAG_VALUE,
                               Policy.OPEN, [])])
        result = self.objects.getTagsByObjects([objectID])
        expected = {objectID: [u'username/tag']}
        self.assertEqual(expected, result)

    def testGetTagsByObjectsReturnsOnlyAllowedTags(self):
        """
        L{SecureObjectAPI.getTagsByObjects} will return all the tags for
        which the user has C{Operation.READ_TAG_VALUE} permissions, but not
        those for which the user doesn't have.
        """
        TagAPI(self.user).create([(u'username/tag1', u'description'),
                                  (u'username/tag2', u'description')])
        objectID = uuid4()
        values = {objectID: {u'username/tag1': 16,
                             u'username/tag2': 16}}
        SecureTagValueAPI(self.user).set(values)
        self.permissions.set([(u'username/tag1', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, []),
                              (u'username/tag2', Operation.READ_TAG_VALUE,
                               Policy.OPEN, [])])

        result = self.objects.getTagsByObjects([objectID])
        expected = {objectID: [u'username/tag2']}
        self.assertEqual(expected, result)

    def testGetTagsByObjectsReturnsNoneAllowedTags(self):
        """
        L{SecureObjectAPI.getTagsByObjects} will return all the tags for
        which the user has C{Operation.READ_TAG_VALUE} permissions, but not
        those for which the user doesn't have.
        """
        TagAPI(self.user).create([(u'username/tag1', u'description'),
                                  (u'username/tag2', u'description')])
        objectID = uuid4()
        values = {objectID: {u'username/tag1': 16,
                             u'username/tag2': 16}}
        SecureTagValueAPI(self.user).set(values)
        self.permissions.set([(u'username/tag1', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, []),
                              (u'username/tag2', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, [])])

        result = self.objects.getTagsByObjects([objectID])
        self.assertEqual({}, result)

    def testGetTagsByObjectsWithCustomPermission(self):
        """
        L{SecureObjectAPI.getTagsByObjects} optionally accepts a permission
        type to check for instead of L{Operation.READ_TAG_VALUE}).
        """
        TagAPI(self.user).create([(u'username/open', u'An accessible tag'),
                                  (u'username/closed', u'A denied tag')])
        objectID = uuid4()
        SecureTagValueAPI(self.user).set({objectID: {u'username/open': 13,
                                                     u'username/closed': 17}})
        self.permissions.set([(u'username/closed', Operation.DELETE_TAG_VALUE,
                               Policy.CLOSED, [])])
        result = self.objects.getTagsByObjects(
            [objectID], permission=Operation.DELETE_TAG_VALUE)
        self.assertEqual({objectID: [u'username/open']}, result)

    def testGetTagsForObjectsOnlyReturnsAccessibleTags(self):
        """
        L{SecureObjectAPI.getTagsForObjects} only returns L{Tag.path}s that
        the user has C{Operation.READ_TAG_VALUE} permissions for.
        """
        TagAPI(self.user).create([(u'username/tag1', u'description'),
                                  (u'username/tag2', u'description')])
        objectID = uuid4()
        SecureTagValueAPI(self.user).set({objectID: {u'username/tag1': 13,
                                                     u'username/tag2': 17}})
        self.permissions.set([(u'username/tag2', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, [])])
        self.assertEqual([u'username/tag1'],
                         self.objects.getTagsForObjects([objectID]))


class SecureObjectAPIWithSuperuserRoleTest(FluidinfoTestCase):

    resources = [('cache', CacheResource()),
                 ('config', ConfigResource()),
                 ('store', DatabaseResource())]

    def setUp(self):
        super(SecureObjectAPIWithSuperuserRoleTest, self).setUp()
        system = createSystemData()
        self.superuser = system.users[u'fluiddb']
        self.permissions = CachingPermissionAPI(self.superuser)
        self.objects = SecureObjectAPI(self.superuser)
        UserAPI().create([(u'username', u'password', u'User',
                           u'user@example.com')])

    def testGetTagsByObjectsIsAlwaysAllowed(self):
        """
        L{SecureObjectAPI.getTagsByObjects} is always allowed for the
        superuser.
        """
        TagAPI(self.superuser).create([(u'username/tag1', u'description'),
                                       (u'username/tag2', u'description')])
        objectID = uuid4()
        values = {objectID: {u'username/tag1': 16,
                             u'username/tag2': 16}}
        SecureTagValueAPI(self.superuser).set(values)
        self.permissions.set([(u'username/tag1', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, []),
                              (u'username/tag2', Operation.READ_TAG_VALUE,
                               Policy.OPEN, [])])

        result = self.objects.getTagsByObjects([objectID])
        self.assertEqual(1, len(result))
        self.assertIn(objectID, result)
        self.assertEqual([u'username/tag1', u'username/tag2'],
                         sorted(result[objectID]))

    def testGetTagsByObjectsWithCustomPermission(self):
        """
        L{SecureObjectAPI.getTagsByObjects} optionally accepts a permission
        type to check for instead of L{Operation.READ_TAG_VALUE}).
        """
        TagAPI(self.superuser).create(
            [(u'username/open', u'An accessible tag'),
             (u'username/closed', u'A denied tag')])
        objectID = uuid4()
        SecureTagValueAPI(self.superuser).set(
            {objectID: {u'username/open': 13, u'username/closed': 17}})
        self.permissions.set([(u'username/closed', Operation.DELETE_TAG_VALUE,
                               Policy.CLOSED, [])])
        result = self.objects.getTagsByObjects(
            [objectID], permission=Operation.DELETE_TAG_VALUE)
        # Superuser can always delete values, regardless of permission settings
        result[objectID].sort()
        self.assertEqual({objectID: [u'username/closed', u'username/open']},
                         result)

    def testGetTagsForObjectsIsAlwaysAllowed(self):
        """
        L{SecureObjectAPI.getTagsForObjects} is always allowed for the
        superuser.
        """
        TagAPI(self.superuser).create([(u'username/tag1', u'description'),
                                       (u'username/tag2', u'description')])
        objectID = uuid4()
        values = {objectID: {u'username/tag1': 16,
                             u'username/tag2': 16}}
        SecureTagValueAPI(self.superuser).set(values)
        self.permissions.set([(u'username/tag1', Operation.READ_TAG_VALUE,
                               Policy.CLOSED, []),
                              (u'username/tag2', Operation.READ_TAG_VALUE,
                               Policy.OPEN, [])])

        self.assertEqual(
            sorted([u'username/tag1', u'username/tag2']),
            sorted(self.objects.getTagsForObjects([objectID])))
