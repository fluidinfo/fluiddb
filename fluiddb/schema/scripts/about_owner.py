"""
Change the creator id of all the fluiddb/about values to the fluiddb user.
"""

from fluiddb.data.tag import getTags
from fluiddb.data.user import getUsers
from fluiddb.scripts.commands import setupStore
from fluiddb.data.value import TagValue


if __name__ == '__main__':

    store = setupStore('postgres:///fluidinfo', 'main')

    print __doc__

    superUser = getUsers(usernames=[u'fluiddb']).one()
    aboutTag = getTags(paths=[u'fluiddb/about']).one()

    print 'Getting value IDs. This might take some minutes.'
    result = store.find(TagValue,
                        TagValue.tagID == aboutTag.id,
                        TagValue.creatorID != superUser.id)
    allValueIDs = list(result.values(TagValue.id))
    i = 0
    valueIDs = allValueIDs[i:i + 100]
    while valueIDs:
        result = store.find(TagValue, TagValue.id.is_in(valueIDs))
        result.set(creatorID=superUser.id)

        print 'Fixed', i + len(valueIDs), 'of', len(allValueIDs), 'tag values',
        print '%00.3f%%.' % (100.0 * (i + len(valueIDs)) / len(allValueIDs))
        i += 100
        valueIDs = allValueIDs[i:i + 100]
        store.commit()
    print 'Done.'
