from fluiddb.api.util import getCategoryAndAction
from fluiddb.common.types_thrift.ttypes import (
    TTag, TTagAlreadyExists, TNonexistentTag, TPathPermissionDenied,
    TInvalidPath)
from fluiddb.data.exceptions import MalformedPathError
from fluiddb.model.exceptions import DuplicatePathError, UnknownPathError
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.security.tag import SecureTagAPI


class FacadeTagMixin(object):

    def getTag(self, session, path, returnDescription):
        """Get information about a L{Tag}.

        @param session: The L{AuthenticatedSession} for the request.
        @param path: The L{Tag.path} to get information about.
        @param returnDescription: A C{bool} indicating whether or not to
            include the L{Tag}'s description in the result.
        @raise TNonexistentTag: Raised if a L{Tag} called C{path} doesn't
            exist.
        @return: A C{Deferred} that will fire with a L{TTag} object
            representing the L{Tag}.
        """
        path = path.decode('utf-8')

        def run():
            tags = SecureTagAPI(session.auth.user)
            result = tags.get([path], withDescriptions=returnDescription)

            if not result:
                raise TNonexistentTag()
            else:
                tag = TTag()
                tag.objectId = str(result[path]['id'])
                tag.path = path
                tag.indexed = True
                if returnDescription:
                    tag.description = result[path]['description']
                return tag

        return session.transact.run(run)

    def createTag(self, session, parentNamespace, name, description, indexed,
                  rangeType):
        """Create a new L{Tag}.

        A new L{Tag} is created along with C{fluiddb/tags/description} and
        C{fluiddb/tags/path} L{TagValue}s.  Documents for these values are
        created in the L{ObjectIndex}.

        @param session: The L{AuthenticatedSession} for the request.
        @param parentNamespace: The path of the parent L{Namespace}.
        @param name: The name of the new L{Tag}.
        @param description: The description for the new L{Tag}.
        @param indexed: Always ignored, only present for backwards
            compatibility.
        @param rangeType: Always ignored, only present for backwards
            compatibility.
        @raise TTagAlreadyExists: If the L{Tag} already exists.
        @raise TNonexistentTag: If the parent L{Namespace} does not exist.
        @raise TPathPermissionDenied: If the user doesn't have CREATE
            permissions on the parent L{Namespace}.
        @raise TInvalidPath: If the path of the new L{Tag} is not well formed.
        @return: A C{Deferred} that will fire with the object ID for the new
            L{Tag}.
        """
        parentNamespace = parentNamespace.decode('utf-8')
        name = name.decode('utf-8')
        description = description.decode('utf-8')

        def run():
            tags = SecureTagAPI(session.auth.user)
            path = u'/'.join([parentNamespace, name])
            try:
                [(objectID, _)] = tags.create([(path, description)])
            except DuplicatePathError as error:
                session.log.exception(error)
                raise TTagAlreadyExists(path.encode('utf-8'))
            except UnknownPathError as error:
                session.log.exception(error)
                path = error.paths[0]
                raise TNonexistentTag(path.encode('utf-8'))
            except PermissionDeniedError as error:
                session.log.exception(error)
                deniedPath, operation = error.pathsAndOperations[0]
                deniedPath = deniedPath.encode('utf-8')
                category, action = getCategoryAndAction(operation)
                raise TPathPermissionDenied(category, action, deniedPath)
            except MalformedPathError as error:
                session.log.exception(error)
                raise TInvalidPath(path.encode('utf-8'))

            return str(objectID)

        return session.transact.run(run)

    def updateTag(self, session, path, description):
        """Update the description for a L{Tag}.

        The C{fluiddb/tags/description} L{Tag} is updated and its value is
        updated in the L{ObjectIndex}.

        @param session: The L{AuthenticatedSession} for the request.
        @param path: The L{Tag.path} to update.
        @param description: The description for the L{Tag}.
        @return: A C{Deferred} that will fire when the request finishes.
        """
        path = path.decode('utf-8')

        def run():
            value = {path: description}
            try:
                SecureTagAPI(session.auth.user).set(value)
            except UnknownPathError as error:
                session.log.exception(error)
                raise TNonexistentTag(path.encode('utf-8'))
            except PermissionDeniedError as error:
                session.log.exception(error)
                deniedPath, operation = error.pathsAndOperations[0]
                deniedPath = deniedPath.encode('utf-8')
                category, action = getCategoryAndAction(operation)
                raise TPathPermissionDenied(category, action, deniedPath)

        return session.transact.run(run)

    def deleteTag(self, session, path):
        """Delete a L{Tag}.

        L{TagValue}s associated with a L{Tag} are deleted automatically when
        its removed.  The L{ObjectIndex} is also updated when a L{Tag} is
        deleted:

          1. All documents associated with the deleted L{Tag.objectID} are
             removed.  This destroys documents for C{fluiddb/tags/path} and
             C{fluiddb/tags/description} tag values stored for the tag.
          2. All documents associated with the deleted L{Tag.path} are
             removed.  This removes documents for all associated L{TagValue}s.

        @param session: The L{AuthenticatedSession} for the request.
        @param path: The L{Tag.path} to delete.
        @return: A C{Deferred} that will fire when the request is finished.
        """
        path = path.decode('utf-8')

        def run():
            try:
                SecureTagAPI(session.auth.user).delete([path])
            except UnknownPathError as error:
                session.log.exception(error)
                raise TNonexistentTag(path.encode('utf-8'))
            except PermissionDeniedError as error:
                session.log.exception(error)
                deniedPath, operation = error.pathsAndOperations[0]
                deniedPath = deniedPath.encode('utf-8')
                category, action = getCategoryAndAction(operation)
                raise TPathPermissionDenied(category, action, deniedPath)

        return session.transact.run(run)
