from fluiddb.data.permission import Operation
from fluiddb.cache.recentactivity import CachingRecentActivityAPI
from fluiddb.security.permission import checkPermissions


class SecureRecentActivityAPI(object):
    """The public API to secure recent activity related functionality.

    @param user: The L{User} to perform operations on behalf of.
    """

    def __init__(self, user):
        self._user = user
        self._recentActivity = CachingRecentActivityAPI()

    def _filterResult(self, result):
        """
        Filter recent activity eliminating those tags the user doesn't have
        L{Operation.READ_TAG_VALUE} permissions for.

        @param result: A C{list} of C{(Tag.path, TagValue.objectID,
            AboutTagValue.value, TagValue.value, User.username,
            value.creationTime)} 6-tuples with the information about the
            recent tag values.
        @return: Same items in result minus the tags the user is not allowed to
            read.
        """
        if not result:
            return []

        pathsAndOperations = set(
            (path, Operation.READ_TAG_VALUE) for
            path, objectID, about, value, username, time in result)

        deniedOperations = checkPermissions(self._user, pathsAndOperations)
        deniedPaths = set(path for path, operation in deniedOperations)

        #  FIXME: There's a potential problem with the filtering, which is that
        #  we only ever fetch N recent items from the database, but with
        #  filtering we might return N-M items (where M is the number of
        #  inaccessible items).
        return [(path, objectID, about, value, username, time)
                for path, objectID, about, value, username, time in result
                if path not in deniedPaths]

    def getForObjects(self, objectIDs):
        """See L{RecentActivityAPI.getForObjects}."""
        result = self._recentActivity.getForObjects(objectIDs)
        return self._filterResult(result)

    def getForUsers(self, usernames):
        """See L{RecentActivityAPI.getForUsers}."""
        result = self._recentActivity.getForUsers(usernames)
        return self._filterResult(result)
