from fluiddb.cache.object import CachingObjectAPI
from fluiddb.data.permission import Operation
from fluiddb.model.object import isEqualsQuery
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.security.permission import checkPermissions


# FIXME We should probably have an IObjectAPI interface and assert that
# SecureObjectAPI and ObjectAPI both implement it.  And also move the
# docstrings there.
class SecureObjectAPI(object):
    """The public API to secure object-related functionality.

    @param user: The L{User} to perform operations on behalf of.
    """

    def __init__(self, user):
        self._api = CachingObjectAPI(user)
        self._user = user

    def create(self, value=None):
        """See L{ObjectAPI.create}.

        @raises PermissionDeniedError: Raised if the user is not authorized to
            create objects.
        """
        pathsAndOperations = [(None, Operation.CREATE_OBJECT)]
        deniedOperations = checkPermissions(self._user, pathsAndOperations)
        if deniedOperations:
            raise PermissionDeniedError(self._user.username, deniedOperations)
        return self._api.create(value)

    def get(self, values):
        """See L{ObjectAPI.get}."""
        return self._api.get(values)

    def getTagsByObjects(self, objectIDs, permission=None):
        """See L{ObjectAPI.getTagsByObjects}.

        @param permission: Optionally, the permission the user must have for
            the L{Tag.path} to be included in the return result.  Default is
            L{Operation.READ_TAG_VALUE}.
        """
        if permission is None:
            permission = Operation.READ_TAG_VALUE
        # We have to call getTagsByObjects first, since we don't know which
        # Tag's the user has the requested permission for.
        tagPaths = self._api.getTagsByObjects(objectIDs)
        if tagPaths:
            pathsAndOperations = set()
            for objectID, paths in tagPaths.iteritems():
                for path in paths:
                    pathsAndOperations.add((path, permission))
            deniedOperations = checkPermissions(self._user, pathsAndOperations)
            deniedPaths = set([path for path, operation in deniedOperations])
            if not deniedPaths:
                return tagPaths

            result = {}
            for objectID, paths in tagPaths.iteritems():
                allowedPaths = [path for path in paths
                                if path not in deniedPaths]
                if allowedPaths:
                    result[objectID] = allowedPaths
            return result
        else:
            return {}

    def getTagsForObjects(self, objectIDs):
        """See L{ObjectAPI.getTagsForObjects}."""
        # We have to call getTagsForObjects first, since we don't know which
        # L{Tag}s the user has L{Operation.READ_TAG_VALUE} permission for.
        tagPaths = self._api.getTagsForObjects(objectIDs)
        if tagPaths:
            pathsAndOperations = set()
            for path in tagPaths:
                pathsAndOperations.add((path, Operation.READ_TAG_VALUE))
            deniedOperations = checkPermissions(self._user, pathsAndOperations)
            deniedPaths = set([path for path, operation in deniedOperations])
            if not deniedPaths:
                return tagPaths
            else:
                return [path for path in tagPaths if path not in deniedPaths]
        else:
            return []

    def search(self, queries, implicitCreate=True):
        """See L{ObjectAPI.search}.

        @raises PermissionDeniedError: Raised if the L{User} doesn't have
            L{Operation.READ_TAG_VALUE} on one or more of the L{Tag.path}s in
            C{queries}.
        @raises UnknownPathError: Raised if any of the L{Tag}s in the L{Query}
            does not exist.
        """
        paths = set()
        aboutValues = set()
        for query in queries:
            if isEqualsQuery(query, u'fluiddb/about'):
                aboutValues.add(query.rootNode.right.value)
            for path in query.getPaths():
                paths.add(path)
        actions = [(path, Operation.READ_TAG_VALUE) for path in paths]
        if aboutValues:
            # TODO: this can be optimized because we repeat the query in
            # model.ObjectAPI.
            existingValues = self.get([value for value in aboutValues
                                       if isinstance(value, unicode)])
            if len(existingValues) != len(aboutValues):
                actions.append((None, Operation.CREATE_OBJECT))
        deniedActions = checkPermissions(self._user, actions)

        # If the implicitCreate option is given, but we don't have permissions,
        # we just disable implicitCreate instead of raising an exception.
        if (implicitCreate
                and deniedActions == [(None, Operation.CREATE_OBJECT)]):
            return self._api.search(queries, False)

        if deniedActions:
            raise PermissionDeniedError(self._user.username, deniedActions)

        return self._api.search(queries, implicitCreate)
