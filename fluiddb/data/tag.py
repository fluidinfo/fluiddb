from uuid import uuid4

from storm.locals import (
    Storm, DateTime, Int, Unicode, UUID, Reference, AutoReload)

from fluiddb.data.exceptions import MalformedPathError
from fluiddb.data.path import isValidPath
from fluiddb.data.store import getMainStore


class Tag(Storm):
    """A tag represents a type of value.

    @param namespaceID: The L{Namespace.id} that contains this tag.
    @param name: The name of this tag.
    """

    __storm_table__ = 'tags'

    id = Int('id', primary=True, allow_none=False, default=AutoReload)
    objectID = UUID('object_id', allow_none=False)
    namespaceID = Int('namespace_id', allow_none=False)
    creatorID = Int('creator_id', allow_none=False)
    path = Unicode('path', allow_none=False)
    name = Unicode('name', allow_none=False)
    creationTime = DateTime('creation_time', default=AutoReload)

    namespace = Reference(namespaceID, 'Namespace.id')
    creator = Reference(creatorID, 'User.id')
    permission = Reference(id, 'TagPermission.tagID')

    def __init__(self, creator, namespace, path, name):
        self.objectID = uuid4()
        self.creator = creator
        self.path = path
        self.namespace = namespace
        self.name = name


def createTag(creator, namespace, name):
    """Create a new L{Tag}.

    @param creator: The L{User} that owns the L{Tag}.
    @param namespace: The parent L{Namespace}.
    @param name: The C{unicode} name of the L{Tag}.
    @raise MalformedPathError: Raised if C{path} is empty or has unnacceptable
        characters.
    @return: A new L{Tag} instance persisted in the main store.
    """
    store = getMainStore()
    path = u'/'.join([namespace.path, name])
    if not isValidPath(path):
        raise MalformedPathError("'%s' is not a valid path." % path)
    tag = Tag(creator, namespace, path, name)
    return store.add(tag)


def getTags(paths=None, objectIDs=None):
    """Get L{Tag}s.

    @param paths: Optionally, a sequence of L{Tag.path}s to filter the result
        with.
    @param objectIDs: Optionally, a sequence of L{Tag.objectID}s to filter the
        result with.
    @return: A C{ResultSet} with matching L{Tag}s.
    """
    store = getMainStore()
    where = []
    if paths:
        where.append(Tag.path.is_in(paths))
    if objectIDs:
        where.append(Tag.objectID.is_in(objectIDs))
    return store.find(Tag, *where)
