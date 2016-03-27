"""Lowercase the first component of all paths in the database."""

from fluiddb.application import setConfig, setupConfig
from fluiddb.data.namespace import getNamespaces, Namespace
from fluiddb.data.object import touchObjects
from fluiddb.data.tag import getTags, Tag
from fluiddb.data.value import TagValue, getAboutTagValues, createAboutTagValue
from fluiddb.model.user import getUser
from fluiddb.model.value import TagValueAPI
from fluiddb.scripts.commands import setupStore


if __name__ == '__main__':

    store = setupStore('postgres:///fluidinfo', 'main')
    setConfig(setupConfig(None))

    BATCH_SIZE = 50

    print __doc__

    superUser = getUser(u'fluiddb')
    tagValues = TagValueAPI(superUser)

    print 'Getting tags to fix.'
    tagsToFix = []
    for tagID, path in getTags().values(Tag.id, Tag.path):
        root = path.split('/', 1)[0]
        if not root.islower():
            tagsToFix.append(tagID)

    print 'Getting namespaces to fix.'
    namespacesToFix = []
    for namespaceID, path in getNamespaces().values(Namespace.id,
                                                    Namespace.path):
        root = path.split('/', 1)[0]
        if not root.islower():
            namespacesToFix.append(namespaceID)

    print 'Fixing tags.'
    i = 0
    currentIDs = tagsToFix[i:i + BATCH_SIZE]
    while currentIDs:
        systemValues = {}
        for tag in store.find(Tag, Tag.id.is_in(currentIDs)):
            root, rest = tag.path.split('/', 1)
            newPath = u'/'.join([root.lower(), rest])
            print 'Replacing tag', tag.path, 'with', newPath
            tag.path = newPath

            newAbout = 'Object for the attribute %s' % newPath
            systemValues[tag.objectID] = {
                u'fluiddb/about': newAbout,
                u'fluiddb/tags/path': newPath
            }

            print 'Fixing about tag value.'
            # Remove the new value if it exists to avoid integrity errors.
            result = getAboutTagValues(values=[newAbout])
            value = result.one()
            if value is not None:
                print 'ERROR about tag value already exists. Deleting it.'
                # Wipe all the tag values for that objectID
                result2 = store.find(TagValue,
                                     TagValue.objectID == value.objectID)
                result2.remove()
                result.remove()
            # Update the about value.
            value = getAboutTagValues(objectIDs=[tag.objectID]).one()
            if value is not None:
                value.value = newAbout
            else:
                createAboutTagValue(tag.objectID, newAbout)

        print 'Fixing system values'
        tagValues.set(systemValues)

        print 'Touching objects.'
        result = store.find(TagValue.objectID,
                            TagValue.tagID.is_in(currentIDs))
        touchObjects(list(result.config(distinct=True)))
        touchObjects(systemValues.keys())

        i += BATCH_SIZE
        currentIDs = tagsToFix[i:i + BATCH_SIZE]

    print 'Fixing namespaces.'
    i = 0
    currentIDs = namespacesToFix[i:i + BATCH_SIZE]
    while currentIDs:
        systemValues = {}
        for namespace in store.find(Namespace, Namespace.id.is_in(currentIDs)):
            if u'/' in namespace.path:
                root, rest = namespace.path.split('/', 1)
                newPath = u'/'.join([root.lower(), rest])
            else:
                newPath = namespace.path.lower()
            print 'Replacing namespace', namespace.path, 'with', newPath
            result = getNamespaces(paths=[newPath])
            if result.one() is not None:
                print 'ERROR: lowercased namespace exists. Ignoring.'
                result.remove()
            namespace.path = newPath

            newAbout = u'Object for the namespace %s' % newPath
            systemValues[namespace.objectID] = {
                u'fluiddb/about': newAbout,
                u'fluiddb/namespaces/path': newPath
            }

            print 'Fixing about tag value.'
            # Remove the new value if it exists to avoid integrity errors.
            result = getAboutTagValues(values=[newAbout])
            value = result.one()
            if value is not None:
                print 'ERROR about tag value already exists. Deleting it.'
                # Wipe all the tag values for that objectID
                result2 = store.find(TagValue,
                                     TagValue.objectID == value.objectID)
                result2.remove()
                result.remove()
            # Update the about value.
            value = getAboutTagValues(objectIDs=[namespace.objectID]).one()
            if value is not None:
                value.value = newAbout
            else:
                createAboutTagValue(namespace.objectID, newAbout)

        print 'Fixing system values'
        tagValues.set(systemValues)

        print 'Touching objects.'
        touchObjects(systemValues.keys())

        i += BATCH_SIZE
        currentIDs = namespacesToFix[i:i + BATCH_SIZE]

    print 'Fixing users.'

    # Usernames were fixed in the lowercase_usernames patch. But there are some
    # pending things.
    systemValues = {}
    result = store.find(TagValue,
                        TagValue.tagID == Tag.id,
                        Tag.path == u'fluiddb/users/username')
    for value in result:
        if value.value.islower():
            continue

        oldUsername = value.value
        newUsername = oldUsername.lower()

        print 'Replacing user', oldUsername, 'with', newUsername

        newAbout = u'@%s' % newUsername
        systemValues[value.objectID] = {
            u'fluiddb/about': newAbout,
            u'fluiddb/users/username': newUsername
        }

        print 'Fixing about tag value.'
        # Remove the new value if it exists to avoid integrity errors.
        result = getAboutTagValues(values=[newAbout])
        aboutValue = result.one()
        if aboutValue is not None:
            print 'ERROR about tag value already exists. Deleting it.'
            # Wipe all the tag values for that objectID
            result2 = store.find(TagValue,
                                 TagValue.objectID == aboutValue.objectID)
            result2.remove()
            result.remove()
        # Update the about value.
        aboutValue = getAboutTagValues(objectIDs=[value.objectID]).one()
        if aboutValue is not None:
            aboutValue.value = newAbout
        else:
            createAboutTagValue(value.objectID, newAbout)

    print 'Fixing system values'
    tagValues.set(systemValues)

    print 'Touching objects.'
    touchObjects(systemValues.keys())

    store.commit()

    print 'Done'
