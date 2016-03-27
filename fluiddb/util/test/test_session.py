from datetime import datetime, timedelta

from psycopg2 import ProgrammingError
from twisted.internet.defer import inlineCallbacks
from twisted.web.http import FORBIDDEN
from twisted.web.http_headers import Headers

from fluiddb.data.store import getMainStore
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.doubles import FakeRequest
from fluiddb.testing.resources import (
    DatabaseResource, LoggingResource, TemporaryDirectoryResource,
    ThreadPoolResource)
from fluiddb.util.session import (
    Session, SessionStorage, HTTPPlugin, LoggingPlugin, TimerPlugin,
    TransactPlugin)
from fluiddb.util.transact import Transact


class SampleSession(Session):

    def __init__(self, id, transact):
        plugins = {'http': HTTPPlugin(),
                   'log': LoggingPlugin(),
                   'timer': TimerPlugin(),
                   'transact': TransactPlugin(transact, 60)}
        super(SampleSession, self).__init__(id, plugins)


class SessionTest(FluidinfoTestCase):

    def testInstantiate(self):
        """A L{Session} only has an ID to start with."""
        session = Session('id')
        self.assertEqual('id', session.id)
        self.assertIdentical(None, session.startDate)
        self.assertIdentical(None, session.stopDate)
        self.assertFalse(session.running)

    def testStartAndStop(self):
        """
        L{Session.start} begins the session and stores the start time and
        L{Session.stop} ends the session and stores the end time.
        """
        session = Session('id')
        session.start()
        try:
            self.assertTrue(isinstance(session.startDate, datetime))
        finally:
            session.stop()

        self.assertTrue(isinstance(session.stopDate, datetime))
        self.assertEqual(session.stopDate - session.startDate,
                         session.duration)

    def testDumpsAndLoads(self):
        """A L{Session} can be dumped to and loaded from JSON."""
        session = Session('id')
        session.start()
        session.stop()

        data = session.dumps()
        loadedSession = Session('another-id')
        loadedSession.loads(data)
        self.assertEqual(session.id, loadedSession.id)
        self.assertEqual(session.startDate, loadedSession.startDate)
        self.assertEqual(session.stopDate, loadedSession.stopDate)
        self.assertEqual(session.duration, loadedSession.duration)


class SessionStorageTest(FluidinfoTestCase):

    resources = [('fs', TemporaryDirectoryResource())]

    def testDump(self):
        """
        L{SessionStorage.dump} appends JSON representations of L{Session}
        instances to a log file.
        """
        path = self.fs.makePath()
        session = Session('id')
        session.start()
        session.stop()

        storage = SessionStorage()
        storage.dump(session, path)
        with open(path, 'r') as stream:
            data = stream.read()
            self.assertEqual(data, session.dumps() + '\n')


class LoggingPluginTest(FluidinfoTestCase):

    resources = [('log', LoggingResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(LoggingPluginTest, self).setUp()
        self.transact = Transact(self.threadPool)

    def testInfo(self):
        """L{Session.info} logs a message using the C{INFO} log level."""
        session = SampleSession('id', self.transact)
        session.start()
        try:
            session.log.info('Hello, world!')
        finally:
            session.stop()

        self.assertIn('INFO', session.log.messages)
        self.assertIn('Hello, world!', session.log.messages)

    def testError(self):
        """L{Session.error} logs a message using the C{ERROR} log level."""
        session = SampleSession('id', self.transact)
        session.start()
        try:
            session.log.error('Something bad happened.')
        finally:
            session.stop()

        self.assertIn('ERROR', session.log.messages)
        self.assertIn('Something bad happened.', session.log.messages)

    def testException(self):
        """
        L{Session.exception} logs an exception using the C{ERROR} log level.
        """
        session = SampleSession('id', self.transact)
        session.start()
        try:
            error = RuntimeError('Something bad happened.')
            session.log.exception(error)
        finally:
            session.stop()

        self.assertIn('ERROR', session.log.messages)
        self.assertIn('Something bad happened.', session.log.messages)

    def testDumpsAndLoads(self):
        """
        Data stored by a L{LoggingPlugin} can be dumped to and loaded from
        JSON.
        """
        session = SampleSession('id', self.transact)
        session.start()
        try:
            session.log.info('Hello, world!')
        finally:
            session.stop()

        data = session.dumps()
        loadedSession = SampleSession('another-id', self.transact)
        loadedSession.loads(data)
        self.assertEqual(session.log.messages, loadedSession.log.messages)


class TransactPluginTest(FluidinfoTestCase):

    resources = [('log', LoggingResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(TransactPluginTest, self).setUp()
        self.transact = Transact(self.threadPool, sleep=lambda seconds: None)

    @inlineCallbacks
    def testRunWithEmptyTransaction(self):
        """Nothing is logged if no statements are run."""
        session = SampleSession('id', self.transact)
        session.start()
        try:
            yield session.transact.run(lambda: None)
        finally:
            session.stop()

        transaction = session.transact.transactions[0]

        self.assertEqual([], transaction['statements'])
        self.assertTrue(isinstance(transaction['duration'],
                                   timedelta))
        self.assertTrue(isinstance(transaction['statementDuration'],
                                   timedelta))

    @inlineCallbacks
    def testRun(self):
        """Statements run in a transaction are captured."""

        def run():
            store = getMainStore()
            store.execute('SELECT 1 FROM patch WHERE 1=2')

        session = SampleSession('id', self.transact)
        session.start()
        try:
            yield session.transact.run(run)
        finally:
            session.stop()

        [transaction] = session.transact.transactions
        [trace] = transaction['statements']
        self.assertEqual('SELECT 1 FROM patch WHERE 1=2', trace['statement'])
        self.assertEqual([], trace['parameters'])
        self.assertIn('startDate', trace)
        self.assertIn('stopDate', trace)
        self.assertIn('duration', trace)

    @inlineCallbacks
    def testRunTwoTransactions(self):
        """Statements run in two or more transactions are captured."""

        def run():
            store = getMainStore()
            store.execute('SELECT 1 FROM patch WHERE 1=2')

        def run2():
            store = getMainStore()
            store.execute('SELECT 2 FROM patch WHERE 1=2')

        session = SampleSession('id', self.transact)
        session.start()
        try:
            yield session.transact.run(run)
            yield session.transact.run(run2)
        finally:
            session.stop()

        [transaction1, transaction2] = session.transact.transactions
        [trace] = transaction1['statements']
        self.assertEqual('SELECT 1 FROM patch WHERE 1=2', trace['statement'])
        self.assertEqual([], trace['parameters'])
        self.assertIn('startDate', trace)
        self.assertIn('stopDate', trace)
        self.assertIn('duration', trace)
        [trace] = transaction2['statements']
        self.assertEqual('SELECT 2 FROM patch WHERE 1=2', trace['statement'])
        self.assertEqual([], trace['parameters'])
        self.assertIn('startDate', trace)
        self.assertIn('stopDate', trace)
        self.assertIn('duration', trace)

    @inlineCallbacks
    def testDumpsAndLoads(self):
        """
        Data stored by the L{TransactPlugin} can be dumped to and loaded from
        JSON.
        """

        def run():
            store = getMainStore()
            store.execute('SELECT 1 FROM patch WHERE 1=2')

        session = SampleSession('id', self.transact)
        session.start()
        try:
            yield session.transact.run(run)
        finally:
            session.stop()

        data = session.dumps()
        loadedSession = SampleSession('another-id', self.transact)
        loadedSession.loads(data)
        self.assertEqual(session.transact.transactions,
                         loadedSession.transact.transactions)
        self.assertEqual(session.transact.totalStatementDuration,
                         loadedSession.transact.totalStatementDuration)

    def testDumpsWithError(self):
        """
        L{TransactPlugin} converts exceptions, such as C{QueryCanceledError}
        that's raised when a statement timeout occurs, to strings when
        generating data that will be serialized to JSON.
        """

        def run():
            store = getMainStore()
            store.execute(u'SELECT * FROM \N{HIRAGANA LETTER A}')

        session = SampleSession('id', self.transact)
        session.transact.timeout = -1
        session.start()

        def check(error):
            session.stop()
            data = session.dumps()
            loadedSession = SampleSession('another-id', self.transact)
            loadedSession.loads(data)
            self.assertEqual(session.transact.transactions,
                             loadedSession.transact.transactions)
            self.assertEqual(session.transact.totalStatementDuration,
                             loadedSession.transact.totalStatementDuration)

        deferred = self.assertFailure(session.transact.run(run),
                                      ProgrammingError)
        return deferred.addCallback(check)

    def testStatementWithNoDurationLogsWarning(self):
        """
        Calling stop on a C{TransactPlugin} that has a statement
        with no 'duration' key should log an error.

        NOTE: This test exists because we currently have a bug elsewhere
        that creates a session statement with no 'duration' key.
        """
        session = SampleSession('id', self.transact)
        session.start()
        transaction = {
            'startDate': datetime.utcnow(),
            'stopDate': datetime.utcnow(),
            'statements': [{}]
        }
        session._plugins['transact'].transactions.append(transaction)
        session.stop()
        logMessages = self.log.getvalue()
        self.assertIn('ERROR', logMessages)
        self.assertIn('Session statement {} has no duration key', logMessages)


class HTTPPluginTest(FluidinfoTestCase):

    resources = [('log', LoggingResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(HTTPPluginTest, self).setUp()
        self.transact = Transact(self.threadPool)

    def testTrace(self):
        """
        L{HTTPPlugin.trace} extracts and stores information from a request
        instance.
        """
        headers = Headers({'x-hello': ['goodbye']})
        request = FakeRequest(uri='/objects', method='PUT',
                              path='/objects?foo=bar', headers=headers)
        session = SampleSession('id', self.transact)
        session.start()
        try:
            session.http.trace(request)
            request.setHeader('foo', 'bar')
            request.setResponseCode(FORBIDDEN)
        finally:
            session.stop()

        self.assertEqual('/objects', session.http.uri)
        self.assertEqual('/objects?foo=bar', session.http.path)
        self.assertEqual('PUT', session.http.method)
        self.assertEqual(headers, session.http.requestHeaders)
        self.assertEqual({'Foo': ['bar']},
                         dict(session.http.responseHeaders.getAllRawHeaders()))
        self.assertEqual(FORBIDDEN, session.http.code)

    def testSanitizeAuthorizationHeader(self):
        """
        The contents of the C{Authorization} header, when it's present, are
        sanitized to avoid leaking password data.
        """
        headers = Headers({'authorization': ['Basic 123456abcdef']})
        request = FakeRequest(uri='/objects', method='PUT',
                              path='/objects?foo=bar', headers=headers)
        session = SampleSession('id', self.transact)
        session.start()
        try:
            session.http.trace(request)
        finally:
            session.stop()

        data = session.dumps()
        loadedSession = SampleSession('another-id', self.transact)
        loadedSession.loads(data)
        self.assertEqual(Headers({'Authorization': ['<sanitized>']}),
                         loadedSession.http.requestHeaders)

    def testDumpsAndLoads(self):
        """
        Data stored by an L{HTTPPlugin} can be dumped to and loaded from JSON.
        """
        headers = Headers({'x-foo': ['bar']})
        request = FakeRequest(uri='/objects', method='PUT',
                              path='/objects?foo=bar', headers=headers)
        session = SampleSession('id', self.transact)
        session.start()
        try:
            session.http.trace(request)
            request.setHeader('foo', 'bar')
            request.setResponseCode(FORBIDDEN)
        finally:
            session.stop()

        data = session.dumps()
        loadedSession = SampleSession('another-id', self.transact)
        loadedSession.loads(data)
        self.assertEqual(loadedSession.http.uri, session.http.uri)
        self.assertEqual(loadedSession.http.path, session.http.path)
        self.assertEqual(loadedSession.http.method, session.http.method)
        self.assertEqual(loadedSession.http.requestHeaders,
                         session.http.requestHeaders)
        self.assertEqual(loadedSession.http.responseHeaders,
                         session.http.responseHeaders)
        self.assertEqual(loadedSession.http.code, session.http.code)


class TimerPluginTest(FluidinfoTestCase):

    resources = [('log', LoggingResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(TimerPluginTest, self).setUp()
        self.transact = Transact(self.threadPool)

    def testTrack(self):
        """
        L{TimerPlugin.track} returns a context manager that records the amount
        of time a block of code takes to run.
        """
        session = SampleSession('id', self.transact)
        session.start()
        try:
            with session.timer.track('test'):
                pass
        finally:
            session.stop()

        self.assertIn('test', session.timer.events)
        [info] = session.timer.events['test']
        self.assertEqual(3, len(info))
        self.assertTrue(isinstance(info['startDate'], datetime))
        self.assertTrue(isinstance(info['stopDate'], datetime))
        self.assertTrue(isinstance(info['duration'], timedelta))

    def testDumpsAndLoads(self):
        """
        Data stored by a L{TimerPlugin} can be dumped to and loaded from JSON.
        """
        session = SampleSession('id', self.transact)
        session.start()
        try:
            with session.timer.track('test'):
                pass
        finally:
            session.stop()

        data = session.dumps()
        loadedSession = SampleSession('another-id', self.transact)
        loadedSession.loads(data)
        self.assertEqual(session.timer.events, loadedSession.timer.events)
