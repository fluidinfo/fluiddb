from inspect import isgenerator

from fluiddb.data.namespace import Namespace, getNamespaces
from fluiddb.data.object import touchObjects
from fluiddb.data.path import getPathName, getParentPath, getParentPaths
from fluiddb.data.permission import (
    createTagPermission, getNamespacePermissions)
from fluiddb.data.tag import Tag, createTag, getTags
from fluiddb.data.value import getObjectIDs
from fluiddb.exceptions import FeatureError
from fluiddb.model.exceptions import DuplicatePathError, UnknownPathError
from fluiddb.model.factory import APIFactory
from fluiddb.model.user import getUser


class TagAPI(object):
    """The public API for L{Tag}s in the model layer.

    @param user: The L{User} to perform operations on behalf of.
    @param factory: Optionally, the API factory to use when creating internal
        APIs.  Default is L{APIFactory}.
    """

    def __init__(self, user, factory=None):
        self._user = user
        self._factory = factory or APIFactory()

    def create(self, values):
        """Create new L{Tag}s.

        L{Namespace}s that don't exist are created automatically before
        L{Tag}s are created.  Associated L{NamespacePermission} and
        L{TagPermission}s are created automatically with the system-wide
        default permissions.

        @param values: A sequence of C{(Tag.path, description)} 2-tuples.
        @raise DuplicatePathError: Raised if the path for a new L{Tag}
            collides with an existing one.
        @raise FeatureError: Raised if the given list of values is empty.
        @raise UnknownParentPathError: Raised if the parent for a new L{Tag}
            can't be found.
        @raise MalformedPathError: Raised if one of the given paths is empty
            or has unacceptable characters.
        @return: A C{list} of C{(objectID, path)} 2-tuples for the new L{Tag}s.
        """
        if not values:
            raise FeatureError("Can't create an empty list of tags.")

        # Make sure tag paths don't exist before trying to create new tags.
        paths = [path for path, _ in values]
        existingPaths = list(getTags(paths=paths).values(Tag.path))
        if existingPaths:
            raise DuplicatePathError(
                'Paths already exist: %s' % ', '.join(existingPaths))

        # Get intermediate namespaces.  If they don't exist, create them
        # automatically.
        paths = [path for (path, _) in values]
        parentPaths = getParentPaths(paths)
        missingParentPaths = self._getMissingNamespaces(parentPaths)
        self._factory.namespaces(self._user).create(
            [(path, u'Object for the namespace %s' % path)
             for path in missingParentPaths])

        # Create the new tags.
        result = getNamespaces(paths=parentPaths)
        parentNamespaces = dict((namespace.path, namespace)
                                for namespace in result)
        return self._createTags(values, parentNamespaces)

    def _getMissingNamespaces(self, paths):
        """Get a C{set} of missing L{Namespace.path}s.

        @param paths: The L{Namespace.path}s to get.
        @return: A C{set} of missing L{Namespace.path}s.
        """
        if paths:
            result = getNamespaces(paths=paths)
            return paths - set(result.values(Namespace.path))
        else:
            return set()

    def _createTags(self, values, parentNamespaces):
        """Create new tags.

        @param values: A sequence of C{(Tag.path, description)} 2-tuples.
        @param parentNamespaces: A C{dict} mapping L{Namespace.path}s to
            L{Namespace} instances, the parents of the new L{Tag}s.
        @return: A C{list} of C{(objectID, Tag.path)} 2-tuples.
        """
        admin = getUser(u'fluiddb')
        objects = self._factory.objects(admin)
        systemValues = {}
        result = []
        tags = []
        for path, description in values:
            parentPath = getParentPath(path)
            name = getPathName(path)
            parentNamespace = parentNamespaces.get(parentPath)
            tag = createTag(self._user, parentNamespace, name)
            tag.objectID = objects.create(
                u'Object for the attribute %s' % path)
            result.append((tag.objectID, path))
            systemValues[tag.objectID] = {
                u'fluiddb/tags/description': description,
                u'fluiddb/tags/path': path
            }
            tags.append(tag)
        self._createPermissions(tags)

        if systemValues:
            self._factory.tagValues(admin).set(systemValues)

        return result

    def _createPermissions(self, tags):
        """Create L{TagPermission}s for new L{Tag}s.

        L{Tag}s inherit permissions from their parent tag, if one
        is available.

        @param tags: A sequence of new L{Tag}s to create
            L{TagPermission}s for.
        """
        # Preload parent Namespace and NamespacePermission's into Storm's
        # cache.  Simply creating the objects will be enough to get them into
        # the cache.  If there are many objects we need to be careful about
        # overloading the cache, but that isn't an issue here.
        parentPaths = [getParentPath(tag.path) for tag in tags]
        list(getNamespacePermissions(parentPaths))
        for tag in tags:
            createTagPermission(tag)

    def delete(self, paths):
        """Delete L{Tag}s matching C{paths}.

        L{TagValue}s and permissions associated with the deleted L{Tag}s are
        removed by cascading deletes in the database schema.

        @param paths: A sequence of L{Tag.path}s.
        @return: A C{list} of C{(objectID, Tag.path)} 2-tuples representing the
            L{Tag}s that were removed.
        """
        if isgenerator(paths):
            paths = list(paths)
        result = getTags(paths=paths)
        deletedTagPaths = list(result.values(Tag.objectID, Tag.path))
        # Delete the fluiddb/tags/description tag values stored for removed
        # tags.  Associated TagValue's are removed by an ON DELETE CASCADE
        # trigger.
        self._factory.tagValues(self._user).delete(
            [(objectID, path) for objectID, _ in deletedTagPaths
             for path in [u'fluiddb/tags/description', u'fluiddb/tags/path']])

        # Touch all the objects for the given tag paths.
        objectIDs = list(getObjectIDs(paths))
        touchObjects(objectIDs)

        result.remove()
        return deletedTagPaths

    def get(self, paths, withDescriptions=None):
        """Get information about L{Tag}s matching C{paths}.

        @param paths: A sequence of L{Tag.path}s.
        @param withDescriptions: Optionally, a C{bool} indicating whether or
            not to include L{Tag} descriptions in the result.  Default is
            C{False}.
        @return: A C{dict} that maps L{Tag.path}s to C{dict}s with information
            about matching L{Tag}s, matching the following format::

              {<path>: {'id': <object-id>,
                        'description': <description>}}
        """
        if not paths:
            raise FeatureError("Can't retrieve an empty list of tags.")

        result = getTags(paths=paths)
        values = list(result.values(Tag.path, Tag.objectID))
        descriptions = (
            self._getDescriptions(objectID for path, objectID in values)
            if withDescriptions else None)

        tags = {}
        for path, objectID in values:
            value = {'id': objectID}
            if withDescriptions:
                value['description'] = descriptions.get(objectID, u'')
            tags[path] = value
        return tags

    def _getDescriptions(self, objectIDs):
        """Get the L{Tag} descriptions for C{objectIDs}.

        @param objectIDs: A sequence of L{Tag.objectID}s.
        @return: A C{dict} that maps L{Tag.objectID}s to descriptions.
        """
        result = self._factory.tagValues(self._user).get(
            objectIDs=objectIDs, paths=[u'fluiddb/tags/description'])
        descriptions = {}
        for objectID, value in result.iteritems():
            description = value[u'fluiddb/tags/description']
            descriptions[objectID] = description.value
        return descriptions

    def set(self, values):
        """Set or update L{Tag}s.

        @param values: A C{dict} mapping L{Tag.path}s to descriptions.
        @return: A C{list} of C{(objectID, Tag.path)} 2-tuples representing the
            L{Tag}s that were updated.
        """
        result = []
        paths = set(values.iterkeys())
        tags = dict(getTags(paths=paths).values(Tag.path, Tag.objectID))
        descriptions = {}
        for path, description in values.iteritems():
            if path not in tags:
                raise UnknownPathError([path])
            objectID = tags[path]
            descriptions[objectID] = {u'fluiddb/tags/description': description}
            result.append((objectID, path))

        admin = getUser(u'fluiddb')
        self._factory.tagValues(admin).set(descriptions)
        return result
