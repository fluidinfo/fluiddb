class DuplicateUserError(Exception):
    """
    Raised when an attempt to create a L{User} with a duplicate name is made.

    @param usernames: A C{list} of the usernames that already exist.
    """

    def __init__(self, usernames):
        self.usernames = usernames

    def __str__(self):
        return "Users with usernames '%s' already exist." \
               % ', '.join(repr(username) for username in self.usernames)


class MalformedPathError(Exception):
    """
    Raised when an attempt to create a L{Namespace} or L{Tag} with a malformed
    path is made.
    """


class MalformedUsernameError(Exception):
    """
    Raised when an attempt to create a L{User} with a malformed username is
    made.
    """


class UnknownUserError(Exception):
    """Raised when an attempt to use an unknown L{User} is made.

    @param username: A sequence of unknown L{User.username}s.
    """

    def __init__(self, usernames):
        self.usernames = usernames

    def __str__(self):
        usernames = u','.join(repr(username) for username in self.usernames)
        return 'Unknown usernames: %s' % usernames
