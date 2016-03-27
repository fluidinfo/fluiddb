import time
import random
import logging
from string import ascii_letters

import psycopg2
from storm.exceptions import DisconnectionError
import transaction
from txsolr.errors import HTTPRequestError, HTTPWrongStatus
from twisted.internet import reactor
from twisted.internet.threads import deferToThreadPool


MAX_RETRIES = 3


class Transact(object):
    """Wrap code that needs to interact with the database.

    This wrapper make sure that code interacting with the database is run in a
    separate thread and that the associated transaction is aborted or
    committed in the same thread.

    @param threadPool: The C{ThreadPool} to get threads from.
    @param _transaction: The C{TransactionManager} to use, for test cases only.
    """

    def __init__(self, threadPool, _transaction=None, sleep=None):
        self._threadPool = threadPool
        self._transaction = _transaction or transaction
        self._sleep = sleep or time.sleep

    def run(self, function, *args, **kwargs):
        """Run C{function} in a thread.

        C{function} is run in a thread within a transaction wrapper, which
        commits the transaction if C{function} succeeds.  If it raises an
        exception the transaction is aborted.

        @param function: The function to run.
        @param args: Positional arguments to pass to C{function}.
        @param kwargs: Keyword arguments to pass to C{function}.
        @return: A C{Deferred} that will fire after the function has been run.
        """
        return deferToThreadPool(reactor, self._threadPool, self._transact,
                                 function, *args, **kwargs)

    def _transact(self, function, *args, **kwargs):
        """
        Run C{function} and commit or abort the transaction, depending on the
        outcome.

        If C{function} succeeds, without raising an exception, the transaction
        will be committed and C{function}'s result will be returned.  If
        either C{function} or the commit operation raise an exception, the
        transaction will be aborted and the exception will be re-raised.

        @param function: The function to run.
        @param args: Positional arguments to pass to C{function}.
        @param kwargs: Keyword arguments to pass to C{function}.
        @raise: Any exception raised by C{function} or when a commit is
            attempted.
        @return: The result of invoking C{function}.
        """
        tries = 0
        transactionID = ''.join(random.choice(ascii_letters) for _ in range(6))
        while True:
            try:
                result = function(*args, **kwargs)
                if hasattr(result, '__storm_table__'):
                    raise RuntimeError('Attempted to return a Storm object '
                                       'from a transaction.')
                self._transaction.commit()
                return result
            except (DisconnectionError, psycopg2.Error, HTTPRequestError,
                    HTTPWrongStatus) as error:
                self._transaction.abort()
                if tries < MAX_RETRIES:
                    logging.warning('Retrying a transaction %s due to %r'
                                    % (transactionID, error))
                    tries += 1
                    self._sleep(random.uniform(1, 2 ** tries))
                else:
                    raise
            except:
                self._transaction.abort()
                raise
