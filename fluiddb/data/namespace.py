from uuid import uuid4

from storm.locals import (
    Storm, DateTime, Int, Unicode, Reference, ReferenceSet, AutoReload, UUID)

from fluiddb.data.exceptions import MalformedPathError
from fluiddb.data.path import getPathName, isValidPath
from fluiddb.data.store import getMainStore
from fluiddb.data.tag import Tag


class Namespace(Storm):
    """A namespace is a container for L{Tag}s and other namespaces.

    @param creator: The L{User} that owns the namespace.
    @param path: The full C{unicode} path for the namespace.
    @param name: The C{unicode} name of the namespace (should be the same as
        the last segment of C{path}).
    @param parent: Optionally, the C{Namespace} instance that represents the
        parent of this namespace.
    """

    __storm_table__ = 'namespaces'

    id = Int('id', primary=True, allow_none=False, default=AutoReload)
    objectID = UUID('object_id', allow_none=False)
    parentID = Int('parent_id')
    creatorID = Int('creator_id', allow_none=False)
    path = Unicode('path', allow_none=False)
    name = Unicode('name', allow_none=False)
    creationTime = DateTime('creation_time', default=AutoReload)

    creator = Reference(creatorID, 'User.id')
    parent = Reference(parentID, id)
    children = ReferenceSet(id, parentID)
    permission = Reference(id, 'NamespacePermission.namespaceID')

    def __init__(self, creator, path, name, parentID=None):
        self.objectID = uuid4()
        self.creator = creator
        self.path = path
        self.name = name
        self.parentID = parentID


def createNamespace(creator, path, parentID=None):
    """Create a new root-level L{Namespace}.

    @param creator: The L{User} that owns the namespace.
    @param path: The C{unicode} path (and name) of the namespace.
    @param parentID: Optionally, the L{Namespace.id} of the parent namespace.
    @raise MalformedPathError: Raised if C{path} is empty or has unacceptable
        characters.
    @return: A new L{Namespace} instance persisted in the main store.
    """
    if not isValidPath(path):
        raise MalformedPathError("'%s' is not a valid path." % path)
    store = getMainStore()
    name = getPathName(path)
    namespace = Namespace(creator, path, name, parentID)
    return store.add(namespace)


def getNamespaces(paths=None, objectIDs=None):
    """Get L{Namespace}s.

    @param paths: Optionally, a sequence of L{Namespace.path}s to filter the
        result with.
    @param objectIDs: Optionally, a sequence of L{Namespace.objectID}s to
        filter the result with.
    @return: A C{ResultSet} with matching L{Namespace}s.
    """
    store = getMainStore()
    where = []
    if paths:
        where.append(Namespace.path.is_in(paths))
    if objectIDs:
        where.append(Namespace.objectID.is_in(objectIDs))
    return store.find(Namespace, *where)


def getChildNamespaces(paths):
    """Get child L{Namespace}s.

    @param paths: A sequence of L{Namespace.path}s to get child L{Namespace}s
        for.
    @return: A C{ResultSet} with matching L{Namespace} children.
    """
    store = getMainStore()
    result = getNamespaces(paths)
    subselect = result.get_select_expr(Namespace.id)
    return store.find(Namespace, Namespace.parentID.is_in(subselect))


def getChildTags(paths):
    """Get child L{Tag}s.

    @param paths: A sequence of L{Namespace.path}s to get child L{Tag}s for.
    @return: A C{ResultSet} with matching L{Namespace} children.
    """
    store = getMainStore()
    result = getNamespaces(paths)
    subselect = result.get_select_expr(Namespace.id)
    return store.find(Tag, Tag.namespaceID.is_in(subselect))
