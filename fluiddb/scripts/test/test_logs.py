from datetime import datetime, timedelta
import os

from twisted.python.util import sibpath

from fluiddb.scripts.logs import (
    LogParser, TraceLogParser, ErrorLine, StatusLine, TraceLog, loadLogs,
    loadTraceLogs)
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    LogsDatabaseResource, TemporaryDirectoryResource)


class LogParserTest(FluidinfoTestCase):

    resources = [('fs', TemporaryDirectoryResource())]

    def setUp(self):
        super(LogParserTest, self).setUp()
        self.parser = LogParser()

    def testParseWithEmptyFile(self):
        """
        Passing an empty file to L{LogParser.parse} is essentially a no-op.
        """
        path = self.fs.makePath('')
        self.assertEqual([], list(self.parser.parse(path)))

    def testParseWithStatus(self):
        """
        L{LogParser.parse} parses status lines from the log and yields
        L{StatusLine} instances for each one.
        """
        path = sibpath(__file__, 'status-line.log')
        [status] = list(self.parser.parse(path))
        self.assertEqual(datetime(2011, 6, 14, 6, 36, 47, 68), status.time)
        self.assertEqual('POST', status.method)
        self.assertEqual('/objects', status.endpoint)
        self.assertEqual(201, status.code)
        self.assertEqual(131, status.contentLength)
        self.assertEqual('fom/0.9.2', status.agent)

    def testParseWithUnexpectedContent(self):
        """L{LogParser.parse} skips lines in the log that it can't parse."""
        path = sibpath(__file__, 'unknown-line.log')
        self.assertEqual([], list(self.parser.parse(path)))

    def testParseWithError(self):
        """
        L{LogParser.parse} parses error lines from the log and yields
        L{ErrorLine} instances for each one.
        """
        path = sibpath(__file__, 'error-line.log')
        [error] = list(self.parser.parse(path))
        self.assertEqual(datetime(2011, 6, 14, 10, 33, 33, 312), error.time)
        self.assertEqual("Unknown path u'fluidinfo/chrome-ext.xml'.",
                         error.message)
        self.assertIdentical(None, error.exceptionClass)
        self.assertIdentical(None, error.traceback)

    def testParseWithTraceback(self):
        """
        L{LogParser.parse} extracts full tracebacks from the logs when they're
        encountered with error lines.
        """
        path = sibpath(__file__, 'error-traceback.log')
        [error] = list(self.parser.parse(path))
        self.assertEqual(datetime(2011, 6, 14, 10, 33, 33, 312), error.time)
        self.assertEqual("Unknown path u'fluidinfo/chrome-ext.xml'.",
                         error.message)
        self.assertEqual('UnknownPathError', error.exceptionClass)
        with open(path, 'r') as stream:
            traceback = stream.read()
            traceback = '\n'.join(traceback.split('\n')[1:])
        self.assertEqual(traceback.strip(), error.traceback.strip())

    def testParseWithMixedLines(self):
        """L{LogParser.parse} correctly parses and skips lines in a log."""
        path = sibpath(__file__, 'mixed-lines.log')
        [error, status] = list(self.parser.parse(path))
        self.assertEqual(datetime(2011, 6, 14, 10, 33, 33, 312), error.time)
        self.assertEqual("Unknown path u'fluidinfo/chrome-ext.xml'.",
                         error.message)
        with open(path, 'r') as stream:
            traceback = stream.read()
            traceback = '\n'.join(traceback.split('\n')[2:-3])
        self.assertEqual(traceback.strip(), error.traceback.strip())

        self.assertEqual(datetime(2011, 6, 14, 11, 36, 47, 68), status.time)
        self.assertEqual(201, status.code)
        self.assertEqual('POST', status.method)
        self.assertEqual('/objects', status.endpoint)
        self.assertEqual('fom/0.9.2', status.agent)
        self.assertEqual(131, status.contentLength)


class LoadLogsTest(FluidinfoTestCase):

    resources = [('fs', TemporaryDirectoryResource()),
                 ('store', LogsDatabaseResource())]

    def testLoadWithEmptyFile(self):
        """Calling L{loadLogs} with an empty file is essentially a no-op."""
        path = self.fs.makePath('')
        loadLogs(path, self.store)
        self.assertTrue(self.store.find(ErrorLine).is_empty())
        self.assertTrue(self.store.find(StatusLine).is_empty())

    def testLoadWithStatus(self):
        """
        L{loadLogs} stores L{StatusLine} instances loaded from the log file in
        the database.
        """
        path = sibpath(__file__, 'status-line.log')
        loadLogs(path, self.store)
        status = self.store.find(StatusLine).one()
        self.assertEqual(datetime(2011, 6, 14, 6, 36, 47, 68), status.time)
        self.assertEqual(201, status.code)
        self.assertEqual('POST', status.method)
        self.assertEqual('/objects', status.endpoint)
        self.assertEqual('fom/0.9.2', status.agent)
        self.assertEqual(131, status.contentLength)

    def testLoadWithUnexpectedContent(self):
        """L{loadLogs} skips lines in the log that can't be parsed."""
        path = sibpath(__file__, 'unknown-line.log')
        loadLogs(path, self.store)
        self.assertTrue(self.store.find(ErrorLine).is_empty())
        self.assertTrue(self.store.find(StatusLine).is_empty())

    def testLoadWithError(self):
        """
        L{loadLogs} stores L{ErrorLine}s instances loaded from the log file in
        the database.
        """
        path = sibpath(__file__, 'error-line.log')
        loadLogs(path, self.store)
        error = self.store.find(ErrorLine).one()
        self.assertEqual(datetime(2011, 6, 14, 10, 33, 33, 312), error.time)
        self.assertEqual("Unknown path u'fluidinfo/chrome-ext.xml'.",
                         error.message)
        self.assertIdentical(None, error.exceptionClass)
        self.assertIdentical(None, error.traceback)

    def testLoadWithTraceback(self):
        """
        L{loadLogs} stores the tracebacks loaded with errors in the database.
        """
        path = sibpath(__file__, 'error-traceback.log')
        loadLogs(path, self.store)
        error = self.store.find(ErrorLine).one()
        self.assertEqual(datetime(2011, 6, 14, 10, 33, 33, 312), error.time)
        self.assertEqual("Unknown path u'fluidinfo/chrome-ext.xml'.",
                         error.message)
        self.assertEqual('UnknownPathError', error.exceptionClass)
        with open(path, 'r') as stream:
            traceback = stream.read()
            traceback = '\n'.join(traceback.split('\n')[1:])
        self.assertEqual(traceback.strip(), error.traceback.strip())

    def testLoadWithMixedLines(self):
        """L{loadLogs} correctly parses and skips lines in a log."""
        path = sibpath(__file__, 'mixed-lines.log')
        loadLogs(path, self.store)
        error = self.store.find(ErrorLine).one()
        self.assertEqual(datetime(2011, 6, 14, 10, 33, 33, 312), error.time)
        self.assertEqual("Unknown path u'fluidinfo/chrome-ext.xml'.",
                         error.message)
        with open(path, 'r') as stream:
            traceback = stream.read()
            traceback = '\n'.join(traceback.split('\n')[2:-3])
        self.assertEqual(traceback.strip(), error.traceback.strip())

        status = self.store.find(StatusLine).one()
        self.assertEqual(datetime(2011, 6, 14, 11, 36, 47, 68), status.time)
        self.assertEqual(201, status.code)
        self.assertEqual('POST', status.method)
        self.assertEqual('/objects', status.endpoint)
        self.assertEqual('fom/0.9.2', status.agent)
        self.assertEqual(131, status.contentLength)


class TraceLogParserTest(FluidinfoTestCase):

    resources = [('fs', TemporaryDirectoryResource())]

    def setUp(self):
        super(TraceLogParserTest, self).setUp()
        self.parser = TraceLogParser()

    def testParse(self):
        """
        L{TraceLogParser.parse} gets the root endpoint and stores it.  A query
        string, when present, is automatically removed.
        """
        path = sibpath(__file__, 'simple-trace-logs')
        filename = os.path.join(path, 'API-9000-20110630-165151-000901')
        [trace] = list(self.parser.parse(filename))
        self.assertEqual('API-9000-20110630-165151-000901',
                         trace.sessionID)
        self.assertTrue(isinstance(trace.duration, timedelta))
        self.assertEqual('/objects', trace.endpoint)

    def testParseWithURIAndQueryString(self):
        """
        L{TraceLogParser.parse} gets the root endpoint and stores it.  A query
        string, when present, is automatically removed.
        """
        path = sibpath(__file__, 'query-string-trace-logs')
        filename = os.path.join(path, 'API-9000-20110630-165209-001507')
        [trace] = list(self.parser.parse(filename))
        self.assertEqual('API-9000-20110630-165209-001507',
                         trace.sessionID)
        self.assertTrue(isinstance(trace.duration, timedelta))
        self.assertEqual('/values', trace.endpoint)


class LoadTraceLogsTest(FluidinfoTestCase):

    resources = [('fs', TemporaryDirectoryResource()),
                 ('store', LogsDatabaseResource())]

    def setUp(self):
        super(LoadTraceLogsTest, self).setUp()
        self.parser = TraceLogParser()

    def testLoadWithFiles(self):
        """L{loadTraceLogs} loads trace logs from the specified path."""
        path = sibpath(__file__, 'simple-trace-logs')
        filename = os.path.join(path, 'API-9000-20110630-165151-000901')
        loadTraceLogs(filename, self.store)
        trace = self.store.find(TraceLog).one()
        self.assertEqual('API-9000-20110630-165151-000901', trace.sessionID)
        self.assertTrue(isinstance(trace.duration, timedelta))
        self.assertEqual('/objects', trace.endpoint)
