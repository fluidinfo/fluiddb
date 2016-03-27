from ConfigParser import RawConfigParser
from cStringIO import StringIO
from datetime import datetime
import logging
import os
from textwrap import dedent
from uuid import uuid4

from fluiddb.application import (
    APIServiceOptions, FluidinfoSessionFactory, FluidinfoSession, setupConfig,
    setupOptions, setupLogging, setupStore, setupFacade, setupRootResource,
    getConfig, getDevelopmentMode, setupCache, getCacheConnectionPool)
from fluiddb.data.system import createSystemData
from fluiddb.model.user import UserAPI
from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import (
    ConfigResource, DatabaseResource, TemporaryDirectoryResource,
    ThreadPoolResource)
from fluiddb.util.transact import Transact


class SetupConfigTest(FluidinfoTestCase):

    resources = [('fs', TemporaryDirectoryResource())]

    def setUp(self):
        super(SetupConfigTest, self).setUp()
        content = dedent("""\
            [service]
            temp-path = var/run
            trace-path = var/log
            max-threads = 2
            port = 9000

            [store]
            main-uri = postgres://fluiddb:fluiddb@localhost/fluiddb-test

            [index]
            url = http://localhost:8080/solr
            shards = localhost:8080/solr

            [cache]
            host = 127.0.0.1
            port = 6379
            db = 0
            expire-timeout = 3600

            [oauth]
            access-secret = testaccesssecret
            renewal-secret = testrenewalsecrt
            renewal-token-duration = 24

            [comments]
            extract-atnames = true
            extract-hashtags = true
            extract-plustags = true
            extract-urls = true
            extract-files = true
            file-object = :files:
            """)
        self.path = self.fs.makePath(content)

    def testSetupConfig(self):
        """L{setupConfig} loads data from a configuration file."""
        config = setupConfig(self.path)
        self.assertEqual('var/run', config.get('service', 'temp-path'))
        self.assertEqual('var/log', config.get('service', 'trace-path'))
        self.assertEqual('2', config.get('service', 'max-threads'))
        self.assertEqual('9000', config.get('service', 'port'))
        self.assertEqual('False', config.get('service', 'development'))
        self.assertEqual('http://localhost:8080/solr',
                         config.get('index', 'url'))
        self.assertEqual('localhost:8080/solr',
                         config.get('index', 'shards'))
        self.assertEqual('postgres://fluiddb:fluiddb@localhost/fluiddb-test',
                         config.get('store', 'main-uri'))
        self.assertEqual('127.0.0.1', config.get('cache', 'host'))
        self.assertEqual(6379, config.getint('cache', 'port'))
        self.assertEqual(0, config.getint('cache', 'db'))
        self.assertEqual(3600, config.getint('cache', 'expire-timeout'))
        self.assertEqual('testaccesssecret',
                         config.get('oauth', 'access-secret'))
        self.assertEqual('testrenewalsecrt',
                         config.get('oauth', 'renewal-secret'))
        self.assertEqual('24', config.get('oauth', 'renewal-token-duration'))
        self.assertTrue(config.getboolean('comments', 'extract-atnames'))
        self.assertTrue(config.getboolean('comments', 'extract-hashtags'))
        self.assertTrue(config.getboolean('comments', 'extract-plustags'))
        self.assertTrue(config.getboolean('comments', 'extract-urls'))
        self.assertTrue(config.getboolean('comments', 'extract-files'))
        self.assertEqual(':files:', config.get('comments', 'file-object'))

    def testSetupConfigWithCustomPort(self):
        """
        L{setupConfig} can override the port defined in the configuration
        file.
        """
        config = setupConfig(self.path, port=9002)
        self.assertEqual('9002', config.get('service', 'port'))

    def testSetupConfigWithCustomDevelopmentMode(self):
        """L{setupConfig} can override the development mode flag."""
        config = setupConfig(self.path, development=True)
        self.assertEqual('True', config.get('service', 'development'))


class SetupOptionsTest(FluidinfoTestCase):

    resources = [('fs', TemporaryDirectoryResource())]

    def setUp(self):
        super(SetupOptionsTest, self).setUp()
        content = dedent("""\
            [service]
            temp-path = var/run
            trace-path = var/log
            max-threads = 2
            port = 9000
            allow-anonymous-access = True

            [store]
            main-uri = postgres://fluiddb:fluiddb@localhost/fluiddb-test

            [index]
            url = http://localhost:8080/solr
            shards = localhost:8080/solr

            [cache]
            host = 127.0.0.1
            port = 6379
            db = 0
            expire-timeout = 3600

            [oauth]
            access-secret = testaccesssecret
            renewal-secret = testrenewalsecrt
            renewal-token-duration = 24

            [comments]
            extract-atnames = true
            extract-hashtags = true
            extract-plustags = true
            extract-urls = true
            extract-files = true
            file-object = :files:
            """)
        self.path = self.fs.makePath(content)

    def testSetupOptions(self):
        """
        L{setupOptions} loads a configuration using information from an
        L{APIServiceOptions} instance.
        """
        options = APIServiceOptions()
        options.parseOptions(['--config', self.path])
        config = setupOptions(options)
        self.assertEqual('var/run', config.get('service', 'temp-path'))
        self.assertEqual('var/log', config.get('service', 'trace-path'))
        self.assertEqual('2', config.get('service', 'max-threads'))
        self.assertEqual('9000', config.get('service', 'port'))
        self.assertEqual('True',
                         config.get('service', 'allow-anonymous-access'))
        self.assertEqual('False', config.get('service', 'development'))
        self.assertEqual('postgres://fluiddb:fluiddb@localhost/fluiddb-test',
                         config.get('store', 'main-uri'))
        self.assertEqual('http://localhost:8080/solr',
                         config.get('index', 'url'))
        self.assertEqual('localhost:8080/solr',
                         config.get('index', 'shards'))
        self.assertEqual('127.0.0.1', config.get('cache', 'host'))
        self.assertEqual(6379, config.getint('cache', 'port'))
        self.assertEqual(0, config.getint('cache', 'db'))
        self.assertEqual(3600, config.getint('cache', 'expire-timeout'))
        self.assertEqual('testaccesssecret',
                         config.get('oauth', 'access-secret'))
        self.assertEqual('testrenewalsecrt',
                         config.get('oauth', 'renewal-secret'))
        self.assertEqual('24', config.get('oauth', 'renewal-token-duration'))
        self.assertTrue(config.getboolean('comments', 'extract-atnames'))
        self.assertTrue(config.getboolean('comments', 'extract-hashtags'))
        self.assertTrue(config.getboolean('comments', 'extract-plustags'))
        self.assertTrue(config.getboolean('comments', 'extract-urls'))
        self.assertTrue(config.getboolean('comments', 'extract-files'))
        self.assertEqual(':files:', config.get('comments', 'file-object'))

    def testSetupOptionsWithoutPath(self):
        """
        L{setupOptions} loads a default configuration if no path is provided.
        """
        options = APIServiceOptions()
        options.parseOptions([])
        config = setupOptions(options)
        tempPath = config.get('service', 'temp-path')
        self.assertTrue(tempPath.endswith('var/tmp'))
        tracePath = config.get('service', 'trace-path')
        self.assertTrue(tracePath.endswith('var/tmp'))
        self.assertEqual('1', config.get('service', 'max-threads'))
        self.assertEqual('9000', config.get('service', 'port'))
        self.assertEqual('False',
                         config.get('service', 'allow-anonymous-access'))
        self.assertEqual('False', config.get('service', 'development'))
        self.assertEqual(
            'postgres://fluidinfo:fluidinfo@localhost/fluidinfo-test',
            config.get('store', 'main-uri'))
        self.assertEqual('http://localhost:8080/solr',
                         config.get('index', 'url'))
        self.assertEqual('localhost:8080/solr',
                         config.get('index', 'shards'))
        self.assertEqual('127.0.0.1', config.get('cache', 'host'))
        self.assertEqual(6379, config.getint('cache', 'port'))
        self.assertEqual(0, config.getint('cache', 'db'))
        self.assertEqual(3600, config.getint('cache', 'expire-timeout'))
        self.assertEqual('', config.get('oauth', 'access-secret'))
        self.assertEqual('', config.get('oauth', 'renewal-secret'))
        self.assertEqual('168', config.get('oauth', 'renewal-token-duration'))

    def testSetupOptionsOverridesPort(self):
        """
        If an explicit port is defined in the L{APIServiceOptions} instance it
        will be used to override the value in the configuration file.
        """
        options = APIServiceOptions()
        options.parseOptions(['--config', self.path, '--port', '9003'])
        config = setupOptions(options)
        self.assertEqual('9003', config.get('service', 'port'))

    def testSetupOptionsOverridesDevelopmentMode(self):
        """
        If the development mode flag is defined in the L{APIServiceOptions}
        instance it will be used to set the development mode.
        """
        options = APIServiceOptions()
        options.parseOptions(['--config', self.path, '--development'])
        config = setupOptions(options)
        self.assertEqual('True', config.get('service', 'development'))


class SetupCacheTest(FluidinfoTestCase):

    def setUp(self):
        super(SetupCacheTest, self).setUp()

    def testSetupCache(self):
        """
        L{setupCache} creates a new L{redis.ConnectionPool} with the defined
        configuration.
        """
        config = setupConfig(None)
        connectionPool = setupCache(config)

        expected = {
            'host': config.get('cache', 'host'),
            'port': config.getint('cache', 'port'),
            'db': config.getint('cache', 'db')
        }
        self.assertEqual(expected, connectionPool.connection_kwargs)

    def testSetupCacheSetsGlobalValue(self):
        """
        L{setupCache} makes the new L{redis.ConnectionPool} available via the
        global L{fluiddb.application.getCacheConnectionPool} function.
        """
        config = setupConfig(None)
        connectionPool = setupCache(config)
        self.assertIdentical(connectionPool, getCacheConnectionPool())


class SetupLoggingTest(FluidinfoTestCase):

    resources = [('fs', TemporaryDirectoryResource())]

    def tearDown(self):
        log = logging.getLogger()
        while log.handlers:
            log.removeHandler(log.handlers.pop())
        super(SetupLoggingTest, self).tearDown()

    def testSetupLoggingWithStream(self):
        """
        L{setupLogging} can configure logging to write messages to a stream.
        """
        stream = StringIO()
        setupLogging(stream=stream)
        logging.info('Test log message.')
        self.assertIn('Test log message.', stream.getvalue())

    def testSetupLoggingWithStreamSupportsUnicode(self):
        """
        The log configured by L{setupLogging} handles C{unicode} messages
        properly.
        """
        stream = StringIO()
        setupLogging(stream=stream)
        logging.info(u'\N{HIRAGANA LETTER A}')
        logging.getLogger().handlers[0].flush()
        self.assertIn(u'\N{HIRAGANA LETTER A}'.encode('utf-8'),
                      stream.getvalue())

    def testSetupLoggingUsesRootLogger(self):
        """L{setupLogging} configures the C{logging} module's root logger."""
        stream = StringIO()
        log = setupLogging(stream=stream)
        self.assertIdentical(log, logging.getLogger())

    def testSetupLoggingUsesDebugLevel(self):
        """L{setupLogging} uses the C{logging.INFO} log level, by default."""
        stream = StringIO()
        setupLogging(stream=stream)
        self.assertEqual(logging.INFO, logging.getLogger().level)

    def testSetupLoggingWithCustomLevel(self):
        """L{setupLogging} sets the log level passed by the caller."""
        stream = StringIO()
        log = setupLogging(stream=stream, level=logging.CRITICAL)
        self.assertEqual(logging.CRITICAL, log.level)

    def testSetupLoggingWithFile(self):
        """
        L{setupLogging} can configure logging to write messages to a file.
        """
        path = self.fs.makePath()
        setupLogging(path=path)
        logging.info('Log message.')
        logging.getLogger().handlers[0].flush()
        with open(path, 'r') as log:
            self.assertIn('Log message.', log.read())

    def testSetupLoggingWithFileSupportsUnicode(self):
        """
        The log configured by L{setupLogging} handles C{unicode} messages
        properly.
        """
        path = self.fs.makePath()
        setupLogging(path=path)
        logging.info(u'\N{HIRAGANA LETTER A}')
        logging.getLogger().handlers[0].flush()
        with open(path, 'r') as log:
            self.assertIn(u'\N{HIRAGANA LETTER A}'.encode('utf-8'), log.read())

    def testSetupLoggingWithFileSupportsLogRotation(self):
        """
        L{setupLogging} uses a C{WatchedFileHandler} when a path is used.  The
        handler automatically reopens the log file if it gets moved, by
        logrotate for example.
        """
        path = self.fs.makePath()
        setupLogging(path=path)
        logging.info('Log message 1.')
        os.rename(path, '%s.1' % path)
        logging.info('Log message 2.')
        logging.getLogger().handlers[0].flush()
        with open(path, 'r') as log:
            self.assertIn('Log message 2.', log.read())
        with open('%s.1' % path, 'r') as log:
            self.assertIn('Log message 1.', log.read())


class SetupStoreTest(FluidinfoTestCase):

    def testSetupStore(self):
        """
        L{setupStore} configures and registers a C{ZStorm} instance using the
        URI defined in the configuration file.
        """
        config = RawConfigParser()
        config.add_section('store')
        config.set('store', 'main-uri', 'sqlite:')
        try:
            zstorm = setupStore(config)
            store = zstorm.get('main')
            self.assertEqual(':memory:', store.get_database()._filename)
        finally:
            for name, store in zstorm.iterstores():
                zstorm.remove(store)


class SetupFacadeTest(FluidinfoTestCase):

    def testSetupFacade(self):
        """
        L{setupFacade} creates a L{Facade} with a L{Transact} instance
        configured to use the number of threads defined in the configuration
        file.
        """
        config = RawConfigParser()
        config.add_section('service')
        config.set('service', 'max-threads', '3')
        config.set('service', 'port', '9000')
        facade = setupFacade(config)
        self.assertEqual(3, facade._transact._threadPool.max)
        self.assertEqual('API-9000', facade._factory._prefix)


class SetupRootResourceTest(FluidinfoTestCase):

    def testSetupRootResource(self):
        """
        L{setupRootResource} configures authentication utilities and registers
        the facade with the realm.
        """
        config = RawConfigParser()
        config.add_section('service')
        config.set('service', 'max-threads', '3')
        config.set('service', 'port', '9000')
        facade = setupFacade(config)
        resource = setupRootResource(facade)
        self.assertIdentical(facade, resource._portal.realm.facadeClient)


class GetDevelopmentModeTest(FluidinfoTestCase):

    resources = [('config', ConfigResource())]

    def testGetDevelopmentMode(self):
        """
        L{getDevelopmentMode} returns the flag specifying whether or not
        development mode is in use, which is C{True} by default.
        """
        self.assertTrue(getDevelopmentMode())

    def testGetDevelopmentModeEnabled(self):
        """
        L{getDevelopmentMode} returns the flag specifying whether or not
        development mode is in use.
        """
        config = getConfig()
        config.set('service', 'development', 'True')
        self.assertTrue(getDevelopmentMode())


class FluidinfoSessionTest(FluidinfoTestCase):

    resources = [('config', ConfigResource()),
                 ('fs', TemporaryDirectoryResource()),
                 ('store', DatabaseResource()),
                 ('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(FluidinfoSessionTest, self).setUp()
        self.transact = Transact(self.threadPool)

    def testLogin(self):
        """L{AuthenticationPlugin.login} stores the provided credentials."""
        objectID = uuid4()
        session = FluidinfoSession('id', self.transact)
        session.start()
        try:
            session.auth.login(u'username', objectID)
        finally:
            session.stop()
        self.assertEqual(u'username', session.auth.username)
        self.assertEqual(objectID, session.auth.objectID)

    def testLoginWithoutStart(self):
        """
        L{AuthenticationPlugin.login} raises a C{RuntimeError} if the session
        hasn't been started.
        """
        session = FluidinfoSession('id', self.transact)
        self.assertRaises(RuntimeError,
                          session.auth.login, u'username', uuid4())

    def testUser(self):
        """
        The L{AuthenticationPlugin.user} property returns the L{User} instance
        for the session.
        """
        createSystemData()
        [(objectID, username)] = UserAPI().create(
            [(u'user', u'secret', u'User', u'user@example.com')])
        session = FluidinfoSession('id', self.transact)
        session.start()
        try:
            session.auth.login(username, objectID)
        finally:
            session.stop()
        self.assertEqual(u'user', session.auth.user.username)

    def testDumpsAndLoads(self):
        """
        Data stored by a L{LoggingPlugin} can be dumped to and loaded from
        JSON.
        """
        objectID = uuid4()
        session = FluidinfoSession('id', self.transact)
        session.start()
        try:
            session.auth.login(u'username', objectID)
        finally:
            session.stop()
        data = session.dumps()
        loadedSession = FluidinfoSession('another-id', self.transact)
        loadedSession.loads(data)
        self.assertEqual(session.auth.username, loadedSession.auth.username)
        self.assertEqual(session.auth.objectID, loadedSession.auth.objectID)


class FluidinfoSessionFactoryTest(FluidinfoTestCase):

    resources = [('threadPool', ThreadPoolResource())]

    def setUp(self):
        super(FluidinfoSessionFactoryTest, self).setUp()
        self.transact = Transact(self.threadPool)

    def testCreate(self):
        """L{SessionFactory.create} creates a new L{Session} instance."""
        now = datetime.utcnow()
        factory = FluidinfoSessionFactory('API-9001', lambda: now)
        session = factory.create(self.transact)
        expectedDate = now.strftime('%Y%m%d-%H%M%S')
        self.assertEqual('API-9001-%s-000001' % expectedDate, session.id)

    def testCreateIncrementsCount(self):
        """
        The counter, appended at the end of the L{Session.id}, is incremented
        each time an L{Session} is created.
        """
        now = datetime.utcnow()
        factory = FluidinfoSessionFactory('API-9001', lambda: now)
        factory.create(self.transact)
        session = factory.create(self.transact)
        expectedDate = now.strftime('%Y%m%d-%H%M%S')
        self.assertEqual('API-9001-%s-000002' % expectedDate, session.id)
