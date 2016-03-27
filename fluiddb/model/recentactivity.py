from fluiddb.data.exceptions import UnknownUserError
from fluiddb.data.recentactivity import getRecentActivity
from fluiddb.data.user import getUsers, User


class RecentActivityAPI(object):

    def _formatResult(self, result):
        """
        Formats the output of a call to L{getRecentActivity} changing binary
        values to hide the C{file-id} and match the expected format.

        @param result: A generator of 6-tuples produced by L{getRecentActivity}
        @return A C{list} of C{(Tag.path, TagValue.objectID,
            AboutTagValue.value, TagValue.value, User.username,
            value.creationTime)} 6-tuples with the formatted information about
            the recent tag values.
        """
        recentActivity = []
        for path, objectID, about, value, username, time in result:
            if isinstance(value, dict):
                value = {u'value-type': value[u'mime-type'],
                         u'size': value[u'size']}
            recentActivity.append(
                (path, objectID, about, value, username, time))
        return recentActivity

    def getForObjects(self, objectIDs):
        """Get information about recent tag values on the given objects.

        @param objectIDs: A sequence of object IDs to get recent tags from.
        @return: A C{list} of C{(Tag.path, TagValue.objectID,
            AboutTagValue.value, TagValue.value, User.username,
            value.creationTime)} 6-tuples with the information about the
            recent tag values.
        """
        return self._formatResult(getRecentActivity(objectIDs=objectIDs))

    def getForUsers(self, usernames):
        """Get information about recent tag values on the given users.

        @param usernames: A sequence of usernames to get recent tags from.
        @raise: L{UnknownUserError} if one of the given usernames doesn't
            exist.
        @return: A C{list} of C{(Tag.path, TagValue.objectID,
            AboutTagValue.value, TagValue.value, User.username,
            value.creationTime)} 6-tuples with the information about the
            recent tag values.
        """
        usernames = set(usernames)
        result = getUsers(usernames=usernames)
        existingUsernames = set(result.values(User.username))
        unknownUsernames = usernames - existingUsernames
        if unknownUsernames:
            raise UnknownUserError(list(unknownUsernames))
        return self._formatResult(getRecentActivity(usernames=usernames))
