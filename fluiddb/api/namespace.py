from fluiddb.api.util import getCategoryAndAction
from fluiddb.common.types_thrift.ttypes import (
    TPathPermissionDenied, TNonexistentNamespace, TNamespace,
    TNamespaceAlreadyExists, TNamespaceNotEmpty, TInvalidPath)
from fluiddb.data.exceptions import MalformedPathError
from fluiddb.model.exceptions import (
    DuplicatePathError, UnknownPathError, NotEmptyError)
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.security.namespace import SecureNamespaceAPI


class FacadeNamespaceMixin(object):

    def getNamespace(self, session, path, returnDescription, returnNamespaces,
                     returnTags):
        """Get information about a L{Namespace}.

        @param session: The L{AuthenticatedSession} for the request.
        @param path: The L{Namespace.path} to get information about.
        @param returnDescription: A C{bool} indicating whether or not to
            include L{Namespace.description}s in the result.
        @param returnNamespaces: A C{bool} indicating whether or not to
            include the names of child L{Namespace}s in the result.
        @param returnTags: A C{bool} indicating whether or not to include the
            names of child L{Tag}s in the resulttr
        @return: A C{Deferred} that will fire with an object representing a
            namespace.
        """
        # FIXME The caller should really be providing the path as a unicode
        # value.
        path = path.decode('utf-8')

        def run():
            namespaces = SecureNamespaceAPI(session.auth.user)
            try:
                result = namespaces.get([path],
                                        withDescriptions=returnDescription,
                                        withNamespaces=returnNamespaces,
                                        withTags=returnTags)
            except UnknownPathError as error:
                unknownPath = error.paths.pop()
                raise TNonexistentNamespace(unknownPath.encode('utf-8'))
            except PermissionDeniedError as error:
                session.log.exception(error)
                path_, operation = error.pathsAndOperations[0]
                category, action = getCategoryAndAction(operation)
                raise TPathPermissionDenied(path_, category, action)

            if not result:
                raise TNonexistentNamespace(path.encode('utf-8'))
            else:
                namespace = TNamespace()
                namespace.objectId = str(result[path]['id'])
                namespace.path = path
                if returnDescription:
                    namespace.description = result[path]['description']
                if returnNamespaces:
                    namespace.namespaces = result[path]['namespaceNames']
                if returnTags:
                    namespace.tags = result[path]['tagNames']
                return namespace

        return session.transact.run(run)

    def createNamespace(self, session, parentNamespace, name, description):
        """Create a new L{Namespace}.

        @param session: The L{AuthenticatedSession} for the request.
        @param parentNamespace: The path of the parent L{Namespace}.
        @param name: The name of the new L{Namespace}.
        @param description: The description for the new L{Namespace}.
        @raise TNamespaceAlreadyExists: If the L{Namespace} already exists.
        @raise TNonexistentNamespace: If the parent L{Namespace} does not
            exist.
        @raise TPathPermissionDenied: If the user doesn't have CREATE
            permissions on the parent L{Namespace}.
        @raise TInvalidPath: If the path of the new L{Namespace} is not well
            formed.
        @return: A C{Deferred} that will fire with the object ID for the new
            L{Namespace}.
        """
        parentNamespace = parentNamespace.decode('utf-8')
        name = name.decode('utf-8')
        description = description.decode('utf-8')

        def run():
            namespaces = SecureNamespaceAPI(session.auth.user)
            path = u'/'.join([parentNamespace, name])
            try:
                result = namespaces.create([(path, description)])
                [objectID] = [objectID for objectID, path_ in result
                              if path_ == path]
            except DuplicatePathError as error:
                session.log.exception(error)
                raise TNamespaceAlreadyExists(path.encode('utf-8'))
            except UnknownPathError as error:
                session.log.exception(error)
                unknownPath = error.paths[0]
                raise TNonexistentNamespace(unknownPath.encode('utf-8'))
            except PermissionDeniedError as error:
                session.log.exception(error)
                path, operation = error.pathsAndOperations[0]
                category, action = getCategoryAndAction(operation)
                path = path.encode('utf-8')
                raise TPathPermissionDenied(path, category, action)
            except MalformedPathError as error:
                session.log.exception(error)
                raise TInvalidPath(path.encode('utf-8'))
            return str(objectID)

        return session.transact.run(run)

    def updateNamespace(self, session, path, description):
        """Update the description for a L{Namespace}.

        @param session: The L{AuthenticatedSession} for the request.
        @param path: The L{Namespace.path} to update.
        @param description: The description for the L{Namespace}.
        """
        path = path.decode('utf-8')
        description = description.decode('utf-8')

        def run():
            namespaces = SecureNamespaceAPI(session.auth.user)
            try:
                namespaces.set({path: description})
            except UnknownPathError as error:
                session.log.exception(error)
                unknownPath = error.paths[0]
                raise TNonexistentNamespace(unknownPath.encode('utf-8'))
            except PermissionDeniedError as error:
                session.log.exception(error)
                path_, operation = error.pathsAndOperations[0]
                category, action = getCategoryAndAction(operation)
                path_ = path_.encode('utf-8')
                raise TPathPermissionDenied(path_, category, action)

        return session.transact.run(run)

    def deleteNamespace(self, session, path):
        """Delete a L{Namespace}.

        @param session: The L{AuthenticatedSession} for the request.
        @param path: The L{Namespace.path} to delete.
        """
        path = path.decode('utf-8')

        def run():
            namespaces = SecureNamespaceAPI(session.auth.user)
            try:
                namespaces.delete([path])
            except UnknownPathError as error:
                session.log.exception(error)
                unknownPath = error.paths[0]
                raise TNonexistentNamespace(unknownPath.encode('utf-8'))
            except NotEmptyError as error:
                session.log.exception(error)
                raise TNamespaceNotEmpty(path.encode('utf-8'))
            except PermissionDeniedError as error:
                session.log.exception(error)
                path_, operation = error.pathsAndOperations[0]
                category, action = getCategoryAndAction(operation)
                path_ = path_.encode('utf-8')
                raise TPathPermissionDenied(path_, category, action)

        return session.transact.run(run)
