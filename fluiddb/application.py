"""Logic needed to bootstrap the Fluidinfo API service."""

from ConfigParser import RawConfigParser
from datetime import datetime
from logging import getLogger, Formatter, StreamHandler, INFO
from logging.handlers import WatchedFileHandler
import os
import sys
from uuid import UUID

from redis import ConnectionPool
from storm.zope.interfaces import IZStorm
from storm.zope.zstorm import ZStorm
from twisted.application.internet import TCPServer
from twisted.application.service import Application
from twisted.conch.manhole import Manhole
from twisted.conch.manhole_ssh import TerminalRealm, ConchFactory
from twisted.conch.checkers import SSHPublicKeyDatabase
from twisted.cred.portal import Portal
from twisted.internet import reactor
from twisted.python.log import ILogObserver, PythonLoggingObserver
from twisted.python.threadpool import ThreadPool
from twisted.web.guard import (
    HTTPAuthSessionWrapper, BasicCredentialFactory)
from twisted.web.server import Site
from zope.component import getUtility, provideUtility

from fluiddb.scripts.twistd import ServerOptions
from fluiddb.util.oauth_credentials import OAuthCredentialFactory
from fluiddb.util.oauth2_credentials import OAuth2CredentialFactory
from fluiddb.util.session import (
    Session, HTTPPlugin, LoggingPlugin, TimerPlugin, TransactPlugin)


__all__ = ['APIServiceOptions', 'getConfig', 'setConfig', 'setupApplication']


class APIServiceOptions(ServerOptions):
    """Command-line options for the API service."""


APIServiceOptions.optParameters.append(
    ['config', 'c', None, 'The path to the config file.'])
APIServiceOptions.optParameters.append(
    ['port', None, '9000', 'The port to listen on.'])
APIServiceOptions.optFlags.append(
    ['development', None, 'Run the API service in development mode.'])


_config = None


def getConfig():
    """Get the configuration.

    @return: A configuration instance or C{None} if one hasn't been
        registered.
    """
    return _config


def setConfig(config):
    """Set the configuration.

    @param: A configuration instance.
    """
    global _config
    _config = config


_cacheConnectionPool = None


def getCacheConnectionPool():
    """Get a Redis connection pool.

    @return: A L{redis.ConnectionPool} object or None if one hasn't been
        registered.
    """
    return _cacheConnectionPool


def setCacheConnectionPool(connectionPool):
    """Set the Redis connection pool.

    @param: A L{redis.ConnectionPool} object.
    """
    global _cacheConnectionPool
    _cacheConnectionPool = connectionPool


def getDevelopmentMode():
    """Get the development mode flag.

    @return: C{True} if development mode is enabled, otherwise C{False}.
    """
    config = getConfig()
    return config.getboolean('service', 'development')


def setupApplication(options):
    """Setup the API service.

    @param options: A parsed L{APIServiceOptions} instance.
    @return: A C{(port, site, application)} 3-tuple.
    """
    config = setupOptions(options)
    setConfig(config)
    setupStore(config)
    setupCache(config)
    facade = setupFacade(config)
    root = setupRootResource(facade,
                             development=bool(options.get('development')))
    site = Site(root)
    application = Application('fluidinfo-api')

    setupManhole(application, config)

    if options.get('nodaemon') and not options.get('logfile'):
        setupLogging(stream=sys.stdout, level=INFO)
    else:
        logPath = options.get('logfile', 'fluidinfo-api.log')
        setupLogging(path=logPath, level=INFO)
    setupTwistedLogging(application)

    return int(config.get('service', 'port')), site, application


def setupManhole(application, config):
    """Setup an SSH manhole for the API service.

    The manhole port is taken from the C{manhole-port} option in the config
    file. If this option is not provided the api port plus 100 is used.

    @param application: The fluidinfo API L{Application} object.
    @param config: The configuration object.
    """
    servicePort = config.getint('service', 'port')
    if config.has_option('service', 'manhole-port'):
        manholePort = config.getint('service', 'manhole-port')
    else:
        manholePort = servicePort + 100

    def getManhole(_):
        manhole = Manhole(globals())
        ps1 = 'fluidinfo-api [%d] > ' % servicePort
        ps2 = '... '.rjust(len(ps1))
        manhole.ps = (ps1, ps2)
        return manhole

    realm = TerminalRealm()
    realm.chainedProtocolFactory.protocolFactory = getManhole
    portal = Portal(realm)
    portal.registerChecker(SSHPublicKeyDatabase())
    factory = ConchFactory(portal)
    manholeService = TCPServer(manholePort, factory, interface='127.0.0.1')
    manholeService.setServiceParent(application)


def setupOptions(options):
    """
    Load a configuration and override its properties with command-line
    options.

    @param options: An L{APIServiceOptions} instance, optionally with
        overrides for the configuration file.
    @return: A configuration instance.
    """
    configPath = options.get('config')
    return setupConfig(configPath, port=options.get('port'),
                       development=bool(options.get('development')))


def setupConfig(path, port=None, development=None):
    """Load a configuration and specialize it for the API service instance.

    The following fields are expected to be in the configuration file in the
    C{service} section:

      * temp-path - The directory to create temporary files in.
      * trace-path - The directory to create trace log files in.
      * max-threads - The maximum number of database threads to use.
      * port - The port number for API service to use.
      * allow-anonymous-access - A C{True} or C{False} value that determines
        whether or not to allow requests made by the C{anon} user.  Default is
        C{False}.

    A special C{development} field will be added to the C{service} section of
    the configuration.  By default, it has a C{True} string value, otherwise
    it has a C{False} value.

    The following fields are expected to be in the configuration file in the
    C{store} section:

      * main-uri - The Storm-compatible URI to the PostgreSQL database.

    The following fields are expected to be in the configuration file in the
    C{index} section:

      * url - The URL to the Solr index server.
      * shards - The list of URLs of the Solr shards separated by commas.

    The following fields are expected to be in the configuration file in the
    C{oauth} section:

      * access-secret - The secret to use when generating tokens during the
        OAuth Echo process.  This value must be exactly 16 characters long.
      * renewal-secret - The secret to use when generating renewal tokens for
        use when regenerating OAuth access tokens.  This value must be exactly
        16 characters long.
      * renewal-token-duration - The length of time, in hours, that a renewal
        token is valid for.

    The following fields are expected to be in the configuration file in the
    C{comments} section:

      * extract-atnames - If true, @names in comments will be detected and
        added to the list of things the comment is about.

      * extract-hashtags - If true, #hashtags in comments will be detected and
        added to the list of things the comment is about.

      * extract-plustags - If true, +plustags in comments will be detected and
        added to the list of things the comment is about.

      * extract-urls - If true, URLs in comments will be detected and
        added to the list of things the comment is about.

      * extract-files - If true, file:type:hash in comments will be detected
        and added to the list of things the comment is about.

      * file-object - Is a common object linked to all file:type:hash files.

    Field values are always strings.  If an explicit C{port} is provided it
    will override the value loaded from the configuration file.

    @param path: Optionally, the location of the configuration file to load.
        Default values will be used if a path isn't provided.
    @param port: Optionally, a port number to use in preference to the one in
        the configuration file.
    @param development: Optionally, a boolean flag to indicate whether
        development mode should be enabled.
    @return: A configuration instance.
    """
    config = RawConfigParser()
    if path:
        with open(path, 'r') as configFile:
            config.readfp(configFile)
    else:
        config.add_section('service')
        config.set('service', 'temp-path', getBranchPath('var/tmp'))
        config.set('service', 'trace-path', getBranchPath('var/tmp'))
        config.set('service', 'max-threads', '1')
        config.set('service', 'port', '9000')
        config.set('service', 'allow-anonymous-access',
                   'True' if development else 'False')

        config.add_section('store')
        config.set('store', 'main-uri',
                   'postgres://fluidinfo:fluidinfo@localhost/fluidinfo-test')

        config.add_section('index')
        config.set('index', 'url', 'http://localhost:8080/solr')
        config.set('index', 'shards', 'localhost:8080/solr')

        config.add_section('cache')
        config.set('cache', 'host', '127.0.0.1')
        config.set('cache', 'port', 6379)
        config.set('cache', 'db', 0)
        config.set('cache', 'expire-timeout', 3600)

        config.add_section('oauth')
        config.set('oauth', 'access-secret', '')
        config.set('oauth', 'renewal-secret', '')
        config.set('oauth', 'renewal-token-duration', '168')

        config.add_section('comments')
        config.set('comments', 'extract-atnames', 'true')
        config.set('comments', 'extract-hashtags', 'true')
        config.set('comments', 'extract-plustags', 'true')
        config.set('comments', 'extract-urls', 'true')
        config.set('comments', 'extract-files', 'true')
        config.set('comments', 'file-object', ':files:')

    if port is not None:
        config.set('service', 'port', str(port))

    if development is None:
        development = False
    config.set('service', 'development', str(development))
    return config


def getBranchPath(path):
    """Get a path rooted in the current branch.

    @param path: A path relative to the current branch.
    @return: A fully-qualified path.
    """
    currentPath = os.path.dirname(__file__)
    fullyQualifiedPath = os.path.join(currentPath, '..', path)
    return os.path.abspath(fullyQualifiedPath)


def setupCache(config):
    """Setup the Redis Cache

    A new L{redis.ConnectionPool} is created using the values defined in the
    configuration, and then registered with L{setCacheConnectionPool}

    @param config: a configuration instance.
    @return a L{redis.ConnectionPool}.
    """
    host = config.get('cache', 'host')
    port = config.getint('cache', 'port')
    db = config.getint('cache', 'db')
    connectionPool = ConnectionPool(host=host, port=port, db=db)
    setCacheConnectionPool(connectionPool)
    return connectionPool


def setupLogging(stream=None, path=None, level=None, format=None):
    """Setup logging.

    Either a stream or a path can be provided.  When a path is provided a log
    handler that works correctly with C{logrotate} is used.  Generally
    speaking, C{stream} should only be used for non-file streams that don't
    need log rotation.

    @param name: The name of the logger to setup.
    @param stream: The stream to write output to.
    @param path: The path to write output to.
    @param level: Optionally, the log level to set on the logger.  Default is
        C{logging.INFO}.
    @param format: A format string for the logger.
    @raise RuntimeError: Raised if neither C{stream} nor C{path} are provided,
        or if both are provided.
    @return: The configured logger, ready to use.
    """
    if (not stream and not path) or (stream and path):
        raise RuntimeError('A stream or path must be provided.')
    if stream:
        handler = StreamHandler(stream)
    else:
        handler = WatchedFileHandler(path)

    if format is None:
        format = '%(asctime)s %(levelname)8s  %(message)s'

    formatter = Formatter(format)
    handler.setFormatter(formatter)
    log = getLogger()
    log.addHandler(handler)
    log.propagate = False
    log.setLevel(level or INFO)
    return log


def setupTwistedLogging(application):
    """Setup a L{LogFile} for the given application.

    @param application: A C{twisted.application.service.Application} instance.
    """
    application.setComponent(ILogObserver, PythonLoggingObserver(None).emit)


def setupStore(config):
    """Setup the main store.

    A C{ZStorm} instance is configured and registered as a global utility.

    @param config: A configuration instance.
    @return: A configured C{ZStorm} instance.
    """
    zstorm = ZStorm()
    provideUtility(zstorm)
    uri = config.get('store', 'main-uri')
    zstorm.set_default_uri('main', uri)
    return zstorm


def verifyStore():
    """Ensure that the patch level in the database matches the application.

    @raise RuntimeError: Raised if there are unknown or unapplied patches.
    """
    from fluiddb.schema.main import createSchema
    from fluiddb.scripts.schema import getPatchStatus

    schema = createSchema()
    zstorm = getUtility(IZStorm)
    store = zstorm.get('main')
    try:
        status = getPatchStatus(store, schema)
        if status.unappliedPatches:
            patches = ', '.join('patch_%d' % version
                                for version in status.unappliedPatches)
            raise RuntimeError('Database has unapplied patches: %s' % patches)
        if status.unknownPatches:
            patches = ', '.join('patch_%d' % version
                                for version in status.unknownPatches)
            raise RuntimeError('Database has unknown patches: %s' % patches)
    finally:
        zstorm.remove(store)
        store.close()


def setupFacade(config):
    """Get the L{Facade} instance to use in the API service."""
    from fluiddb.api.facade import Facade
    from fluiddb.util.transact import Transact

    maxThreads = int(config.get('service', 'max-threads'))
    threadpool = ThreadPool(minthreads=0, maxthreads=maxThreads)
    reactor.callWhenRunning(threadpool.start)
    reactor.addSystemEventTrigger('during', 'shutdown', threadpool.stop)
    transact = Transact(threadpool)
    factory = FluidinfoSessionFactory('API-%s' % config.get('service', 'port'))
    return Facade(transact, factory)


def setupRootResource(facade, development=None):
    """Get the root resource to use for the API service.

    @param facade: A L{Facade} instance.
    @return: An C{HTTPAuthSessionWrapper} instance.
    """
    from fluiddb.web.root import WSFERealm, IFacadeRealm
    from fluiddb.web.checkers import (
        AnonymousChecker, FacadeChecker, FacadeOAuthChecker,
        FacadeOAuth2Checker, IFacadeChecker)

    portal = Portal(WSFERealm(), [FacadeChecker(), FacadeOAuthChecker(),
                                  FacadeOAuth2Checker(), AnonymousChecker()])
    realm = IFacadeRealm(portal.realm)
    realm.facadeClient = facade
    for checker in portal.checkers.values():
        if IFacadeChecker.providedBy(checker):
            checker.facadeClient = facade

    factories = [BasicCredentialFactory('fluidinfo.com'),
                 OAuthCredentialFactory('fluidinfo.com'),
                 OAuth2CredentialFactory('fluidinfo.com', development)]
    return HTTPAuthSessionWrapper(portal, factories)


class AuthenticationPlugin(object):
    """A L{Session} plugin for capturing authentication details."""

    def __init__(self):
        self._session = None
        self.username = None
        self.objectID = None

    def start(self, session):
        """Start the logger for this session.

        @param session: The L{Session} parent of this plugin.
        """
        self._session = session

    def stop(self):
        """Stop the logger for this session."""
        pass

    def login(self, username, objectID):
        """Login to the session.

        @param username: The L{User.username} for this session.
        @param objectID The L{User.objectID} for this session.
        """
        if self._session is None:
            raise RuntimeError('The session must be started first.')
        self.username = username
        self.objectID = objectID

    @property
    def user(self):
        """Get the L{User} for this session.

        This property should only be accessed in a database thread.  The
        L{User} instance is loaded once and cached.  It's never invalidated.

        @return: The L{User} instance for this session.
        """
        if '_user' not in self.__dict__:
            from fluiddb.model.user import getUser

            self._user = getUser(self.username)
        return self._user

    def dumps(self):
        """Write session data to a C{dict}."""
        return {'username': self.username, 'objectID': str(self.objectID)}

    def loads(self, data):
        """Load session data from a C{dict}."""
        self.username = data.get('username')
        self.objectID = UUID(data.get('objectID'))


class FluidinfoSession(Session):
    """Logic for tracking activities in a Fluidinfo session.

    @param id: The unique ID for this session.
    @param transact: The L{Transact} instance to use when running
        transactions.
    """

    # The following timeout (used by Storm to abandon long-running
    # Postgres operations), was increased from 60 to 120 on 2013-10-1
    # due to timeouts on queries from tesco3gm.
    timeout = 120

    def __init__(self, id, transact):
        plugins = {'auth': AuthenticationPlugin(),
                   'http': HTTPPlugin(),
                   'log': LoggingPlugin(),
                   'timer': TimerPlugin(),
                   'transact': TransactPlugin(transact, self.timeout)}
        super(FluidinfoSession, self).__init__(id, plugins)


class FluidinfoSessionFactory(object):
    """A factory for L{FluidinfoSession} instances.

    @param prefix: The prefix to prepend to L{FluidinfoSession.id}'s.  It
        should uniquely identify the process the session is being run in, such
        as C{API-9001} for the API service running on port 9001.
    @param utcnow: For testing purposes, the implementation of
        C{datetime.utcnow} to use when calculating the time.
    """

    def __init__(self, prefix, utcnow=None):
        self._prefix = prefix
        self._count = 0
        self._utcnow = utcnow or datetime.utcnow

    def create(self, transact):
        """Create a new L{Session} instance."""
        self._count += 1
        now = self._utcnow().strftime('%Y%m%d-%H%M%S')
        sessionID = '%s-%s-%06d' % (self._prefix, now, self._count)
        return FluidinfoSession(sessionID, transact)
