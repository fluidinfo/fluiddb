from fluiddb.data.permission import Operation
from fluiddb.model.comment import CommentAPI
from fluiddb.security.exceptions import PermissionDeniedError
from fluiddb.security.permission import checkPermissions


class SecureCommentAPI(object):
    """The public API to secure L{Comment}-related functionality.

    @param user: The L{User} to perform operations on behalf of.
    """

    def __init__(self, user):
        self._user = user
        self._api = CommentAPI(user)

    def create(self, text, username, about=None, importer=None, when=None,
               url=None):
        """See L{CommentAPI.create}.

        @raise PermissionDeniedError: If the user is the anonymous user.
        """
        if self._user.isAnonymous():
            # Raise a permission denied specifying the path name to just
            # one of the various fluidinfo.com/info/* tags that would need
            # to be written to create a comment object. That's better than
            # returning C{None} as the path.
            raise PermissionDeniedError(
                self._user.username,
                [(u'fluidinfo.com/info/username', Operation.WRITE_TAG_VALUE)])
        else:
            return self._api.create(text, username, about=about,
                                    importer=importer, when=when, url=url)

    def delete(self, importer, username, when):
        """See L{CommentAPI.delete}.

        @raise PermissionDeniedError: If (1) the user is the anonymous user
            or (2) the user making the request is not C{username} and not
            the superuser.
        """
        if self._user.isAnonymous() or (username != self._user.username and
                                        not self._user.isSuperuser()):
            # Raise PermissionDeniedError, specifying the path name to just
            # one of the various fluidinfo.com/info/* tags that would need
            # to be removed to delete a comment object. That's better than
            # returning C{None} as the path.
            raise PermissionDeniedError(
                self._user.username,
                [(u'fluidinfo.com/info/username', Operation.DELETE_TAG_VALUE)])
        else:
            return self._api.delete(importer, username, when)

    def update(self, importer, username, when, newText):
        """See L{CommentAPI.update}.

        @raise PermissionDeniedError: If (1) the user is the anonymous user
            or (2) the user making the request is not C{username} and not
            the superuser.
        """
        if self._user.isAnonymous() or (username != self._user.username and
                                        not self._user.isSuperuser()):
            # Raise PermissionDeniedError, specifying the path name to just
            # one of the various fluidinfo.com/info/* tags that would need
            # to be removed to delete a comment object. That's better than
            # returning C{None} as the path.
            raise PermissionDeniedError(
                self._user.username,
                [(u'fluidinfo.com/info/username', Operation.WRITE_TAG_VALUE)])
        else:
            return self._api.update(importer, username, when, newText)

    def getForObject(self, about, limit=None, olderThan=None, newerThan=None,
                     username=None, followedByUsername=None, filterTags=None,
                     filterAbout=None, additionalTags=None):
        """See L{CommentAPI.getForObject}

        @raise PermissionDeniedError: If the user lacks READ_TAG_VALUE
        permissions on any of the tag paths in additionalTags.
        """
        if additionalTags is not None:
            pathsAndOperations = set((path, Operation.READ_TAG_VALUE)
                                     for path in additionalTags)
            deniedOperations = checkPermissions(self._user, pathsAndOperations)
            if deniedOperations:
                raise PermissionDeniedError(self._user.username,
                                            deniedOperations)
        return self._api.getForObject(about, limit, olderThan, newerThan,
                                      username, followedByUsername, filterTags,
                                      filterAbout, additionalTags)

    def summarizeObject(self, about):
        """See L{CommentAPI.summarizeObject}."""
        return self._api.summarizeObject(about)

    def getRecent(self, limit=None, olderThan=None, newerThan=None,
                  filterTags=None, additionalTags=None):
        """See L{CommentAPI.getRecent}.

        @raise PermissionDeniedError: If the user lacks READ_TAG_VALUE
        permissions on any of the tag paths in additionalTags.
        """
        if additionalTags is not None:
            pathsAndOperations = set((path, Operation.READ_TAG_VALUE)
                                     for path in additionalTags)
            deniedOperations = checkPermissions(self._user, pathsAndOperations)
            if deniedOperations:
                raise PermissionDeniedError(self._user.username,
                                            deniedOperations)
        return self._api.getRecent(limit, olderThan, newerThan, filterTags,
                                   additionalTags)

    def getByUser(self, about, limit=None, olderThan=None, newerThan=None):
        """See L{CommentAPI.getByUser}."""
        return self._api.getByUser(about, limit, olderThan, newerThan)

    def getForUser(self, username, limit=None, olderThan=None, newerThan=None,
                   filterTags=None, filterAbout=None, additionalTags=None):
        """See L{CommentAPI.getForUser}.

        @raise PermissionDeniedError: If the user lacks READ_TAG_VALUE
        permissions on any of the tag paths in additionalTags.
        """
        if additionalTags is not None:
            pathsAndOperations = set((path, Operation.READ_TAG_VALUE)
                                     for path in additionalTags)
            deniedOperations = checkPermissions(self._user, pathsAndOperations)
            if deniedOperations:
                raise PermissionDeniedError(self._user.username,
                                            deniedOperations)
        return self._api.getForUser(username, limit, olderThan, newerThan,
                                    filterTags, filterAbout, additionalTags)

    def getForFollowedObjects(self, username, limit=None, olderThan=None,
                              newerThan=None):
        """See L{CommentAPI.getForFollowedObjects}."""
        return self._api.getForFollowedObjects(username, limit, olderThan,
                                               newerThan)

    def getForFollowedUsers(self, username, limit=None, olderThan=None,
                            newerThan=None):
        """See L{CommentAPI.getForFollowedObjects}."""
        return self._api.getForFollowedUsers(username, limit, olderThan,
                                             newerThan)

    def getAllFollowed(self, username, limit=None, olderThan=None,
                       newerThan=None):
        """See L{CommentAPI.getForFollowedObjects}."""
        return self._api.getAllFollowed(username, limit, olderThan, newerThan)

    def getFollowedObjects(self, username, limit=None, olderThan=None,
                           objectType=None):
        """See L{CommentAPI.getFollowedObjects}."""
        # FIXME This logic skips permission checks.  We assume, maybe in full
        # muppet fashion, that '<username>/follows' is always publicly
        # readable. -jkakar
        return self._api.getFollowedObjects(username, limit, olderThan,
                                            objectType)
