import psycopg2
from storm.exceptions import DisconnectionError
import transaction
from twisted.internet.defer import inlineCallbacks

from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.doubles import FakeThreadPool
from fluiddb.testing.resources import LoggingResource
from fluiddb.util.transact import Transact


class TransactTest(FluidinfoTestCase):

    resources = [('log', LoggingResource(format='%(message)s'))]

    @inlineCallbacks
    def testRun(self):
        """
        L{Transact.run} executes a function in a thread, commits the
        transaction and returns a C{Deferred} that fires with the function's
        result.
        """

        class FakeTransactionManager(object):

            def commit(self):
                self.committed = True

        def function(a, b=None):
            return a + b

        manager = FakeTransactionManager()
        transact = Transact(FakeThreadPool(), manager)
        result = yield transact.run(function, 1, b=2)
        self.assertEqual(3, result)
        self.assertTrue(manager.committed)

    @inlineCallbacks
    def testRetries(self):
        """
        L{Transact.run} retries the transaction if a DB error occours during
        a transaction collision.
        """

        class FakeTransactionManager(object):

            def commit(self):
                self.committed = True

            def abort(self):
                self.aborted = True

        self.flag = False

        def function():
            if not self.flag:
                self.flag = True
                raise psycopg2.Error('Error')
            return 'success'

        manager = FakeTransactionManager()
        transact = Transact(FakeThreadPool(), manager, lambda seconds: None)
        result = yield transact.run(function)
        self.assertEqual('success', result)
        self.assertTrue(manager.aborted)
        self.assertTrue(manager.committed)

    @inlineCallbacks
    def testRetryWriteWarningInLog(self):
        """
        L{Transact.run} writes a warning in the logs if a retry is done.
        """

        class FakeTransactionManager(object):

            def commit(self):
                self.committed = True

            def abort(self):
                self.aborted = True

        self.flag = False

        def function():
            if not self.flag:
                self.flag = True
                raise psycopg2.Error('Error')
            return 'success'

        manager = FakeTransactionManager()
        transact = Transact(FakeThreadPool(), manager, lambda seconds: None)
        result = yield transact.run(function)
        self.assertEqual('success', result)
        self.assertTrue(manager.aborted)
        self.assertTrue(manager.committed)
        self.assertIn('Retrying a transaction', self.log.getvalue())

    @inlineCallbacks
    def testRetriesDisconnectionErrors(self):
        """
        L{Transact.run} retries the transaction if a L{DisconnectionError}
        occurs during a transaction.
        """

        class FakeTransactionManager(object):

            def commit(self):
                self.committed = True

            def abort(self):
                self.aborted = True

        self.flag = False

        def function():
            if not self.flag:
                self.flag = True
                raise DisconnectionError('Disconnected')
            return 'success'

        manager = FakeTransactionManager()
        transact = Transact(FakeThreadPool(), manager)
        result = yield transact.run(function)
        self.assertEqual('success', result)
        self.assertTrue(manager.aborted)
        self.assertTrue(manager.committed)

    @inlineCallbacks
    def testRunWithFunctionFailure(self):
        """
        If the given function raises an error, then L{Transact.run} aborts the
        transaction and re-raises the same error.
        """

        class FakeTransactionManager(object):

            def abort(self):
                self.aborted = True

        def function():
            raise RuntimeError('Function call exploded!')

        manager = FakeTransactionManager()
        transact = Transact(FakeThreadPool(), manager)
        yield self.assertFailure(transact.run(function), RuntimeError)
        self.assertTrue(manager.aborted)

    @inlineCallbacks
    def testRunWithCommitFailure(self):
        """
        If the specified function succeeds but the transaction fails to
        commit, then L{Transact.run} aborts the transaction and re-raises the
        commit exception.
        """

        class FakeTransactionManager(object):

            def abort(self):
                self.aborted = True

            def commit(self):
                raise RuntimeError('Commit exploded!')

        def function():
            pass

        manager = FakeTransactionManager()
        transact = Transact(FakeThreadPool(), manager)
        yield self.assertFailure(transact.run(function), RuntimeError)
        self.assertTrue(manager.aborted)

    @inlineCallbacks
    def testReturnStormObject(self):
        """
        A C{RuntimeError} is raised if a Storm object is returned from the
        transaction.  Storm objects may only be used in the thread they were
        created in, so this provides some safety checking to prevent strange
        behaviour.
        """

        class FakeTransactionManager(object):

            def abort(self):
                self.aborted = True

        class StormObject(object):

            __storm_table__ = 'storm_object'

        def function():
            return StormObject()

        manager = FakeTransactionManager()
        transact = Transact(FakeThreadPool(), manager)
        yield self.assertFailure(transact.run(function), RuntimeError)
        self.assertTrue(manager.aborted)

    def testWBDefaultTransactionManager(self):
        """
        By default L{Transact} uses the C{transaction} package as the default
        transaction manager.
        """
        transact = Transact(FakeThreadPool())
        self.assertIdentical(transaction, transact._transaction)
