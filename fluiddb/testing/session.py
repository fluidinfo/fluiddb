from fluiddb.application import FluidinfoSession


class login(object):
    """
    A context manager to make it easier to use a L{FluidinfoSession} in unit
    tests.

    @param username: The username to login as.
    @param objectID: The L{User}'s object ID.
    @param transact: The L{Transact} instance to use when running database
        transactions.
    """

    def __init__(self, username, objectID, transact):
        self._username = username
        self._objectID = objectID
        self._transact = transact

    def __enter__(self):
        """Start the L{FluidinfoSession} and login the configured L{User}.

        @return: The authenticated L{FluidinfoSession} instance.
        """
        self._session = FluidinfoSession('id', self._transact)
        self._session.start()
        self._session.auth.login(self._username, self._objectID)
        return self._session

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop the L{FluidinfoSession}."""
        if self._session.running:
            self._session.stop()
