"""
Change the object for every user in the database to use the '@<username>' about
value. Also migrate all the existing tag values on the old object to the new
one.
"""
from fluiddb.application import setConfig, setupConfig
from fluiddb.data.tag import getTags
from fluiddb.data.user import getUsers
from fluiddb.data.value import (
    TagValue, getTagValues, getAboutTagValues, AboutTagValue)
from fluiddb.model.object import ObjectAPI
from fluiddb.scripts.commands import setupStore


if __name__ == '__main__':
    print __doc__

    store = setupStore('postgres:///fluidinfo', 'main')
    setConfig(setupConfig(None))

    aboutTag = getTags(paths=[u'fluiddb/about']).one()
    superUser = getUsers(usernames=[u'fluiddb']).one()

    result = store.find(AboutTagValue, AboutTagValue.value.like(u'@%'))
    for aboutValue in result:
        if aboutValue.value == aboutValue.value.lower():
            continue
        print 'Migrating mixed cased', aboutValue.value.encode('utf-8')

        newAbout = u'@%s' % aboutValue.value.lower()
        oldObjectID = aboutValue.objectID
        newObjectID = ObjectAPI(superUser).create(newAbout)
        result = store.find(TagValue,
                            TagValue.objectID == oldObjectID,
                            TagValue.tagID != aboutTag.id)
        for tagValue in result:
            existingValue = getTagValues([(newObjectID, tagValue.tagID)]).one()
            if existingValue is not None:
                error = ('ERROR: Cannot migrate value {path} on {about} '
                         'because the value already exist.')
                print error.format(path=tagValue.tag.path,
                                   about=aboutValue.value.encode('utf-8'))
            else:
                tagValue.objectID = newObjectID

    store.commit()

    for i, user in enumerate(getUsers()):
        print 'Migrating', user.username.encode('utf-8'), 'object.'

        newAbout = u'@%s' % user.username
        aboutValue = getAboutTagValues(objectIDs=[user.objectID]).one()
        if aboutValue and aboutValue.value == newAbout:
            print 'User already migrated.'
            continue

        oldObjectID = user.objectID
        newObjectID = ObjectAPI(superUser).create(newAbout)
        result = store.find(TagValue,
                            TagValue.objectID == oldObjectID,
                            TagValue.tagID != aboutTag.id)
        for tagValue in result:
            existingValue = getTagValues([(newObjectID, tagValue.tagID)]).one()
            if existingValue is not None:
                error = ('ERROR: Cannot migrate value {path} on {username} '
                         'because the value already exist.')
                print error.format(path=tagValue.tag.path,
                                   username=user.username)
            else:
                tagValue.objectID = newObjectID

        user.objectID = newObjectID

        if i % 100 == 0:
            store.commit()

    print 'Done.'
    store.commit()
