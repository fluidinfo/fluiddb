from itertools import izip
import json

from fluiddb.cache.cache import BaseCache, CacheResult
from fluiddb.cache.factory import CachingAPIFactory
from fluiddb.data.permission import (
    NamespacePermission, Operation, Policy, TagPermission)
from fluiddb.model.permission import PermissionAPI, PermissionCheckerAPI


class CachingPermissionAPI(object):
    """The public API to cached permission-related logic in the model."""

    def __init__(self, user):
        self._api = PermissionAPI(user, factory=CachingAPIFactory())

    def set(self, values):
        """See L{PermissionAPI.set}.

        Modified permissions are removed from the cache.
        """
        namespacePaths = [path for (path, operation, _, _) in values
                          if operation in Operation.NAMESPACE_OPERATIONS]
        tagPaths = [path for (path, operation, _, _) in values
                    if operation in Operation.TAG_OPERATIONS]
        cache = PermissionCache()
        cache.clearNamespacePermissions(namespacePaths)
        cache.clearTagPermissions(tagPaths)
        self._api.set(values)

    def get(self, values):
        """See L{PermissionAPI.get}."""
        return self._api.get(values)


class CachingPermissionCheckerAPI(object):
    """
    The public API to cached permission checking-related logic in the model.
    """

    def __init__(self):
        self._api = PermissionCheckerAPI()
        self._cache = PermissionCache()

    def getNamespacePermissions(self, paths):
        """See L{PermissionCheckerAPI.getNamespacePermissions}.

        L{NamespacePermission}s will be fetched from the cache if they are
        available, otherwise they will be fetched directly from the database.
        Cache misses will be added to the cache.
        """
        cached = self._cache.getNamespacePermissions(paths)
        if cached.uncachedValues:
            result = self._api.getNamespacePermissions(cached.uncachedValues)
            if result:
                self._cache.saveNamespacePermissions(result)
                cached.results.update(result)
        return cached.results

    def getTagPermissions(self, paths):
        """See L{PermissionCheckerAPI.getTagPermissions}.

        L{TagPermission}s will be fetched from the cache if they are
        available, otherwise they will be fetched directly from the database.
        Cache misses will be added to the cache.
        """
        cached = self._cache.getTagPermissions(paths)
        if cached.uncachedValues:
            result = self._api.getTagPermissions(cached.uncachedValues)
            if result:
                self._cache.saveTagPermissions(result)
                cached.results.update(result)
        return cached.results

    def getUnknownPaths(self, values):
        """See L{PermissionCheckerAPI.getUnknownPaths}."""
        # FIXME Make this work with the cache.
        return self._api.getUnknownPaths(values)

    def getUnknownParentPaths(self, unknownPaths):
        """See L{PermissionCheckerAPI.getUnknownParentPaths}."""
        # FIXME Make this work with the cache.
        return self._api.getUnknownParentPaths(unknownPaths)


class PermissionCache(BaseCache):
    """Provides caching functions for the L{PermissionAPI} class."""

    keyPrefix = u'permission:'

    def _getPermissions(self, paths, kind):
        """
        Get a set of permission objects stored in the cache for the given
        paths.

        @param paths: A sequence of paths of the permissions wanted.
        @param kind: Either 'tags' or 'namespaces'
        @return: A C{dict} mapping paths to permission objects from the given
            class.
        """
        if not paths:
            return CacheResult({}, paths)

        identifiers = [u'%s:%s' % (kind, path) for path in paths]
        results = self.getValues(identifiers)
        if results is None:
            return CacheResult({}, paths)

        notFoundValues = []
        permissionsByPath = {}

        for path, permissionDict in izip(paths, results):
            if permissionDict is None:
                notFoundValues.append(path)
                continue
            # FIXME: We use 0 as userID and namespaceID/tagID below for
            # permission instances.  A better solution would decouple the
            # permission classes from the database, but for now we'll live with
            # the inconsistency.
            if kind == 'tag':
                permission = TagPermission(0, 0)
            elif kind == 'namespace':
                permission = NamespacePermission(0, 0)
            else:
                raise RuntimeError('Wrong kind of permission.')

            permissionDict = json.loads(permissionDict)
            for operationID, (policyID, exceptions) in permissionDict.items():
                operation = Operation.fromID(int(operationID))
                policy = Policy.fromID(policyID)
                permission.set(operation, policy, exceptions)

            permissionsByPath[path] = permission

        return CacheResult(permissionsByPath, notFoundValues)

    def getTagPermissions(self, paths):
        """
        Get a set of L{TagPermission} objects stored in the cache for the given
        paths.

        @param paths: A sequence of paths of the permissions wanted.
        @return: A L{CacheResult} containing a C{dict} mapping paths to
            L{TagPermission} objects.
        """
        return self._getPermissions(paths, 'tag')

    def getNamespacePermissions(self, paths):
        """
        Get a set of L{NamespacePermission} objects stored in the cache for the
        given paths.

        @param paths: A sequence of paths of the permissions wanted.
        @return: A L{CacheResult} containing a C{dict} mapping paths to
            L{TagPermission} objects.
        """
        return self._getPermissions(paths, 'namespace')

    def _clearPermissions(self, paths, kind):
        """
        Remove permissions from the cache for the given paths and operations.

        @param paths: A sequence of paths to remove.
        @param kind: Either 'tags' or 'namespaces'
        """
        identifiers = [u'%s:%s' % (kind, path) for path in paths]
        self.deleteValues(identifiers)

    def clearTagPermissions(self, paths):
        """Remove L{TagPermissions} from the cache.

        @param paths: A sequence of paths of the L{TagPermission}s to remove.
        """
        self._clearPermissions(paths, 'tag')

    def clearNamespacePermissions(self, paths):
        """Remove L{NamespacePermissions} from the cache.

        @param paths: A sequence of paths of the L{NamespacePermission}s to
            remove.
        """
        self._clearPermissions(paths, 'namespace')

    def _savePermissions(self, result, kind):
        """Save a set of permissions in the cache.

        @param result: A C{dict} mapping paths to permission objects.
        @param kind: Either 'tags' or 'namespaces'
        """
        values = {}
        for path, permission in result.iteritems():
            permissionDict = {}
            for operation in permission.operations:
                policy, exceptions = permission.get(operation)
                permissionDict[operation.id] = [policy.id, exceptions]
            identifier = u'%s:%s' % (kind, path)
            values[identifier] = json.dumps(permissionDict)
        self.setValues(values)

    def saveTagPermissions(self, result):
        """Save a set of L{TagPermission}s in the cache.

        @param result: A C{dict} mapping paths to L{TagPermission}s objects.
        """
        self._savePermissions(result, 'tag')

    def saveNamespacePermissions(self, result):
        """Save a set of L{NamespacePermission}s in the cache.

        @param result: A C{dict} mapping paths to L{NamespacePermission}s
            objects.
        """
        self._savePermissions(result, 'namespace')
