from storm.expr import LeftJoin
from storm.locals import Desc, Or, Select

from fluiddb.data.store import getMainStore
from fluiddb.data.tag import Tag
from fluiddb.data.user import User
from fluiddb.data.value import TagValue, AboutTagValue


def getRecentActivity(objectIDs=None, usernames=None, limit=20):
    """Get information about recent tag values.

    @param objectIDs: Optionally, a sequence of L{TagValue.objectID} to get
        recent tag value information for.
    @param usernames: Optionally, a sequence of L{User.username}s to get
        recent tag value information for.
    @param limit: Optionally, a limit to the number of rows returned by this
        function.
    @return: A generator yielding C{(Tag.path, TagValue.objectID,
        AboutTagValue.value, TagValue.value, User.username,
        value.creationTime)} 6-tuples with the information about the recent
        tag values. The tuples are sorted by creation time.
    """
    if objectIDs and usernames:
        mainCondition = Or(User.username.is_in(usernames),
                           TagValue.objectID.is_in(objectIDs))
    elif objectIDs:
        mainCondition = (TagValue.objectID.is_in(objectIDs))
    elif usernames:
        # If we're only requesting one user, we use a special query which is
        # optimized by the use the tag_values_creator_creation_idx two-column
        # index in Postgres.
        if len(usernames) == 1:
            [username] = usernames
            subselect = Select(User.id, User.username == username)
            mainCondition = (TagValue.creatorID == subselect)
        else:
            mainCondition = (User.username.is_in(usernames))
    else:
        return

    store = getMainStore()
    join = LeftJoin(TagValue, AboutTagValue,
                    TagValue.objectID == AboutTagValue.objectID)
    result = store.using(User, Tag, join).find(
        (Tag, TagValue, AboutTagValue, User),
        mainCondition,
        TagValue.creatorID == User.id,
        TagValue.tagID == Tag.id)
    result = result.order_by(Desc(TagValue.creationTime))
    result = result.config(limit=limit)

    # FIXME: We have to do this because Storm doesn's support getting null
    # values for about_tag_values in the LEFT JOIN.
    for tag, value, aboutValue, user in result:
        about = aboutValue.value if aboutValue else None
        yield (tag.path, value.objectID, about, value.value,
               user.username, value.creationTime)
