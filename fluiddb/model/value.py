from datetime import datetime
from inspect import isgenerator

from storm.locals import AutoReload

from fluiddb.data.object import touchObjects
from fluiddb.data.tag import Tag, getTags
from fluiddb.data.value import (
    TagValueCollection, createTagValue, getTagValues, getOpaqueValues,
    createOpaqueValue)
from fluiddb.exceptions import FeatureError
from fluiddb.model.factory import APIFactory


class TagValueAPI(object):
    """The public API for L{TagValue}s in the model layer.

    @param user: The L{User} to perform operations on behalf of.
    @param factory: Optionally, the API factory to use when creating internal
        APIs.  Default is L{APIFactory}.
    """

    def __init__(self, user, factory=None):
        self._user = user
        self._factory = factory or APIFactory()

    def get(self, objectIDs, paths=None):
        """Get L{TagValue}s matching filtering criteria.

        @param objectIDs: A sequence of object IDs to retrieve values for.
        @param paths: Optionally, a sequence of L{Tag.path}s to return.  The
            default is to return values for all available L{Tag.path}s.
        @raise FeatureError: Raised if any of the arguments is empty or
            C{None}.
        @return: A C{dict} mapping object IDs to tags and values, matching the
            following format::

              {<object-id>: {<path>: <L{TagValue}>}}
        """
        if not objectIDs:
            raise FeatureError("Can't get tag values for an empty list of "
                               'object IDs.')
        if not paths:
            objects = self._factory.objects(self._user)
            paths = objects.getTagsForObjects(objectIDs)

        result = {}

        if u'fluiddb/id' in paths:
            for objectID in objectIDs:
                tagValue = FluidinfoTagValue.fromObjectID(objectID)
                result[objectID] = {u'fluiddb/id': tagValue}

        # Avoid querying the database if only the 'fluiddb/id' tag has
        # been requested, since we already have the results.
        if [u'fluiddb/id'] == paths:
            return result

        collection = TagValueCollection(objectIDs=objectIDs, paths=paths)
        for tag, tagValue in collection.values():
            if tagValue.objectID not in result:
                result[tagValue.objectID] = {}
            tagValue = FluidinfoTagValue.fromTagValue(tagValue)
            if isinstance(tagValue.value, dict):
                # We have to make a copy of the value because we don't want
                # storm to try to add the 'contents' binary value to the
                # database.
                tagValue.value = dict(tagValue.value)
                opaque = getOpaqueValues([tagValue.id]).one()
                if opaque is None:
                    raise RuntimeError('Opaque value not found.')
                tagValue.value['contents'] = opaque.content
            result[tagValue.objectID][tag.path] = tagValue

        return result

    def set(self, values):
        """Set or update L{TagValue}s.

        L{Tag}s that don't exist are created automatically before L{TagValue}s
        are stored.  Associated L{TagPermission}s are created automatically
        with the system-wide default permissions.

        @param values: A C{dict} mapping object IDs to tags and values,
            matching the following format::

              {<object-id>: {<path>: <value>,
                             <path>: {'mime-type': <mime-type>,
                                      'contents': <contents>}}}

            A binary L{TagValue} is represented using a different layout than
            other values types, as shown for the second value.
        @raise FeatureError: Raised if the given list of values is empty.
        @raise MalformedPathError: Raised if one of the given paths for a
            nonexistent tag is empty or has unacceptable characters.
        """
        if not values:
            raise FeatureError("Can't set an empty list of tag values.")

        objectIDs = set(values.keys())

        # Implicitly create missing tags, if there are any.
        paths = set()
        for tagValues in values.itervalues():
            paths.update(tagValues.iterkeys())
        tagIDs = dict(getTags(paths=paths).values(Tag.path, Tag.id))
        existingPaths = set(tagIDs.iterkeys())
        unknownPaths = paths - existingPaths
        if unknownPaths:
            tags = [(path, u'Object for the attribute %s' % path)
                    for path in unknownPaths]
            self._factory.tags(self._user).create(tags)
            tagIDs = dict(getTags(paths=paths).values(Tag.path, Tag.id))

        # Delete all existing tag values for the specified object IDs and
        # paths.
        deleteValues = []
        for objectID in values:
            for path in values[objectID].iterkeys():
                deleteValues.append((objectID, tagIDs[path]))
        getTagValues(deleteValues).remove()

        # Set new tag values for the specified object IDs and paths.
        for objectID in values:
            tagValues = values[objectID]
            for path, value in tagValues.iteritems():
                tagID = tagIDs[path]

                if isinstance(value, dict):
                    content = value['contents']
                    value = createTagValue(self._user.id, tagID, objectID,
                                           {'mime-type': value['mime-type'],
                                            'size': len(content)})

                    # This is necessary to tell PostgreSQL that generates a
                    # `value.id` immediately.
                    value.id = AutoReload
                    createOpaqueValue(value.id, content)
                else:
                    createTagValue(self._user.id, tagID, objectID, value)
        touchObjects(objectIDs)

    def delete(self, values):
        """Delete L{TagValue}s.

        @param values: A sequence of C{(objectID, Tag.path)} 2-tuples to
            delete values for.
        @raise FeatureError: Raised if the given list of values is empty.
        @return: The number of values deleted.
        """
        if isgenerator(values):
            values = list(values)
        if not values:
            raise FeatureError("Can't delete an empty list of tag values.")

        paths = set([path for objectID, path in values])
        objectIDs = set([objectID for objectID, path in values])
        tagIDs = dict(getTags(paths).values(Tag.path, Tag.id))
        values = [(objectID, tagIDs[path]) for objectID, path in values]
        result = getTagValues(values).remove()
        if result:
            touchObjects(objectIDs)
        return result


class FluidinfoTagValue(object):
    """A copy of a L{TagValue} that can be used across thread boundaries.

    @param id: The ID of the value.
    @param creator: The L{User} of the person creating this value.
    @param tagID: The L{Tag.id} this value is for.
    @param objectID: The object this value is for.
    @param creationgTime: The date and time when the value was created.
    @param value: The value to store.
    """

    class Creator:
        id = None
        username = u'fluiddb'

    def __init__(self, id, creator, tagID, objectID, creationTime, value):
        self.id = id
        self.creator = creator
        self.creatorID = creator.id
        self.tagID = tagID
        self.objectID = objectID
        self.creationTime = creationTime
        self.value = value

    @classmethod
    def fromTagValue(cls, tagValue):
        """Create a L{FluidinfoTagValue} from a L{TagValue} object.

        @param tagValue: The L{TagValue} to copy.
        """
        return cls(tagValue.id, tagValue.creator, tagValue.tagID,
                   tagValue.objectID, tagValue.creationTime, tagValue.value)

    @classmethod
    def fromObjectID(cls, objectID):
        """
        Create a L{FluidinfoTagValue} for C{fluiddb/id} for the given object
        ID.

        @param objectID: The object ID of the value.
        """
        return cls(None, cls.Creator(), None, objectID, datetime.utcnow(),
                   objectID)
