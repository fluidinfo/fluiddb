"""Logic for running a session and tracking events that occur during it."""

from cStringIO import StringIO
from datetime import datetime, timedelta
import json
import logging

from storm.databases.postgres import PostgresTimeoutTracer
from storm.expr import Variable
from storm.tracer import install_tracer, remove_all_tracers
from twisted.web.http_headers import Headers


class Session(object):
    """A manifest that captures details about an API request."""

    plugins = None

    def __init__(self, id, plugins=None):
        self.id = id
        self.startDate = None
        self.stopDate = None
        self.duration = None
        self.running = False
        self._plugins = plugins or {}

    def __getattr__(self, name):
        """Get the plugin matching the specified name.

        @param name: The name of the plugin.
        @return: The plugin instance or C{None} if one isn't available.
        """
        if name not in self._plugins:
            raise AttributeError('No plugin called %s.' % name)
        return self._plugins[name]

    def start(self):
        """Start the session."""
        self.startDate = datetime.utcnow()
        for plugin in self._plugins.itervalues():
            plugin.start(self)
        self.running = True

    def stop(self):
        """Stop the session."""
        for plugin in self._plugins.itervalues():
            plugin.stop()
        self.running = False
        self.stopDate = datetime.utcnow()
        self.duration = self.stopDate - self.startDate

    def dumps(self):
        """Dump session data as a JSON object.

        @return: A JSON representation of this session.
        """

        def encodeObject(obj):
            """Encodes C{datetime} and C{timedelta} objects in JSON"""
            if isinstance(obj, datetime):
                return obj.strftime('datetime(%Y-%m-%d %H:%M:%S.%f)')
            if isinstance(obj, timedelta):
                microseconds = (obj.days * 86400000000 + obj.seconds * 1000000
                                + obj.microseconds)
                return 'timedelta(%s)' % microseconds
            return obj

        data = {'id': self.id,
                'startDate': self.startDate,
                'stopDate': self.stopDate,
                'duration': self.duration}

        for name, plugin in self._plugins.iteritems():
            data[name] = plugin.dumps()

        return json.dumps(data, default=encodeObject)

    def loads(self, data):
        """Load session data from a JSON object.

        @param data: A JSON representation of a session.
        """

        def decodeObject(dictionary):
            """Decodes C{datetime} and C{timedelta} objects in JSON"""
            for key, value in dictionary.items():
                if isinstance(value, (str, unicode)):
                    if value.startswith('datetime('):
                        dictionary[key] = datetime.strptime(
                            value[9:-1], '%Y-%m-%d %H:%M:%S.%f')
                    if value.startswith('timedelta('):
                        microseconds = int(value[10:-1])
                        dictionary[key] = timedelta(microseconds=microseconds)
            return dictionary

        data = json.loads(data, object_hook=decodeObject)
        self.id = data['id']
        self.startDate = data['startDate']
        self.stopDate = data['stopDate']
        self.duration = data['duration']
        for name, plugin in self._plugins.iteritems():
            plugin.loads(data[name])


class SessionStorage(object):
    """Writer appends L{Session}s to a log file."""

    def dump(self, session, path):
        """Write a L{Session} to a log file.

        @param session: A L{Session} instance to persist.
        @param path: The path to the log file.
        """
        with open(path, 'a') as stream:
            stream.write(session.dumps() + '\n')


class LoggingPlugin(object):
    """A L{Session} plugin for capturing logs.

    Log messages written using this plugin are captured and also written to
    the root logger.
    """

    messages = None

    def start(self, session):
        """Start the logger for this session.

        @param session: The L{Session} parent of this plugin.
        """
        self._messages = StringIO()
        handler = logging.StreamHandler(self._messages)
        formatter = logging.Formatter(
            '%(asctime)s %(levelname)8s  %(message)s')
        handler.setFormatter(formatter)
        self._logger = logging.Logger(session.id)
        self._logger.addHandler(handler)
        self._logger.propagate = False
        self._logger.setLevel(logging.DEBUG)

    def stop(self):
        """Stop the logger for this session."""
        self.messages = self._messages.getvalue()
        for handler in self._logger.handlers:
            handler.close()

    def info(self, message, *args, **kwargs):
        """Write an C{INFO} level log message.

        @param message: The message to write.
        @param args: Positional arguments to use when interpolating the
            message.
        @param kwargs: Keyword arguments to use when interpolating the message.
        """
        logging.info(message, *args, **kwargs)
        self._logger.info(message, *args, **kwargs)

    def error(self, message, *args, **kwargs):
        """Write an C{ERROR} level log message.

        @param message: The message to write.
        @param args: Positional arguments to use when interpolating the
            message.
        @param kwargs: Keyword arguments to use when interpolating the message.
        """
        logging.error(message, *args, **kwargs)
        self._logger.error(message, *args, **kwargs)

    def exception(self, exception, *args, **kwargs):
        """Write an C{ERROR} level log message for an exception.

        @param message: The message to write.
        @param args: Positional arguments to use when interpolating the
            message.
        @param kwargs: Keyword arguments to use when interpolating the message.
        """
        logging.debug(exception, *args, **kwargs)
        self._logger.exception(exception, *args, **kwargs)

    def dumps(self):
        """Write session data to a C{dict}.

        @return: A C{dict} with information about the HTTP request.
        """
        return {'messages': self.messages}

    def loads(self, data):
        """Load session data from a C{dict}.

        @param data: The C{dict} to load information from.
        """
        self.messages = data.get('messages')


class StatementTracer(PostgresTimeoutTracer):
    """A custom SQL statement tracer.

    Statements are written to a log, so that they can be used in post mortem
    analysis.  In addition, the total amount of time that may be consumed when
    running queries is limited.  A C{storm.exceptions.TimeoutError} is raised
    if the allocated time is exceeded.

    @param timeout: The maximum amount of time that may be spent executing
        database statements, in seconds.
    """

    def __init__(self, timeout):
        super(StatementTracer, self).__init__()
        self.statements = []
        self.timeout = timeout
        self._remainingTime = timedelta(seconds=timeout)

    def connection_raw_execute(self, connection, cursor, statement,
                               parameters):
        """Called when a statement is executed.

        @param connection: The L{Connection} to the database.
        @param cursor: A cursor object, specific to the backend being used.
        @param statement: The SQL statement to execute.
        @param parameters: The parameters to use with C{statement}.
        """
        rawParameters = []
        for parameter in parameters:
            if isinstance(parameter, Variable):
                rawParameters.append(unicode(parameter.get()))
            else:
                rawParameters.append(unicode(parameter))
        self.statements.append({'statement': statement.decode('utf-8'),
                                'parameters': rawParameters,
                                'startDate': datetime.utcnow()})
        super(StatementTracer, self).connection_raw_execute(
            connection, cursor, statement, parameters)

    def connection_raw_execute_error(self, connection, cursor, statement,
                                     parameters, error):
        """Called when an executed statement fails.

        @param connection: The L{Connection} to the database.
        @param cursor: A cursor object, specific to the backend being used.
        @param statement: The SQL statement to execute.
        @param parameters: The parameters to use with C{statement}.
        @param error: The exception that was raised to signal the error.
        """
        trace = self.statements[-1]
        trace['stopDate'] = datetime.utcnow()
        trace['error'] = str(error).decode('utf-8')
        trace['duration'] = trace['stopDate'] - trace['startDate']
        self._remainingTime = self._remainingTime - trace['duration']
        super(StatementTracer, self).connection_raw_execute_error(
            connection, cursor, statement, parameters, error)

    def connection_raw_execute_success(self, connection, cursor,
                                       statement, parameters):
        """Called when an executed statement succeeds.

        @param connection: The L{Connection} to the database.
        @param cursor: A cursor object, specific to the backend being used.
        @param statement: The SQL statement to execute.
        @param parameters: The parameters to use with C{statement}.
        """
        trace = self.statements[-1]
        trace['stopDate'] = datetime.utcnow()
        trace['duration'] = trace['stopDate'] - trace['startDate']

    def get_remaining_time(self):
        """
        Get the amount of time the current session has left to execute
        statements.

        @return: Number of seconds allowed for the next statement.
        """
        return self._remainingTime.seconds


class TransactPlugin(object):
    """A L{Session} plugin for capturing database statements.

    @ivar statements: A C{list} of C{dict}s matching the following format::

        {'statement': <statement>,
         'parameters': <parameters>,
         'startDate': <start-time>,
         'stoptime': <stop-time>,
         'duration': <duration>}

    @ivar duration: The total time spent in the transaction thread.
    @ivar statementDuration: The total time spent running database statements.
    @param transact: The L{Transact} instance to use when running
        transactions.
    """

    def __init__(self, transact, timeout):
        self._transact = transact
        self.timeout = timeout
        self.transactions = []
        self.totalStatementDuration = timedelta()

    def start(self, session):
        """Start the transaction manager for this session.

        @param session: The L{Session} parent of this plugin.
        """
        pass

    def stop(self):
        """Stop the transaction manager."""
        for transaction in self.transactions:
            transaction['duration'] = (transaction['stopDate']
                                       - transaction['startDate'])
            transaction['statementDuration'] = timedelta()
            for statement in transaction['statements']:
                try:
                    transaction['statementDuration'] += statement['duration']
                except KeyError:
                    logging.error(
                        'Session statement %r has no duration key. '
                        'The full list of statements for this session is %r.'
                        % (statement, transaction['statements']))
            self.totalStatementDuration += transaction['statementDuration']

    def run(self, function, *args, **kwargs):
        """Run C{function} in a transaction and log all statements."""
        transaction = {'statements': [], 'startDate': datetime.utcnow()}

        def runTransaction(function, *args, **kwargs):
            tracer = StatementTracer(self.timeout)
            install_tracer(tracer)
            try:
                return function(*args, **kwargs)
            finally:
                transaction['statements'] = tracer.statements
                remove_all_tracers()

        def endTransaction(value):
            transaction['stopDate'] = datetime.utcnow()
            self.transactions.append(transaction)
            return value

        deferred = self._transact.run(runTransaction, function,
                                      *args, **kwargs)
        return deferred.addBoth(endTransaction)

    def dumps(self):
        """Write session data to a C{dict}.

        @return: A C{dict} with information about the HTTP request.
        """
        return {'totalStatementDuration': self.totalStatementDuration,
                'transactions': self.transactions}

    def loads(self, data):
        """Load session data from a C{dict}.

        @param data: The C{dict} to load information from.
        """
        self.__dict__.update(data)


class HTTPPlugin(object):
    """A L{Session} plugin for capturing information about HTTP requests."""

    _request = None
    uri = None
    path = None
    method = None
    requestHeaders = None
    responseHeaders = None
    code = None

    def start(self, session):
        """Start the HTTP tracer for this session.

        @param session: The L{Session} parent of this plugin.
        """
        pass

    def stop(self):
        """Stop the HTTP tracer."""
        if self._request is not None:
            self.uri = self._request.uri
            self.path = self._request.path
            self.method = self._request.method
            self.requestHeaders = self._request.requestHeaders
            self.responseHeaders = self._request.responseHeaders
            self.code = self._request.code

    def trace(self, request):
        """Trace an HTTP request.

        @param request: The C{twisted.web.http.Request} instance to trace.
        """
        self._request = request

    def dumps(self):
        """Write session data to a C{dict}.

        @return: A C{dict} with information about the HTTP request.
        """
        requestHeaders = None
        if self.requestHeaders is not None:
            requestHeaders = dict(self.requestHeaders.getAllRawHeaders())
            if 'Authorization' in requestHeaders:
                requestHeaders['Authorization'] = ['<sanitized>']
        responseHeaders = None
        if self.responseHeaders is not None:
            responseHeaders = dict(self.responseHeaders.getAllRawHeaders())
        return {'uri': self.uri,
                'path': self.path,
                'method': self.method,
                'requestHeaders': requestHeaders,
                'responseHeaders': responseHeaders,
                'code': self.code}

    def loads(self, data):
        """Load session data from a C{dict}.

        @param data: The C{dict} to load information from.
        """
        self.uri = data['uri']
        self.path = data['path']
        self.method = data['method']
        self.requestHeaders = Headers(data['requestHeaders'])
        self.responseHeaders = Headers(data['responseHeaders'])
        self.code = data['code']


class Timer(object):
    """Context manager times the code that runs in its scope.

    @param name: The name of the timer.
    @param events: The dictionary used to track events.
    """

    def __init__(self, name, events):
        self.name = name
        self.events = events

    def __enter__(self):
        """Start the timer."""
        self.startDate = datetime.utcnow()

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop the timer."""
        stopDate = datetime.utcnow()
        self.events[self.name].append(
            {'startDate': self.startDate,
             'stopDate': stopDate,
             'duration': stopDate - self.startDate})


class TimerPlugin(object):
    """
    A L{Session} plugin for capturing timing information about events that
    occur while handling an HTTP request.
    """

    def __init__(self):
        self.events = {}

    def start(self, session):
        """Start the timing tracer for this session.

        @param session: The L{Session} parent of this plugin.
        """
        pass

    def stop(self):
        """Stop the timing tracer."""
        pass

    def track(self, name):
        """Track the amount of time spent during an event.

        @param name: The name of the event.
        @return: A context manager that tracks the duration of the code that
            runs in its scope.
        """
        if name not in self.events:
            self.events[name] = []
        return Timer(name, self.events)

    def dumps(self):
        """Write session data to a C{dict}.

        @return: A C{dict} with information about the HTTP request.
        """
        return self.events

    def loads(self, data):
        """Load session data from a C{dict}.

        @param data: The C{dict} to load information from.
        """
        self.events.update(data)
