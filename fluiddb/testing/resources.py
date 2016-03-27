from cStringIO import StringIO
from httplib2 import Http
import logging
import os
import shutil
import sys
import tempfile
from urlparse import urljoin

from redis import ConnectionPool, Redis
from storm.zope.testing import ZStormResourceManager
from testresources import TestResource
import transaction
from twisted.python.threadpool import ThreadPool
from txsolr import SolrClient

from fluiddb.application import (
    getConfig, setCacheConnectionPool, setConfig, setupLogging)
from fluiddb.schema import logs, main


class MainDatabaseResource(ZStormResourceManager):
    """
    Test resource sets up default URIs and schemas for the main database and
    provides a ready to use C{Store} instance.
    """

    def __init__(self):
        uri = 'postgres://fluidinfo:fluidinfo@localhost/fluidinfo-unit-test'
        uri = os.environ.get('FLUIDDB_DB', uri)
        databases = [{'name': 'main',
                      'uri': uri,
                      'schema': main.createSchema()}]
        super(MainDatabaseResource, self).__init__(databases)

    def make(self, dependency_resources):
        """Return the main C{Store} for easy access in tests."""
        zstorm = super(MainDatabaseResource, self).make(dependency_resources)
        return zstorm.get('main')

    # FIXME We're overriding the base clean() method to workaround an issue.
    # This method should go away entirely. -jkakar
    def clean(self, resource):
        """Clean up the stores after a test."""
        try:
            for name, store in self._zstorm.iterstores():
                # Ensure that the store is in a consistent state
                store.flush()
                # Clear the alive cache *before* abort is called,
                # to prevent a useless loop in Store.invalidate
                # over the alive objects

                # FIXME I had to comment out this line to prevent our test
                # suite from being 4x slower! -jkakar
                # store._alive.clear()
        finally:
            transaction.abort()

        # Clean up tables after each test if a commit was made
        needs_commit = False
        for name, store in self._zstorm.iterstores():
            if self.force_delete or store in self._commits:
                schema_store = self._schema_zstorm.get(name)
                schema = self._schemas[name]
                schema.delete(schema_store)
                needs_commit = True
        if needs_commit:
            transaction.commit()
        self._commits = {}


_databaseResource = None


def DatabaseResource():
    """A shared L{MainDatabaseResource}.

    The L{MainDatabaseResource} manages a pool of database connections, which
    avoids unnecessary reconnections, but we only benefit from this pooling if
    we share the same pool across as many test suites as possible.  In fact,
    without sharing the pool of connections PostgreSQL produces 'Non-superuser
    connection limit exceeded' messages during the final tests in the test
    suite.

    @return: The global L{MainDatabaseResource} instance.
    """
    global _databaseResource
    if _databaseResource is None:
        _databaseResource = MainDatabaseResource()
    return _databaseResource


class LogsDatabaseResource(ZStormResourceManager):
    """
    Test resource sets up default URIs and schemas for the logs database and
    provides a ready to use C{Store} instance.
    """

    def __init__(self):
        # FIXME I'm not sure why 'sqlite:' (for an in-memory database) doesn't
        # work here.  It's also a bit bad that we're leaving a file lying
        # around in /tmp.
        databases = [{'name': 'logs',
                      'uri': 'sqlite:////tmp/fluidinfo-unit-test.db',
                      'schema': logs.createSchema()}]
        super(LogsDatabaseResource, self).__init__(databases)

    def make(self, dependency_resources):
        """Return the main C{Store} for easy access in tests."""
        zstorm = super(LogsDatabaseResource, self).make(dependency_resources)
        return zstorm.get('logs')


class IndexResource(TestResource):
    """
    Test resource resets Solr and provides a ready-to-use C{SolrClient}
    instance.
    """

    def make(self, dependency_resources):
        """Reset the Solr index and prepare a C{SolrClient}.

        The Solr index is cleared before a test runs, instead of after it
        finishes, to:

         * Guarantee the index is empty when the test runs.
         * Leave the index untouched after the test completes so that it can
           be investigated during debugging activities.
        """
        url = 'http://localhost:8080/solr/'
        self._resetIndex(url)
        return SolrClient(url)

    def _resetIndex(self, baseURL):
        """Reset the Solr index."""
        url = urljoin(baseURL, '/solr/update?wt=json')
        headers = {'User-Agent': 'FluidDB test suite',
                   'Content-Type': 'text/xml'}
        body = '<delete><query>*:*</query></delete>'
        response, content = Http().request(url, 'POST', body, headers)
        if response.status != 200:
            raise RuntimeError(
                "Couldn't clear Solr index!  Got HTTP %s return code and "
                'content: %s', (response.status, content))

        url = urljoin(baseURL, '/solr/update?wt=json')
        headers = {'User-Agent': 'FluidDB test suite',
                   'Content-Type': 'text/xml'}
        body = '<commit></commit>'
        response, content = Http().request(url, 'POST', body, headers)
        if response.status != 200:
            raise RuntimeError(
                "Couldn't commit Solr index!  Got HTTP %s return code and "
                'content: %s', (response.status, content))


class TemporaryDirectory(object):
    """A temporary directory resource.

    @ivar path: The directory in which all temporary directories and files
        will be created.
    """

    def setUp(self):
        """Initialize this resource."""
        self._counter = 1
        self.path = tempfile.mkdtemp()

    def tearDown(self):
        """Clean up temporary directories created by this resource."""
        shutil.rmtree(self.path)

    def makeDir(self):
        """Create a temporary directory.

        @return: The path to the new directory.
        """
        path = self.makePath()
        os.mkdir(path)
        return path

    def makePath(self, content=None, path=None):
        """Create a new C{path} name.

        @param content: Optionally, content to write to the new file.  If no
            content is provided a file will not be created, only a path will
            be generated.
        @param path: Optionally, the directory to use as the root for the new
            path.
        @return: The C{path} provided or a new one if it was C{None}.
        """
        if path is None:
            self._counter += 1
            path = '%s/%03d' % (self.path, self._counter)
        if content is not None:
            file = open(path, 'w')
            try:
                file.write(content)
            finally:
                file.close()
        return path


class TemporaryDirectoryResource(TestResource):
    """Resource provides and destroys temporary directories."""

    def make(self, dependency_resources):
        """Create a temporary directory."""
        directory = TemporaryDirectory()
        directory.setUp()
        return directory

    def clean(self, directory):
        """Destroy a temporary directory."""
        directory.tearDown()


class PythonPackageBuilder(object):
    """A builder for dynamically creating Python packages."""

    def __init__(self):
        self._directory = TemporaryDirectory()
        self._packages = []

    def setUp(self):
        """Initialize this resource."""
        self._directory.setUp()

    def tearDown(self):
        """Clean up Python package created by this resource."""
        for package in self._packages:
            sys.path.remove(os.path.dirname(package.path))
            for name in sorted(sys.modules):
                if name == package.name or name.startswith(package.name + '.'):
                    del sys.modules[name]
        self._directory.tearDown()

    def createPackage(self, name):
        """Create a new Python package.

        @param name: The name of the package.
        @return: A L{PythonModuleBuilder} that can be used to dynamically
            create modules in the new Python package.
        """
        basePath = self._directory.makeDir()
        packagePath = os.path.join(basePath, name)
        os.mkdir(packagePath)
        with open(os.path.join(packagePath, '__init__.py'), 'w'):
            pass
        sys.path.append(basePath)
        package = PythonModuleBuilder(name, packagePath)
        self._packages.append(package)
        return package


class PythonModuleBuilder(object):
    """A builder for a dynamically creating Python modules.

    @param name: The name of the parent Python package.
    @param path: The path for the parent Python package.
    """

    def __init__(self, name, path):
        self.name = name
        self.path = path

    def createModule(self, name, contents):
        """Create a new module in this package.

        @param name: The name of the module.
        @param contents: The Python code to write to the module file.
        """
        filename = name + '.py'
        with open(os.path.join(self.path, filename), 'w') as module:
            module.write(contents)


class PythonPackageBuilderResource(TestResource):
    """Resource provides facilities to build temporary Python packages."""

    def make(self, dependency_resources):
        """Create a Python package factory."""
        factory = PythonPackageBuilder()
        factory.setUp()
        return factory

    def clean(self, factory):
        """Destroy dynamically created Python packages."""
        factory.tearDown()


_threadPool = None


class ThreadPoolResource(TestResource):
    """
    Resource provides a running thread pool with a single available thread.
    """

    def make(self, dependency_resources):
        """Create and start a new thread pool."""
        from twisted.internet import reactor

        global _threadPool
        if _threadPool is None:
            _threadPool = ThreadPool(minthreads=1, maxthreads=1)
            reactor.callWhenRunning(_threadPool.start)
            reactor.addSystemEventTrigger('during', 'shutdown',
                                          _threadPool.stop)
        return _threadPool


class LoggingResource(TestResource):
    """Resource configures logging and provides access to the log stream.

    @param format: The format string to use with the logger.
    """

    def __init__(self, format=None):
        super(LoggingResource, self).__init__()
        self._format = format

    def make(self, dependency_resources):
        """Setup logging and return the log stream."""
        stream = StringIO()
        log = logging.getLogger()
        while log.handlers:
            log.removeHandler(log.handlers.pop())
        setupLogging(stream=stream, format=self._format)
        return stream


class ConfigResource(TestResource):
    """Resource provides a configuration instance.

    The configuration instance is registered globally and can be retrieved
    with L{getConfig}.  It has an C{url} field in the C{index} section, by
    default.
    """

    _originalConfig = None

    def make(self, dependency_resources):
        """Setup the configuration instance."""
        from fluiddb.application import setupConfig

        config = setupConfig(path=None, port=None, development=True)
        self._originalConfig = getConfig()
        setConfig(config)
        return config

    def clean(self, config):
        """Restore the original configuration."""
        setConfig(self._originalConfig)


class CacheResource(TestResource):
    """
    Test resource cleans Redis and provides a ready-to-use C{Redis} client
    instance.
    """

    def make(self, dependency_resources):
        host = '127.0.0.1'
        port = 6379
        db = 1  # Use DB number 1 instead of 0 for testing purposes.
        db = int(os.environ.get('FLUIDDB_CACHE', db))
        connectionPool = ConnectionPool(host=host, port=port, db=db)
        setCacheConnectionPool(connectionPool)
        client = Redis(connection_pool=connectionPool)
        client.flushdb()  # Delete everything from the cache.
        return client

    def clean(self, client):
        host = '127.0.0.1'
        # Use a broken port to simulate Redis being unavailable.
        port = 9999
        db = 1  # Use DB number 1 instead of 0 for testing purposes.
        connectionPool = ConnectionPool(host=host, port=port, db=db)
        setCacheConnectionPool(connectionPool)


class BrokenCacheResource(TestResource):
    """
    Test resource puts the Redis connection pool into a broken state to
    simulate Redis being unavailable.
    """

    def make(self, dependency_resources):
        host = '127.0.0.1'
        # Use a broken port to simulate Redis being unavailable.
        port = 9999
        db = 1  # Use DB number 1 instead of 0 for testing purposes.
        connectionPool = ConnectionPool(host=host, port=port, db=db)
        setCacheConnectionPool(connectionPool)
