class PermissionDeniedError(Exception):
    """Raised when an attempt to perform an unauthorized operation is made."""

    def __init__(self, username, pathsAndOperations):
        self.username = username
        self.pathsAndOperations = pathsAndOperations

    def __str__(self):
        pathsAndOperations = ['%s on %r' % (operation, path)
                              for path, operation in self.pathsAndOperations]
        pathsAndOperations = ', '.join(pathsAndOperations)
        return ("User '%s' cannot perform the following operations: %s"
                % (self.username, pathsAndOperations))


class InvalidOAuthTokenError(Exception):
    """Raised if an OAuth token can't be decrypted."""
