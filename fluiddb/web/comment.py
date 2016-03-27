from datetime import datetime

from twisted.internet.defer import fail

from fluiddb.data.path import isValidPath
from fluiddb.model.comment import parseCommentURL
from fluiddb.model.exceptions import UnknownPathError
from fluiddb.security.comment import SecureCommentAPI
from fluiddb.web.jsonrpc import JSONRPCResource, JSONRPCError


def _validateAdditionalTags(additionalTags):
    """Validate a list of tag paths and raise a JSONRPCError if any are
    invalid.
    """
    if additionalTags is not None:
        for path in additionalTags:
            if not isinstance(path, unicode):
                raise JSONRPCError(
                    "Non-unicode element found in additionalTags.")
            if not isValidPath(path):
                raise JSONRPCError(
                    "%r is not a valid path for additionalTags." % path)


class CommentResource(JSONRPCResource):
    """Process incoming comment payloads."""

    def jsonrpc_addComment(self, session, text=None, about=None,
                           creationTime=None):
        """Add a comment to Fluidinfo.

        @param session: A L{FluidinfoSession} instance.
        @param text: The C{unicode} text of the comment.
        @param about: Optionally, the C{unicode} value the comment was about.
        @param creationTime: Optionally, an ISO 8601 extended format date
            representing the time the comment was created.
        @raise JSONRPCError: Returned when C{text} is missing or empty, or
            when C{creationTime} cannot be parsed.
        @return: A C{Deferred} that fires with a C{dict} matching the
            following format::

              {'fluidinfo.com/info/about': ['<about1>', '<about2>', ...],
               'fluidinfo.com/info/text': '<comment-text>',
               'fluidinfo.com/info/timestamp': <utc-timestamp-float>,
               'fluidinfo.com/info/url': '<comment-url>',
               'fluidinfo.com/info/username': '<username>'}
        """
        if not text or text.strip() == '':
            return fail(
                JSONRPCError('Comment text non-existent or just whitespace.'))
        if creationTime is not None:
            try:
                creationTime = datetime.strptime(creationTime,
                                                 '%Y-%m-%dT%H:%M:%S.%f')
            except ValueError:
                return fail(JSONRPCError('Creation time is malformed.'))

        if about is not None:
            # SecureCommentAPI expects a list of about values.
            about = [about]

        def run():
            api = SecureCommentAPI(session.auth.user)
            return api.create(text, session.auth.username, about=about,
                              when=creationTime)

        return session.transact.run(run)

    def jsonrpc_delete(self, session, url):
        """Delete a comment.

        @param session: A L{FluidinfoSession} instance.
        @param url: The URL of the comment to delete.
        @return: A C{dict} matching the following format::

              {deletedComments: <count>}
        """
        if not url or url.strip() == '':
            return fail(
                JSONRPCError('URL is missing or just contains whitespace.'))
        try:
            importer, username, when = parseCommentURL(url)
        except ValueError as error:
            return fail(JSONRPCError(str(error)))

        def run(importer, username, when):
            api = SecureCommentAPI(session.auth.user)
            return {'deletedComments': api.delete(importer, username, when)}

        return session.transact.run(run, importer, username, when)

    def jsonrpc_update(self, session, url, newText):
        """Update the text of a comment.

        @param session: A L{FluidinfoSession} instance.
        @param url: The URL of the comment to update.
        @param newText: The URL of the comment to update.
        @return: A C{dict} matching the following format::

              {'fluidinfo.com/info/about': ['<about1>', '<about2>', ...],
               'fluidinfo.com/info/text': '<comment-text>',
               'fluidinfo.com/info/timestamp': <utc-timestamp-float>,
               'fluidinfo.com/info/url': '<comment-url>',
               'fluidinfo.com/info/username': '<username>'}
        """
        if not url or url.strip() == '':
            return fail(
                JSONRPCError('URL is missing or just contains whitespace.'))
        try:
            importer, username, when = parseCommentURL(url)
        except ValueError as error:
            return fail(JSONRPCError(str(error)))

        def run(importer, username, when, newText):
            api = SecureCommentAPI(session.auth.user)
            return api.update(importer, username, when, newText)

        return session.transact.run(run, importer, username, when, newText)

    def jsonrpc_getForObject(self, session, about, nextPageID=None,
                             currentPageID=None, username=None,
                             followedByUsername=None, filterTags=None,
                             filterAbout=None, additionalTags=None):
        """Get the comments made for a particular object.

        @param session: A L{FluidinfoSession} instance.
        @param about: The about value of the object to get the comments from.
        @param nextPageID: Optionally, a symbol that represents the next page
            to fetch values for.
        @param currentPageID: Optionally, a symbol that represents the page
            with the comments previously fetched, returning only new values.
        @param username: Optionally, only return comments made by the
            specified L{User.username}.
        @param followedByUsername: Optionally, only return comments made by
            L{User}s that the specified L{User.username} follows.
        @param filterTags: Optionally a C{list} of tag paths. If not C{None},
            return only comment objects with _all_ of the specified tag paths.
        @param filterAbout: Optionally, return only comments made on a given
            object.
        @param additionalTags: Optionally, a list of paths of additional tags
            to retrieve.
        @return: A C{dict} with comments, ordered from newest to eldest,
            matching the following format::

              {nextPageID: '...',
               currentPageID: '...',
               comments: [
                   {'fluidinfo.com/info/about': ['<about1>', '<about2>', ...],
                    'fluidinfo.com/info/text': '<comment-text>',
                    'fluidinfo.com/info/timestamp': <float-timestamp>,
                    'fluidinfo.com/info/url': '<url>',
                    'fluidinfo.com/info/username': '<username>'},
                   ...]}
        """
        try:
            _validateAdditionalTags(additionalTags)
        except JSONRPCError as error:
            return fail(error)

        try:
            nextPageID = (datetime.utcfromtimestamp(nextPageID)
                          if nextPageID else None)
        except TypeError:
            return fail(JSONRPCError("Couldn't parse nextPageID."))

        try:
            currentPageID = (datetime.utcfromtimestamp(currentPageID)
                             if currentPageID else None)
        except TypeError:
            return fail(JSONRPCError("Couldn't parse currentPageID."))

        def run(nextPageID, currentPageID, username, followedByUsername,
                filterTags, filterAbout, additionalTags):
            api = SecureCommentAPI(session.auth.user)
            try:
                comments = api.getForObject(about, username=username,
                                            followedByUsername=
                                            followedByUsername,
                                            filterTags=filterTags,
                                            filterAbout=filterAbout,
                                            limit=26, olderThan=nextPageID,
                                            newerThan=currentPageID,
                                            additionalTags=additionalTags)
            except UnknownPathError as error:
                raise JSONRPCError("Unknown path in additionalTags: '%s'." %
                                   error.paths[0].encode('utf-8'))
            nextPageID = None
            if len(comments) == 26:
                nextPageID = comments[-2][u'fluidinfo.com/info/timestamp']
                comments = comments[:-1]
            currentPageID = (comments[0][u'fluidinfo.com/info/timestamp']
                             if comments else None)
            return {'currentPageID': currentPageID,
                    'nextPageID': nextPageID,
                    'comments': comments}

        return session.transact.run(run, nextPageID, currentPageID, username,
                                    followedByUsername, filterTags,
                                    filterAbout, additionalTags)

    def jsonrpc_summarizeObject(self, session, about):
        """Get summary information for an object.

        @param session: A L{FluidinfoSession} instance.
        @param about: The about value of the object to summarize.
        @raise JSONRPCError: Fired by the C{Deferred} when the about value is
            empty or only contains whitespace.
        @return: A C{Deferred} that will fire with an object matching the
            following format::

              {'comment-count':   <count>,
               'followers':       [<username>, ...],
               'related-objects': {'<about>': <count>, ...}}
        """
        if not about or about.strip() == '':
            return fail(JSONRPCError('Need an about value.'))

        def run():
            api = SecureCommentAPI(session.auth.user)
            return api.summarizeObject(about)

        return session.transact.run(run)

    def jsonrpc_getForUser(self, session, username, nextPageID=None,
                           currentPageID=None, filterTags=None,
                           filterAbout=None, additionalTags=None):
        """Get the comments made by a particuar user.

        @param session: A L{FluidinfoSession} instance.
        @param about: The about value of the object to get the comments from.
        @param nextPageID: Optionally, a symbol that represents the next page
            to fetch values for.
        @param currentPageID: Optionally, a symbol that represents the page
            with the comments previously fetched, returning only new values.
        @param filterTags: Optionally a C{list} of tag paths. If not C{None},
            return only comment objects with _all_ of the specified tag paths.
        @param filterAbout: Optionally, return only comments made on a given
            object.
        @param additionalTags: Optionally, a list of paths of additional tags
            to retrieve.
        @return: A C{dict} with comments, ordered from newest to eldest,
            matching the following format::

              {nextPageID: '...',
               currentPageID: '...',
               comments: [
                   {'fluidinfo.com/info/about': ['<about1>', '<about2>', ...],
                    'fluidinfo.com/info/text': '<comment-text>',
                    'fluidinfo.com/info/timestamp': <float-timestamp>,
                    'fluidinfo.com/info/url': '<url>',
                    'fluidinfo.com/info/username': '<username>'},
                   ...]}
        """
        try:
            _validateAdditionalTags(additionalTags)
        except JSONRPCError as error:
            return fail(error)

        try:
            nextPageID = (datetime.utcfromtimestamp(nextPageID)
                          if nextPageID else None)
        except TypeError:
            return fail(JSONRPCError("Couldn't parse nextPageID."))

        try:
            currentPageID = (datetime.utcfromtimestamp(currentPageID)
                             if currentPageID else None)
        except TypeError:
            return fail(JSONRPCError("Couldn't parse currentPageID."))

        def run(nextPageID, currentPageID, filterTags, filterAbout,
                additionalTags):
            api = SecureCommentAPI(session.auth.user)
            comments = api.getForUser(username, limit=26, olderThan=nextPageID,
                                      newerThan=currentPageID,
                                      filterTags=filterTags,
                                      filterAbout=filterAbout,
                                      additionalTags=additionalTags)
            nextPageID = None
            if len(comments) == 26:
                nextPageID = comments[-2][u'fluidinfo.com/info/timestamp']
                comments = comments[:-1]
            currentPageID = (comments[0][u'fluidinfo.com/info/timestamp']
                             if comments else None)
            return {'currentPageID': currentPageID,
                    'nextPageID': nextPageID,
                    'comments': comments}

        return session.transact.run(run, nextPageID, currentPageID, filterTags,
                                    filterAbout, additionalTags)

    def jsonrpc_getAllFollowed(self, session, username, nextPageID=None,
                               currentPageID=None):
        """Get the comments made for all the followed objects and users.

        @param session: A L{FluidinfoSession} instance.
        @param username: The username of the user following the objects.
        @param nextPageID: Optionally, a symbol that represents the next page
            to fetch values for.
        @param currentPageID: Optionally, a symbol that represents the page
            with the comments previously fetched, returning only new values.
        @return: A C{dict} with comments, ordered from newest to oldest,
            matching the following format::

              {nextPageID: '...',
               currentPageID: '...',
               comments: [
                   {'fluidinfo.com/info/about': ['<about1>', '<about2>', ...],
                    'fluidinfo.com/info/text': '<comment-text>',
                    'fluidinfo.com/info/timestamp': <float-timestamp>,
                    'fluidinfo.com/info/url': '<url>',
                    'fluidinfo.com/info/username': '<username>'},
                   ...]}
        """
        try:
            nextPageID = (datetime.utcfromtimestamp(nextPageID)
                          if nextPageID else None)
        except TypeError:
            return fail(JSONRPCError("Couldn't parse nextPageID."))

        try:
            currentPageID = (datetime.utcfromtimestamp(currentPageID)
                             if currentPageID else None)
        except TypeError:
            return fail(JSONRPCError("Couldn't parse currentPageID."))

        def run(nextPageID, currentPageID):
            api = SecureCommentAPI(session.auth.user)
            comments = api.getAllFollowed(username, limit=26,
                                          olderThan=nextPageID,
                                          newerThan=currentPageID)
            nextPageID = None
            if len(comments) == 26:
                nextPageID = comments[-2][u'fluidinfo.com/info/timestamp']
                comments = comments[:-1]
            currentPageID = (comments[0][u'fluidinfo.com/info/timestamp']
                             if comments else None)
            return {'currentPageID': currentPageID,
                    'nextPageID': nextPageID,
                    'comments': comments}

        return session.transact.run(run, nextPageID, currentPageID)

    def jsonrpc_getRecent(self, session, nextPageID=None, currentPageID=None,
                          filterTags=None, additionalTags=None):
        """Get recent comments.

        @param session: A L{FluidinfoSession} instance.
        @param nextPageID: Optionally, a symbol that represents the next page
            to fetch values for.
        @param currentPageID: Optionally, a symbol that represents the page
            with the comments previously fetched, returning only new values.
        @param filterTags: Optionally a C{list} of tag paths. If not C{None},
            return only comment objects with _all_ of the specified tag paths.
        @param additionalTags: Optionally, a list of paths of additional tags
            to retrieve.
        @return: A C{dict} with comments, ordered from newest to oldest,
            matching the following format::

              {nextPageID: '...',
               currentPageID: '...',
               comments: [
                   {'fluidinfo.com/info/about': ['<about1>', '<about2>', ...],
                    'fluidinfo.com/info/text': '<comment-text>',
                    'fluidinfo.com/info/timestamp': <float-timestamp>,
                    'fluidinfo.com/info/url': '<url>',
                    'fluidinfo.com/info/username': '<username>'},
                   ...]}
        """
        try:
            _validateAdditionalTags(additionalTags)
        except JSONRPCError as error:
            return fail(error)

        try:
            nextPageID = (datetime.utcfromtimestamp(nextPageID)
                          if nextPageID else None)
        except TypeError:
            return fail(JSONRPCError("Couldn't parse nextPageID."))

        try:
            currentPageID = (datetime.utcfromtimestamp(currentPageID)
                             if currentPageID else None)
        except TypeError:
            return fail(JSONRPCError("Couldn't parse currentPageID."))

        def run(nextPageID, currentPageID, filterTags, additionalTags):
            api = SecureCommentAPI(session.auth.user)
            comments = api.getRecent(limit=26,
                                     olderThan=nextPageID,
                                     newerThan=currentPageID,
                                     filterTags=filterTags,
                                     additionalTags=additionalTags)
            nextPageID = None
            if len(comments) == 26:
                nextPageID = comments[-2][u'fluidinfo.com/info/timestamp']
                comments = comments[:-1]
            currentPageID = (comments[0][u'fluidinfo.com/info/timestamp']
                             if comments else None)
            return {'currentPageID': currentPageID,
                    'nextPageID': nextPageID,
                    'comments': comments}

        return session.transact.run(run, nextPageID, currentPageID, filterTags,
                                    additionalTags)

    def jsonrpc_getFollowedObjects(self, session, username, nextPageID=None,
                                   objectType=None):
        """Get the objects followed by the specified user.

        @param session: A L{FluidinfoSession} instance.
        @param username: The username of the user following the objects.
        @param nextPageID: Optionally, a C{unicode} that represents the next
            page to fetch values for.
        @param objectType: Optionally, the object type to filter from the
            objects. The allowed values are C{url}, C{user} and C{hashtag}.
        @return: A C{dict} with followed objects, ordered from newest to
            oldest, matching the following format::

              {nextPageID: '...',
               objects: [
                   {'about': '<about>',
                    'creationTime': '<float-timestamp>',
                    'following': '<boolean>'},
                   ...]}
        """
        try:
            nextPageID = (datetime.utcfromtimestamp(nextPageID)
                          if nextPageID else None)
        except TypeError:
            return fail(JSONRPCError("Couldn't parse nextPageID."))

        if objectType not in (None, 'user', 'url', 'hashtag'):
            return fail(JSONRPCError("Unknown object type: %r." % objectType))

        def run(nextPageID, objectType):
            api = SecureCommentAPI(session.auth.user)
            result = api.getFollowedObjects(username, limit=21,
                                            olderThan=nextPageID,
                                            objectType=objectType)

            objects = [{'about': followedObject['about'],
                       'following': followedObject['following']}
                       for followedObject in result]
            nextPageID = None
            if len(result) == 21:
                nextPageID = result[-2][u'creationTime']
                objects = objects[:-1]
            return {'nextPageID': nextPageID, 'objects': objects}

        return session.transact.run(run, nextPageID, objectType)
