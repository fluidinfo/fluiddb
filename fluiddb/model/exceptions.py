class DuplicatePathError(Exception):
    """
    Raised when an attempt to create a L{Namespace} or L{Tag} with a duplicate
    path is made.
    """


class UnknownPathError(Exception):
    """Raised when an attempt to use an unknown L{Namespace} or L{Tag} is made.

    @param paths: A sequence of unknown L{Namespace.path}s or L{Tag.path}s.
    """

    def __init__(self, paths):
        self.paths = list(paths)

    def __str__(self):
        if len(self.paths) > 1:
            paths = u','.join(repr(path) for path in self.paths)
            return 'Unknown paths: %s.' % paths
        elif len(self.paths) == 1:
            return 'Unknown path %r.' % self.paths[0]
        else:
            return 'Unknown path.'


class NotEmptyError(Exception):
    """Raised when an attempt to delete a non-empty L{Namespace} is made."""


class UserNotAllowedInExceptionError(Exception):
    """
    Raised when a user is not allowed to be in a permission exception list.
    """


class UnknownConsumerError(Exception):
    """Raised when an unknown consumer makes an OAuth Echo request."""


class ExpiredOAuthTokenError(Exception):
    """
    Raised when an expired L{OAuthAccessToken} or L{OAuthRenewalToken} is used
    in a request.
    """
