from collections import defaultdict
from inspect import isgenerator

from fluiddb.data.namespace import (
    Namespace, createNamespace, getNamespaces, getChildNamespaces,
    getChildTags)
from fluiddb.data.path import getParentPath, getParentPaths, getPathHierarchy
from fluiddb.data.permission import (
    createNamespacePermission, getNamespacePermissions)
from fluiddb.data.tag import Tag
from fluiddb.model.exceptions import DuplicatePathError, NotEmptyError
from fluiddb.model.factory import APIFactory


class NamespaceAPI(object):
    """The public API to L{Namespace}-related functionality in the model layer.

    @param user: The L{User} to perform operations on behalf of.
    @param factory: Optionally, the API factory to use when creating internal
        APIs.  Default is L{APIFactory}.
    """

    def __init__(self, user, factory=None):
        self._user = user
        self._factory = factory or APIFactory()

    def create(self, values):
        """Create new L{Namespace}s.

        Missing parent L{Namespace}s are created automatically.  For example,
        if C{foo/bar/baz} is requested, and C{foo/bar} doesn't already exist,
        it will be created before C{foo/bar/baz} is created.  Associated
        L{NamespacePermission}s are created automatically with the system-wide
        default permissions.

        @param values: A sequence of C{(path, description)} 2-tuples.
        @raises DuplicatePathError: Raised if the path for a new L{Namespace}
            collides with an existing one.
        @raise MalformedPathError: Raised if one of the given paths is empty
            or has unacceptable characters.
        @return: A C{list} of C{(objectID, path)} 2-tuples for the new
            L{Namespace}s.
        """
        from fluiddb.model.user import getUser

        if not values:
            return []

        paths = [path for path, description in values]
        descriptions = dict(values)

        self._checkForDuplicates(paths)

        admin = getUser(u'fluiddb')
        objects = self._factory.objects(admin)
        systemValues = {}

        paths = getPathHierarchy(paths)
        existingNamespaces = dict((namespace.path, namespace)
                                  for namespace in getNamespaces(paths=paths))
        newNamespaces = []

        for path in sorted(paths):
            if path in existingNamespaces:
                continue

            parentPath = getParentPath(path)
            parentID = (existingNamespaces[parentPath].id
                        if parentPath is not None
                        else None)
            namespace = createNamespace(self._user, path, parentID)
            aboutValue = u'Object for the namespace %s' % path
            description = descriptions.get(path, aboutValue)
            namespace.objectID = objects.create(aboutValue)
            systemValues[namespace.objectID] = {
                u'fluiddb/namespaces/description': description,
                u'fluiddb/namespaces/path': path,
                u'fluiddb/about': aboutValue}
            existingNamespaces[path] = namespace
            newNamespaces.append(namespace)

        self._createPermissions(newNamespaces)
        self._factory.tagValues(admin).set(systemValues)
        values = [(namespace.objectID, namespace.path)
                  for namespace in newNamespaces]
        return values

    def _checkForDuplicates(self, paths):
        """
        Make sure L{Namespace} or L{Tag} paths don't exist before trying to
        create new namespaces.

        @param values: A sequence of C{(path, description)} 2-tuples.
        @raises DuplicatePathError: Raised if the path for a new L{Namespace}
            collides with an existing one.
        """
        existingPaths = list(getNamespaces(paths=paths).values(Namespace.path))
        if existingPaths:
            raise DuplicatePathError(
                'Paths already exist: %s' % ', '.join(existingPaths))

    def _createPermissions(self, namespaces):
        """Create L{NamespacePermission}s for new L{Namespace}s.

        L{Namespace}s inherit permissions from their parent namespace, if one
        is available.

        @param namespaces: A sequence of new L{Namespace}s to create
            L{NamespacePermission}s for.
        """
        paths = [namespace.path for namespace in namespaces]
        parentPaths = getParentPaths(paths)
        index = {}
        for parent, permission in getNamespacePermissions(parentPaths):
            index[parent.path] = permission
        for namespace in sorted(namespaces,
                                key=lambda namespace: namespace.path):
            parentPath = getParentPath(namespace.path)
            parentPermission = index.get(parentPath)
            permission = createNamespacePermission(
                namespace, permissionTemplate=parentPermission)
            index[namespace.path] = permission

    def delete(self, paths):
        """Delete L{Namespace}s matching C{paths}.

        @param paths: A sequence of L{Namespace.path}s.
        @raises NotEmptyError: Raised if the L{Namespace} is not empty.
        @return: A C{list} of C{(objectID, Namespace.path)} 2-tuples
            representing the deleted L{Namespace}s.
        """
        if isgenerator(paths):
            paths = list(paths)
        if getChildNamespaces(paths).any() or getChildTags(paths).any():
            raise NotEmptyError("Can't delete non-empty namespaces.")

        result = getNamespaces(paths=paths)
        deletedNamespaces = list(result.values(Namespace.objectID,
                                               Namespace.path))
        values = [(objectID, systemTag)
                  for objectID, _ in deletedNamespaces
                  for systemTag in (u'fluiddb/namespaces/description',
                                    u'fluiddb/namespaces/path')]
        if values:
            self._factory.tagValues(self._user).delete(values)
        result.remove()
        return deletedNamespaces

    def get(self, paths, withDescriptions=None, withNamespaces=None,
            withTags=None):
        """Get information about L{Namespace}s matching C{paths}.

        @param paths: A sequence of L{Namespace.path}s.
        @param withDescriptions: Optionally, a C{bool} indicating whether or
            not to include L{Namespace} descriptions in the result.  Default
            is C{False}.
        @param withNamespaces: Optionally, a C{bool} indicating whether or not
            to include the names of child L{Namespace}s in the result.
            Default is C{False}.
        @param withTags: Optionally, a C{bool} indicating whether or not to
            include the names of child L{Tag}s in the result.  Default is
            C{False}.
        @return: A C{dict} that maps L{Namespace.path}s to C{dict}s with
            information about matching L{Namespace}s, matching the following
            format::

              {<path>: {'tagNames': [<tag-name>, ...],
                        'namespaceNames': [<namespace-name>, ...],
                        'id': <object-id>,
                        'description': <description>}}
        """
        if not paths:
            return {}

        result = getNamespaces(paths=paths)
        values = list(result.values(Namespace.id, Namespace.objectID,
                                    Namespace.path))
        descriptions = (
            self._getDescriptions(objectID for id, objectID, path in values)
            if withDescriptions else None)
        childNamespaces = (self._getChildNamespaces(paths)
                           if withNamespaces else None)
        childTags = self._getChildTags(paths) if withTags else None

        namespaces = {}
        for id, objectID, path in values:
            value = {'id': objectID}
            if withDescriptions:
                value['description'] = descriptions[objectID]
            if withNamespaces:
                value['namespaceNames'] = childNamespaces.get(id, [])
            if withTags:
                value['tagNames'] = childTags.get(id, [])
            namespaces[path] = value
        return namespaces

    def _getDescriptions(self, objectIDs):
        """Get the L{Namespace} descriptions for C{objectIDs}.

        @param objectIDs: A sequence of L{Namespace.objectID}s.
        @return: A C{dict} that maps L{Namespace.objectID}s to descriptions.
        """
        result = self._factory.tagValues(self._user).get(
            objectIDs=objectIDs, paths=[u'fluiddb/namespaces/description'])
        descriptions = {}
        for objectID, value in result.iteritems():
            description = value[u'fluiddb/namespaces/description']
            descriptions[objectID] = description.value
        return descriptions

    def _getChildNamespaces(self, paths):
        """Get the child L{Namespace}s for C{paths}.

        @param paths: A sequence of L{Namespace.path}s.
        @return: A C{dict} that maps L{Namespace.id}s to C{list}s of child
            L{Namespace.name}s.
        """
        childNamespaces = defaultdict(list)
        result = getChildNamespaces(paths)
        for parentID, name in result.values(Namespace.parentID,
                                            Namespace.name):
            childNamespaces[parentID].append(name)
        return childNamespaces

    def _getChildTags(self, paths):
        """Get the child L{Tag}s for C{paths}.

        @param paths: A sequence of L{Namespace.path}s.
        @return: A C{dict} that maps L{Namespace.id}s to C{list}s of child
            L{Tag.name}s.
        """
        childTags = defaultdict(list)
        result = getChildTags(paths)
        for parentID, name in result.values(Tag.namespaceID, Tag.name):
            childTags[parentID].append(name)
        return childTags

    def set(self, values):
        """Set or update L{Namespace}s.

        @param values: A C{dict} mapping L{Namespace.path}s to descriptions.
        @return: A C{list} of C{(objectID, Namespace.path)} 2-tuples
            representing the L{Namespace}s that were updated.
        """
        from fluiddb.model.user import getUser

        paths = set(values.iterkeys())
        result = getNamespaces(paths=paths)
        namespaces = dict(result.values(Namespace.path, Namespace.objectID))
        descriptions = {}
        updatedNamespaces = []
        for path, description in values.iteritems():
            objectID = namespaces[path]
            descriptions[objectID] = {
                u'fluiddb/namespaces/description': description}
            updatedNamespaces.append((objectID, path))

        admin = getUser(u'fluiddb')
        self._factory.tagValues(admin).set(descriptions)
        return updatedNamespaces
