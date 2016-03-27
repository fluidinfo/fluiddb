from uuid import UUID

from fluiddb.common.types_thrift.ttypes import TObjectInfo, TUnauthorized
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.security.object import SecureObjectAPI
from fluiddb.security.value import SecureTagValueAPI


class FacadeObjectMixin(object):

    def createObject(self, session, about=None):
        """Create an object.

        If an about value is given and it already exists,
        this will return the object ID that matches the L{AboutTagValue}.

        @param session: The L{AuthenticatedSession} for the request.
        @param about: Optionally, a C{str} for an L{AboutTagValue.value}.
        @raise TUnauthorized: Raised if the L{User} doesn't have permission
            to create an object.
        @return: A C{Deferred} that will fire with a C{str} representing the
            new object's ID.
        """
        if about:
            about = about.decode('utf-8')

        def run():
            try:
                result = SecureObjectAPI(session.auth.user).create(about)
            except PermissionDeniedError as error:
                session.log.exception(error)
                raise TUnauthorized()
            return str(result)

        return session.transact.run(run)

    def getObject(self, session, objectId, showAbout=False):
        """Get information about an object.

        @param session: The L{AuthenticatedSession} for the request.
        @param objectId:: A C{str} for the requested object ID.
        @param showAbout: Optionally, return the about tag value associated
            with the object, if one exists.
        @return: A C{Deferred} that will fire with a L{TObjectInfo} that
            contains the list of L{Tag.path}s for this object that the L{User}
            has L{Operation.READ_TAG_VALUE} permission.
        """
        objectID = UUID(objectId)

        def run():
            result = TObjectInfo()
            objects = SecureObjectAPI(session.auth.user)
            tagPaths = objects.getTagsByObjects([objectID])
            if not tagPaths:
                result.tagPaths = []
                return result

            tagPaths = tagPaths[objectID]
            if showAbout and u'fluiddb/about' in tagPaths:
                tagValues = SecureTagValueAPI(session.auth.user)
                values = tagValues.get([objectID], [u'fluiddb/about'])
                about = values[objectID][u'fluiddb/about'].value
                result.about = about.encode('utf-8')
            result.tagPaths = tagPaths
            return result

        return session.transact.run(run)
