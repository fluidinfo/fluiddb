from uuid import UUID

from twisted.internet.defer import fail

from fluiddb.common.types_thrift.ttypes import (
    TNoSuchUser, TParseError, TBadRequest)
from fluiddb.data.exceptions import UnknownUserError
from fluiddb.query.grammar import QueryParseError
from fluiddb.query.parser import parseQuery, IllegalQueryError
from fluiddb.security.object import SecureObjectAPI
from fluiddb.security.recentactivity import SecureRecentActivityAPI
from fluiddb.security.value import SecureTagValueAPI


class FacadeRecentActivityMixin(object):

    def getRecentObjectActivity(self, session, objectID):
        """Get information about recent tag values on the given object.

        @param session: The L{FluidinfoSession} for the request.
        @param objectID: A C{str} representing the ID of the object.
        @return: A C{list} of C{dict}s matching the following format::

             [{'tag': <path>,
               'id': <object-id>,
               'about': <about-value>,
               'value': <value>,
               'username': <username>,
               'updated-at': <timestamp>},
               ...]
        """
        try:
            objectID = UUID(objectID)
        except ValueError:
            error = TBadRequest('Invalid UUID: %r.' % objectID)
            return fail(error)

        def run():
            recentActivity = SecureRecentActivityAPI(session.auth.user)
            result = recentActivity.getForObjects([objectID])
            return self._formatResult(result)

        return session.transact.run(run)

    def getRecentActivityForQuery(self, session, query):
        """
        Get information about recent tag values on the objects returned by the
        given query.

        @param session: The L{FluidinfoSession} for the request.
        @param query: A UTF-8 C{str} with the query to resolve.
        @return: A C{list} of C{dict}s matching the following format::

             [{'tag': <path>,
               'id': <object-id>,
               'about': <about-value>,
               'value': <value>,
               'username': <username>,
               'updated-at': <timestamp>},
               ...]
        """
        try:
            parsedQuery = parseQuery(query.decode('utf-8'))
        except QueryParseError as error:
            session.log.exception(error)
            return fail(TParseError(query, error.message))
        except IllegalQueryError as error:
            return fail(TBadRequest(str(error)))

        def run():
            objects = SecureObjectAPI(session.auth.user)

            # _resolveQuery is implemented in FacadeTagValueMixin
            objectIDs = self._resolveQuery(session, objects, parsedQuery)

            # FIXME: This sucks, but right now if the query returns too many
            # objects, RecentActivityAPI will blow up. While we fix this, it's
            # better to return a 400 than a 500.
            if len(objectIDs) > 2000:
                raise TBadRequest('The given query returns to many objects.')

            recentActivity = SecureRecentActivityAPI(session.auth.user)
            result = recentActivity.getForObjects(objectIDs)
            return self._formatResult(result)

        return session.transact.run(run)

    def getRecentAboutActivity(self, session, about):
        """Get information about recent tag values on the given object.

        @param session: The L{FluidinfoSession} for the request.
        @param about: A UTF-8 C{str} with the about value for the object.
        @return: A C{list} of C{dict}s matching the following format::

             [{'tag': <path>,
               'id': <object-id>,
               'about': <about-value>,
               'value': <value>,
               'username': <username>,
               'updated-at': <timestamp>},
               ...]
        """
        about = about.decode('utf-8')

        def run():
            objects = SecureObjectAPI(session.auth.user)
            objectID = objects.get([about]).get(about)
            if objectID is None:
                return []
            recentActivity = SecureRecentActivityAPI(session.auth.user)
            result = recentActivity.getForObjects([objectID])
            return self._formatResult(result)

        return session.transact.run(run)

    def getRecentUserActivity(self, session, username):
        """Get information about recent tag values on the given user.

        @param session: The L{FluidinfoSession} for the request.
        @param username: A UTF-8 C{str} with the username.
        @raise: L{TNoSuchUser} if the user doesn't exist.
        @return: A C{list} of C{dict}s matching the following format::

             [{'tag': <path>,
               'id': <object-id>,
               'about': <about-value>,
               'value': <value>,
               'username': <username>,
               'updated-at': <timestamp>},
               ...]
        """
        username = username.decode('utf-8')

        def run():
            recentActivity = SecureRecentActivityAPI(session.auth.user)
            try:
                result = recentActivity.getForUsers([username])
            except UnknownUserError as error:
                session.log.exception(error)
                raise TNoSuchUser(username.encode('utf-8'))
            return self._formatResult(result)

        return session.transact.run(run)

    def getRecentUserActivityForQuery(self, session, query):
        """
        Get information about recent tag values by the users whose objects are
        returned by the given query.

        @param session: The L{FluidinfoSession} for the request.
        @param query: A UTF-8 C{str} with the query to resolve.
        @return: A C{list} of C{dict}s matching the following format::

             [{'tag': <path>,
               'id': <object-id>,
               'about': <about-value>,
               'value': <value>,
               'username': <username>,
               'updated-at': <timestamp>},
               ...]
        """
        try:
            # Extend the query to get only objects for users.
            query = '(%s) AND HAS fluiddb/users/username' % query
            parsedQuery = parseQuery(query.decode('utf-8'))
        except QueryParseError as error:
            session.log.exception(error)
            return fail(TParseError(query, error.message))
        except IllegalQueryError as error:
            return fail(TBadRequest(str(error)))

        def run():
            objects = SecureObjectAPI(session.auth.user)

            # _resolveQuery is implemented in FacadeTagValueMixin
            objectIDs = self._resolveQuery(session, objects, parsedQuery)

            if not objectIDs:
                return []

            # FIXME: This sucks, but right now if the query returns too many
            # objects, RecentActivityAPI will blow up. While we fix this, it's
            # better to return a 400 than a 500.
            if len(objectIDs) > 2000:
                raise TBadRequest('The given query returns to many objects.')

            values = SecureTagValueAPI(session.auth.user)
            result = values.get(objectIDs, [u'fluiddb/users/username'])
            usernames = [result[objectID][u'fluiddb/users/username'].value
                         for objectID in result]

            recentActivity = SecureRecentActivityAPI(session.auth.user)
            result = recentActivity.getForUsers(usernames)
            return self._formatResult(result)

        return session.transact.run(run)

    def _formatResult(self, result):
        """
        Format a result from a call to L{RecentActivityAPI}, converting object
        IDs and datetimes to strings and generating a dictionary with the
        values.

        @param result: A C{list} of C{(Tag.path, TagValue.objectID,
            AboutTagValue.value, TagValue.value, User.username,
            value.creationTime)} 6-tuples with the information about the
            recent tag values.
        @return: A C{list} of C{dict}s matching the following format::

             [{'tag': <path>,
               'id': <object-id>,
               'about': <about-value>,
               'value': <value>,
               'username': <username>,
               'updated-at': <timestamp>},
               ...]
        """
        newResult = []
        for path, objectID, about, value, username, time in result:
            item = {
                'username': username,
                'tag': path,
                'id': str(objectID),
                'about': about,
                'value': value,
                'updated-at': time.isoformat()}
            newResult.append(item)
        return newResult
