from hashlib import sha256

from storm.locals import (
    Storm, DateTime, Int, Unicode, UUID, RawStr, Reference, AutoReload, And,
    Or)
from storm.store import EmptyResultSet

from fluiddb.data.store import getMainStore
from fluiddb.data.tag import Tag
from fluiddb.util.database import BinaryJSON


BINARY_VALUE_KEYS = ['mime-type', 'size']


def validateTagValue(obj, attribute, value):
    """Validate a L{Tag} value before storing it in the database.

    @param obj: The L{TagValue} instance being updated.
    @param attribute: The name of the attribute being set.
    @param value: The value being stored.
    @raise ValueError: Raised if the value doesn't match the expected schema.
    @return: The value to store.
    """
    if isinstance(value, dict):
        if sorted(value.iterkeys()) != BINARY_VALUE_KEYS:
            raise ValueError("Can't store invalid binary value: %r" % value)
    return value


class TagValue(Storm):
    """A value for L{Tag}.

    @param creatorID: The L{User.id} of the person creating this value.
    @param tagID: The L{Tag.id} this value is for.
    @param objectID: The object this value is for.
    @param value: The value to store.
    """

    __storm_table__ = 'tag_values'

    id = Int('id', primary=True, allow_none=False)
    creatorID = Int('creator_id', allow_none=False)
    tagID = Int('tag_id', allow_none=False)
    objectID = UUID('object_id', allow_none=False)
    creationTime = DateTime('creation_time', default=AutoReload)
    value = BinaryJSON('value', validator=validateTagValue)

    tag = Reference(tagID, 'Tag.id')
    creator = Reference(creatorID, 'User.id')

    def __init__(self, creatorID, tagID, objectID, value):
        self.creatorID = creatorID
        self.tagID = tagID
        self.objectID = objectID
        self.value = value


class OpaqueValue(Storm):
    """An opaque tag value

    @param fileID: The sha-256 hash of the file.
    @param content: The content of the file.
    """

    __storm_table__ = 'opaque_values'

    fileID = RawStr('file_id', primary=True, allow_none=False)
    content = RawStr('content', allow_none=False)

    def __init__(self, fileID, content):
        self.fileID = fileID
        self.content = content


class OpaqueValueLink(Storm):
    """A representation of tag_value - opaque_value many-to-one relation.

    @param valueID: The L{TagValue.id}.
    @param fileID: The L{OpaqueValue.fileID}
    """

    __storm_table__ = 'opaque_value_link'
    __storm_primary__ = 'valueID', 'fileID'

    valueID = Int('value_id', allow_none=False)
    fileID = RawStr('file_id', allow_none=False)

    def __init__(self, valueID, fileID):
        self.valueID = valueID
        self.fileID = fileID


def createOpaqueValue(valueID, content):
    """Create a new L{OpaqueValue} associated with the given L{TagValue}.

    @param valueID: The L{TagValue.id} for the associated value.
    @param content: The binary content of the opaque value.
    """
    fileID = sha256(content).hexdigest()
    store = getMainStore()
    opaque = store.find(OpaqueValue, OpaqueValue.fileID == fileID).one()
    if opaque is None:
        opaque = OpaqueValue(fileID, content)
        store.add(opaque)
    store.add(OpaqueValueLink(valueID, fileID))
    return opaque


def getOpaqueValues(valueIDs):
    """Get L{OpaqueValue}s for the given L{TagValue}s.

    @param valueIDs: A sequence of L{TagValue.id}s.
    @return: A C{ResultSet} with L{OpaqueValue}s.
    """
    store = getMainStore()
    return store.find(OpaqueValue,
                      OpaqueValue.fileID == OpaqueValueLink.fileID,
                      OpaqueValueLink.valueID.is_in(valueIDs))


def createTagValue(creatorID, tagID, objectID, value):
    """Create a new L{TagValue}.

    @param creatorID: The L{User.id} of the person creating this value.
    @param tagID: The L{Tag.id} this value is associated with.
    @param objectID: The object ID this value is associated with.
    @param value: The value to store.
    @return: A L{TagValue} instance, added to the database.
    """
    store = getMainStore()
    return store.add(TagValue(creatorID, tagID, objectID, value))


def getTagValues(values=None):
    """Get L{TagValue}s.

    @param values: Optionally, a sequence of C{(objectID, Tag.id)} 2-tuples to
        filter the result with.
    @return: A C{ResultSet} with L{TagValue}s.
    """
    store = getMainStore()
    where = []
    if values:
        expressions = [
            And(TagValue.objectID == objectID, TagValue.tagID == tagID)
            for objectID, tagID in values]
        where = [Or(*expressions)]
    return store.find(TagValue, *where)


def getTagPathsAndObjectIDs(objectIDs):
    """Get L{Tag.path}s for object IDs.

    @param objectIDs: A sequence of object IDs.
    @return: A C{ResultSet} yielding C{(Tag.path, objectID)} 2-tuples.
    """
    if not objectIDs:
        return EmptyResultSet()
    store = getMainStore()
    return store.find((Tag.path, TagValue.objectID),
                      Tag.id == TagValue.tagID,
                      TagValue.objectID.is_in(objectIDs))


def getTagPathsForObjectIDs(objectIDs):
    """Get L{Tag.path}s for object IDs.

    @param objectIDs: A sequence of object IDs.
    @return: A C{ResultSet} yield L{Tag.path} values.
    """
    if not objectIDs:
        return EmptyResultSet()
    store = getMainStore()
    result = store.find(Tag.path,
                        Tag.id == TagValue.tagID,
                        TagValue.objectID.is_in(objectIDs))
    result.config(distinct=True)
    return result


def getObjectIDs(paths):
    """Get object IDs for L{Tag.path}s.

    @param tags: A sequence of L{Tag.path}s.
    @return: A C{ResultSet} yielding C{TagValue.objectID}s.
    """
    if not paths:
        return EmptyResultSet()
    store = getMainStore()
    return store.find(TagValue.objectID,
                      Tag.id == TagValue.tagID,
                      Tag.path.is_in(paths))


class TagValueCollection(object):
    """A collection of L{Tag} values.

    @param objectIDs: Optionally, a sequence of object IDs to filter the
        collection with.
    @param paths: Optionally, a sequence of L{Tag.path}s to filter the
        collection with.
    """

    def __init__(self, objectIDs=None, paths=None, createdBeforeTime=None):
        self._criteria = {'objectIDs': objectIDs,
                          'paths': paths,
                          'createdBeforeTime': createdBeforeTime}

    def values(self):
        """
        Get L{Tag} values that match the filtering criteria defined for this
        collection.

        @return: A L{ResultSet} yielding C{(Tag, TagValue)} 2-tuples.
        """
        store = getMainStore()
        tagIDs = self._getTagIDs()
        where = self._getWhereClause(tagIDs)
        return store.find((Tag, TagValue), *where)

    def _getTagIDs(self):
        """Get a L{Tag.id}s for path filtering criteria.

        @return: A C{list} of L{Tag.id}s for paths or C{None} if no path
            filtering criteria are available.
        """
        paths = self._criteria.get('paths')
        if paths:
            store = getMainStore()
            return list(store.find(Tag.id, Tag.path.is_in(paths)))

    def _getWhereClause(self, tagIDs):
        """Build a where clause to find C{valueType} tag values.

        @param tagIDs: A C{list} of L{Tag.id}s.  If an empty C{list} or
            C{None} is provided, no L{Tag} filtering will be performed.
        @return: A list of Storm expressions to use as the where clause.
        """
        objectIDs = self._criteria.get('objectIDs')
        where = [TagValue.tagID == Tag.id]
        if objectIDs:
            where.append(TagValue.objectID.is_in(objectIDs))
        if tagIDs:
            where.append(Tag.id.is_in(tagIDs))
        createdBeforeTime = self._criteria.get('createdBeforeTime')
        if createdBeforeTime:
            where.append(TagValue.creationTime < createdBeforeTime)
        return where


class AboutTagValue(Storm):
    """An about L{Tag} value.

    @param objectID: The object this value is for.
    @param value: The value to store.
    """

    __storm_table__ = 'about_tag_values'

    objectID = UUID('object_id', primary=True, allow_none=False)
    value = Unicode('value', allow_none=False)

    def __init__(self, objectID, value):
        self.objectID = objectID
        self.value = value


def createAboutTagValue(objectID, value):
    """Create a new L{AboutTagValue}.

    @param objectID: The object ID this value is associated with.
    @param value: The value to store.
    @return: An L{AboutTagValue} instance, added to the database.
    """
    store = getMainStore()
    return store.add(AboutTagValue(objectID, value))


def getAboutTagValues(objectIDs=None, values=None):
    """Get L{AboutTagValue}s.

    @param objectIDs: Optionally, a sequence of C{objectID}s to filter the
        result with.
    @param values: Optionally, a sequence of C{AboutTagValue.value}s to filter
        the result with.
    """
    store = getMainStore()
    where = []
    if objectIDs:
        where.append(AboutTagValue.objectID.is_in(objectIDs))
    if values:
        where.append(AboutTagValue.value.is_in(values))
    if where:
        # Can't pass an Or expression to store.find if where is empty
        # i.e, no filtering is requested
        return store.find(AboutTagValue, Or(*where))
    return store.find(AboutTagValue)
