from datetime import datetime
from json import load
import logging
import os
import re
import sys
import time
from traceback import print_exc

from bzrlib.commands import Command
from bzrlib.option import Option
from commandant.commands import TwistedCommand
from commandant.formatting import print_columns
from fabric.context_managers import settings
from fabric.contrib.console import confirm
from fabric.operations import local
from fabric.state import connections
from fom.session import Fluid
from storm.zope.zstorm import ZStorm
import transaction
from zope.component import provideUtility

from fluiddb.application import (
    setConfig, setupConfig, setupLogging, setupCache)
from fluiddb.data.user import Role
from fluiddb.model.comment import CommentAPI, parseCommentURL
from fluiddb.schema import logs, main
from fluiddb.scripts.apidocs import buildAPIDocumentation
from fluiddb.scripts.dataset import DatasetImporter
from fluiddb.scripts.deployment import (
    addAdmin, ping, prepareFluidinfo, deployFluidinfo, switchRevision,
    startFluidinfo, stopFluidinfo, restartFluidinfo, updateVersionTag,
    hasUnappliedDatabasePatches, applyDatabasePatches, clearRedisCache,
    createDisk, bootstrapPostgres, bootstrapSolr, bootstrapRedis,
    bootstrapFrontend, bootstrapFluidDB, prepareInstance, updateFluidDB,
    authorizeSshKey)
from fluiddb.scripts.checker import checkIntegrity
from fluiddb.scripts.index import (
    buildIndex, deleteIndex, updateIndex, batchIndex)
from fluiddb.scripts.load import generateLoad
from fluiddb.scripts.logs import (
    loadLogs, loadTraceLogs, reportErrorSummary, reportErrorTracebacks,
    reportTraceLogSummary)
from fluiddb.scripts.schema import (
    bootstrapSystemData, patchDatabase, getPatchStatus, setVersionTag,
    bootstrapWebAdminData)
from fluiddb.scripts.testing import prepareForTesting, removeTestingData
from fluiddb.scripts.user import createUser, deleteUser, updateUser
from fluiddb.cache.cache import getCacheClient


def setupStore(uri, name):
    """Setup the main store.

    @param uri: The URI for the main database.
    """
    zstorm = ZStorm()
    zstorm.set_default_uri(name, uri)
    provideUtility(zstorm)
    return zstorm.get(name)


class cmd_create_user(Command):
    """Create a new Fluidinfo user.

    Documents in the object index are updated when the new user is created.
    The database URI must be compatible with Storm, for example::

      postgres://fluidinfo:fluidinfo@localhost/fluidinfo

    The index URI should point to the HTTP API for an empty Solr index::

      http://localhost:8080/solr
    """

    takes_args = ['database_uri', 'username', 'password',
                  'fullname', 'email']
    takes_options = [
        Option('role', type=str,
               help=("The 'anonymous', 'superuser', 'user' or 'usermanager' "
                     "role for the new user.  Default is 'user'."))]

    def run(self, database_uri, username, password, fullname,
            email, role=None):
        username = username.decode('utf-8')
        password = password.decode('utf-8')
        fullname = '' if fullname is None else fullname.decode('utf-8')
        email = '' if email is None else email.decode('utf-8')
        roles = {'anonymous': Role.ANONYMOUS,
                 'superuser': Role.SUPERUSER,
                 'user': Role.USER,
                 'usermanager': Role.USER_MANAGER}
        role = roles.get(role.lower() if role else 'user')

        config = setupConfig(None)
        config.set('store', 'main-uri', database_uri)
        config.set('index', 'url', '')
        setConfig(config)
        setupLogging(self.outf)
        setupStore(database_uri, 'main')
        createUser(username, password, fullname, email, role)


class cmd_delete_user(Command):
    """Delete a Fluidinfo user.

    The database URI must be compatible with Storm, for example::

      postgres://fluidinfo:fluidinfo@localhost/fluidinfo

    The index URI should point to the HTTP API for an empty Solr index::

      http://localhost:8080/solr
    """

    takes_args = ['database_uri', 'index_url', 'username']

    def run(self, database_uri, index_url, username):
        username = username.decode('utf-8')
        config = setupConfig(None)
        config.set('store', 'main-uri', database_uri)
        config.set('index', 'url', str(index_url))
        setConfig(config)
        setupLogging(self.outf)
        setupStore(database_uri, 'main')
        deleteUser(username)


class cmd_update_user(Command):
    """Update user details."""

    takes_args = ['database_uri', 'username']
    takes_options = [
        Option('email', type=unicode, help=('The new email for the user.')),
        Option('fullname', type=unicode,
               help=('The new full name for the user.')),
        Option('password', type=unicode,
               help=('The new password for the user.')),
        Option('role', type=unicode,
               help=('The new role for the user. Can be: ANONYMOUS, USER, '
                     'SUPERUSER or USER_MANAGER. Case sensitive'))]

    def run(self, database_uri, username, email=None, fullname=None,
            password=None, role=None):

        if not any([email, fullname, password, role]):
            print ('You must provide an email, name, password, or role '
                   'to update.')
            return

        if role is not None:
            try:
                role = Role.fromName(role)
            except LookupError:
                print 'Invalid role'
                return

        config = setupConfig(None)
        config.set('store', 'main-uri', database_uri)
        setConfig(config)
        setupLogging(self.outf)
        setupStore(database_uri, 'main')
        updateUser(username, password, fullname, email, role)


class cmd_update_version_tag(TwistedCommand):
    """Updates the fluiddb/version tag on the "fluidinfo" object.

    The database URI must be compatible with Storm, for example::

      postgres://fluidinfo:fluidinfo@localhost/fluidinfo

    The index URI should point to the HTTP API for an empty Solr index::

      http://localhost:8080/solr
    """

    takes_args = ['database_uri', 'version']

    def run(self, database_uri, version):
        version = version.decode('utf-8')
        config = setupConfig(None)
        config.set('store', 'main-uri', database_uri)
        setConfig(config)
        setupLogging(self.outf)
        setupStore(database_uri, 'main')
        setVersionTag(version)


class cmd_bootstrap_database(Command):
    """Create the schema and system data for a new database.

    A fresh schema with system data, such as the 'fluidinfo' user and builtin
    tags like 'fluiddb/description', are created in the specified database.
    The database URI must be compatible with Storm, for example::

      postgres://fluidinfo:fluidinfo@localhost/fluidinfo

    Care must be taken to ensure the 'fluidinfo' PostgreSQL database user has
    appropriate permissions.  The database being initialized should be created
    with 'fluidinfo' as the owner::

      createdb fluidinfo -O fluidinfo
    """

    takes_args = ['database_uri']

    def run(self, database_uri):
        setConfig(setupConfig(None))
        setupLogging(self.outf)
        store = setupStore(database_uri, 'main')
        schema = main.createSchema()
        logging.info('Creating schema.')
        patchDatabase(store, schema)
        logging.info('Creating system data.')
        bootstrapSystemData(store)
        logging.info('Creating web admin data.')
        bootstrapWebAdminData()


class cmd_prepare_for_testing(Command):
    """
    Create a set of users, namespaces and tags for being used in integration
    tests.

    Users created:
     - testuser1
     - testuser2

    Namespaces created:
     - fluiddb/testing
     - fluiddb/testing/testing
     - testuser1/testing
     - testuser1/testing/testing
     - testuser2/testing
     - testuser2/testing/testing

    Tags created:
     - fluiddb/testing/test1
     - fluiddb/testing/test2
     - testuser1/testing/test1
     - testuser1/testing/test2
     - testuser2/testing/test1
     - testuser2/testing/test2
    """

    takes_args = ['database_uri']
    _see_also = ['remove-testing-data']

    def run(self, database_uri):
        setConfig(setupConfig(None))
        setupLogging(self.outf)
        setupStore(database_uri, 'main')
        prepareForTesting()


class cmd_remove_testing_data(Command):
    """
    Remove the users, namespaces and tags used for integration tests.
    """

    takes_args = ['database_uri']
    _see_also = ['prepare-for-testing']

    def run(self, database_uri):
        setConfig(setupConfig(None))
        setupLogging(self.outf)
        setupStore(database_uri, 'main')
        removeTestingData()


class cmd_check_integrity(Command):
    """Check the database for integrity errors.

    The checker will detect the following errors:
      - L{Namespace}s, L{Tag}s or L{User}s without system tags such as
        C{fluiddb/about} or C{fluiddb/tags/path}.
      - L{Namespace}s or L{Tag}s with invalid paths.
      - L{Namespace}s or L{Tag}s with incorrect associated parents.
      - L{Namespace}s or L{Tag}s without permissions.
      - L{Namespace}s or L{Tag}s with invalid permission exceptions lists.
      - L{User}s with incorrect usernames.
      - L{User}s without a root L{Namespace}.
      - L{AboutTagValue}s without a corresponding C{fluiddb/about} L{TagValue}.
      - System L{TagValue}s without their corresponding object.

    The database URI must be compatible with Storm, for example::

      postgres://fluidinfo:fluidinfo@localhost/fluidinfo
    """

    takes_args = ['database_uri']
    takes_options = [
        Option('max-rows-per-query', type=int,
               help=('The max number of rows to fetch on each query. '
                     'Default is 10000.'))]

    def run(self, database_uri, max_rows_per_query=None):
        setConfig(setupConfig(None))
        setupLogging(self.outf)
        setupStore(database_uri, 'main')
        logging.info('Checking database:')
        if max_rows_per_query:
            checkIntegrity(max_rows_per_query)
        else:
            checkIntegrity()


class cmd_patch_database(Command):
    """Apply outstanding patches to a database.

    Unapplied patches will be run in the specified database.  If the database
    has perviously had patches applied that don't exist in the current schema
    the command will be aborted.  This can happen when code with an old schema
    is used with a database that has been patched by newer code.  The database
    URI must be compatible with Storm, for example::

      postgres://fluidinfo:fluidinfo@localhost/fluidinfo
    """

    takes_args = ['database_uri']

    def run(self, database_uri):
        setConfig(setupConfig(None))
        setupLogging(self.outf)
        store = setupStore(database_uri, 'main')
        schema = main.createSchema()
        status = getPatchStatus(store, schema)
        if status.unknownPatches:
            unknownPatches = ', '.join(
                'patch_%d' % version for version in status.unknownPatches)
            logging.critical('Database has unknown patches: %s',
                             unknownPatches)
            return 1
        if status.unappliedPatches:
            unappliedPatches = ', '.join(
                'patch_%d' % version for version in status.unappliedPatches)
            logging.info('Applying patches: %s', unappliedPatches)
            patchDatabase(store, schema)
        else:
            logging.info('Database is up-to-date.')


class cmd_patch_status(Command):
    """Show information about a database.

    Information about unapplied and unknown patches is printed to the screen.
    The database URI must be compatible with Storm, for example::

      postgres://fluidinfo:fluidinfo@localhost/fluidinfo
    """

    takes_args = ['database_uri']

    def run(self, database_uri):
        setConfig(setupConfig(None))
        setupLogging(self.outf)
        store = setupStore(database_uri, 'main')
        schema = main.createSchema()
        status = getPatchStatus(store, schema)
        if status.unappliedPatches:
            patches = ', '.join('patch_%d' % version
                                for version in status.unappliedPatches)
            logging.info('Unapplied patches: %s' % patches)
            sys.exit(1)
        if status.unknownPatches:
            patches = ', '.join('patch_%d' % version
                                for version in status.unknownPatches)
            logging.info('Unknown patches: %s' % patches)
            sys.exit(2)
        if not status.unappliedPatches and not status.unknownPatches:
            logging.info('Database is up-to-date.')
            sys.exit(0)


class cmd_build_index(TwistedCommand):
    """Build an object index from a database.

    Documents in the object index are created from information in the
    database.  The database URI must be compatible with Storm, for example::

      postgres://fluidinfo:fluidinfo@localhost/fluidinfo

    The index URI should point to the HTTP API for an empty Solr index::

      http://localhost:8080/solr
    """

    takes_args = ['database_uri', 'index_uri']

    def run(self, database_uri, index_uri):
        setConfig(setupConfig(None))
        setupLogging(self.outf)
        setupStore(database_uri, 'main')
        return buildIndex(str(index_uri))


class cmd_batch_index(TwistedCommand):
    """Touches a list of objects adding them to the objects table.

    These objects will be later read by the Data Import Handler and will be
    indexed in Solr. This command takes the path of a file with a list of
    object IDs to touch, an interval in minutes for each batch of objects IDs
    to process and a number of documents per batch.
    """
    takes_args = ['database_uri', 'filename', 'interval', 'max_objects']

    def run(self, database_uri, filename, interval, max_objects):
        setConfig(setupConfig(None))
        setupLogging(self.outf)
        setupStore(database_uri, 'main')
        return batchIndex(filename, int(interval), int(max_objects))


class cmd_update_index(TwistedCommand):
    """Update an object index from a database.

    Documents in the object index are created from information in the
    database.  The database URI must be compatible with Storm, for example::

      postgres://fluidinfo:fluidinfo@localhost/fluidinfo

    The index URI should point to the HTTP API for an empty Solr index::

      http://localhost:8080/solr

    The date should be given in ISO format, for example::

      2011-06-12
    """

    takes_args = ['database_uri', 'index_uri', 'modified_since']

    def run(self, database_uri, index_uri, modified_since):
        setConfig(setupConfig(None))
        setupLogging(self.outf)
        setupStore(database_uri, 'main')
        modified_since = datetime.strptime(modified_since, '%Y-%m-%d')
        return updateIndex(str(index_uri), modified_since)


class cmd_delete_index(TwistedCommand):
    """Delete all documents in an object index.

    The index URI should point to the HTTP API for an empty Solr index::

      http://localhost:8080/solr
    """

    takes_args = ['index_uri']

    def run(self, index_uri):
        setConfig(setupConfig(None))
        setupLogging(self.outf)
        return deleteIndex(str(index_uri))


class cmd_clear_cache(Command):
    """Deletes all entries in the cache"""

    takes_options = [
        Option('db', type=int,
               help='The Redis DB number to clean.')]

    def run(self, db=None):
        if db is None:
            db = 0
        config = setupConfig(None)
        config.set('cache', 'db', db)
        setConfig(config)
        setupCache(config)
        redisClient = getCacheClient()
        redisClient.flushdb()


class cmd_authorize_sshid(Command):
    """Add an SSH id to a users's authorized_keys
    """

    takes_args = ['host']
    takes_options = [
        Option('username', type=str,
               help='The username whos authorized_keys will be appended to. '
                    'Default is $USER'),
        Option('ssh-id', type=str,
               help='The path to the SSH id to use. Default is '
                    '~/.ssh/id_rsa.pub')]

    def run(self, host, username=None, ssh_id=None):
        username = username or os.environ['USER']
        ssh_id = ssh_id or os.path.expanduser('~/.ssh/id_rsa.pub')
        if not os.access(ssh_id, os.R_OK):
            raise IOError("Can't read ssh-id %r - please check or specify an "
                          " alternative via --ssh-id." % ssh_id)
        with settings(host_string=host):
            authorizeSshKey(username, ssh_id)


class cmd_add_admin(Command):
    """Add a user with administrator privileges to an Ubuntu server.

    The new user is created with a disabled and expired password.  The first
    time the user connects to the server, using the provided SSH public key,
    the user will be asked to set a password.

    The typical way to use this command is as follows::

        export EC2_PRIVATE_KEY=$HOME/amazon/pk-<stuff>.pem
        export EC2_CERT=$HOME/amazon/cert-<stuff>.pem
        export AWS_ACCESS_KEY_ID=<access-key-id>
        export AWS_SECRET_ACCESS_KEY=<secret-access-key>
        export AWS_ENDPOINT=https://ec2.us-east-1.amazonaws.com
        export EC2_KEYPAIR_PATH=gsg-keypair
        export EC2_KEYPAIR_PATH=$HOME/amazon/id_rsa-gsg-keypair
        bin/fluidinfo add-admin $REMOTE_HOST

    This will add a user to $REMOTE_HOST with the same name as your local
    user.  You'll need to SSH to the host to set a local password for sudo
    access.  Once that's done your account is ready to use.
    """

    takes_args = ['host']
    takes_options = [
        Option('username', type=str,
               help='The username to use for the new user.  Default is $USER'),
        Option('ssh-id', type=str,
               help='The path to the SSH id to use. Default is '
               '~/.ssh/id_rsa.pub'),
        Option('user', short_name='u', type=str,
               help="The user to connect as.  Default is 'ubuntu'."),
        Option('identity', short_name='i', type=str,
               help='The identity file to use when connecting to the host.')]
    _see_also = ['deploy']

    def run(self, host, username=None, ssh_id=None, user=None,
            identity=None):
        username = username or os.environ['USER']
        ssh_id = ssh_id or os.path.expanduser('~/.ssh/id_rsa.pub')
        user = user or 'ubuntu'
        identity = identity or os.environ['EC2_KEYPAIR_PATH']
        try:
            with settings(host_string=host):
                addAdmin(username, ssh_id, user, identity)
        finally:
            for key in connections.keys():
                connections[key].close()
                del connections[key]


class cmd_prepare_instance(Command):
    """Prepare an instance updating the packages and creating a new user.

    This command will ask you for a password for the new user. Use it for sudo
    operations.

    Example usage::
        bin/fluidinfo prepare-instance $REMOTE_HOST
    """

    takes_args = ['host']
    takes_options = [
        Option('username', type=str,
               help='The username to use for the new user.  Default is $USER'),
        Option('ssh-id', type=str,
               help='The path to the SSH id to use. Default is '
                    '~/.ssh/id_rsa.pub')]
    _see_also = ['deploy']

    def run(self, host, username=None, ssh_id=None):
        username = username or os.environ['USER']
        ssh_id = (ssh_id or os.path.expanduser('~/.ssh/id_rsa.pub'))
        if not os.access(ssh_id, os.R_OK):
            raise IOError("Can't read ssh-id %r - please check or specify an "
                          "alternative via --ssh-id." % ssh_id)
        with settings(host_string=host):
            prepareInstance(username, ssh_id)


class cmd_create_disk(Command):
    """
    Create a new disk for storage using a RAID array or a single ebs volume.

    Example usage::
        bin/fluidinfo create-disk \\
            --instance-id i-bf948fce \\
            --device-prefix /dev/sdn \\
            --raid-device /dev/md6 \\
            --num-volumes 4 \\
            --volume-size 70 \\
            --mount-path /var/lib/fluidinfo/test \\
            --name-prefix test-instance
    """

    takes_options = [
        Option('instance-id', type=str,
               help='The AWS instance ID to create the disk on.'),
        Option('device-prefix', type=str,
               help='The prefix used for devices for volumes.'),
        Option('raid-device', type=str,
               help='If the disk is going to be a RAID array, specify the'
                    'device to use for the RAID.'),
        Option('num-volumes', type=int,
               help="The number of EBS volumes to create."),
        Option('volume-size', type=int,
               help="The size in GiB for each volume."),
        Option('mount-path', type=str,
               help="The path where the new disk is going to be mounted.."),
        Option('name-prefix', type=str,
               help="A name prefix for each volume."),
    ]

    _see_also = ['deploy']

    def run(self, instance_id=None, device_prefix=None, raid_device=None,
            num_volumes=None, volume_size=None, mount_path=None,
            name_prefix=None):
        createDisk(instance_id, device_prefix, raid_device, num_volumes,
                   volume_size, mount_path, name_prefix)


class cmd_bootstrap_postgres(Command):
    """
    Bootstraps a Postgres sever for Fluidinfo.

    This installs dependencies and setup the necessary configuration files.

    This only bootstraps Postgres. FluidDB, Solr and other services require
    other commands.

    Example usage::
        bin/fluidinfo bootstrap-postgres \\
            --server-name test.example.com \\
            $REMOTE_HOST
    """

    takes_options = [
        Option('server-name', type=str,
               help="The name of the whole Fluidinfo deployment."),
    ]
    takes_args = ['host']
    _see_also = ['deploy']

    def run(self, host, server_name=None):
        if server_name is None:
            server_name = host

        with settings(host_string=host):
            bootstrapPostgres(server_name,
                              os.environ['AWS_ACCESS_KEY_ID'],
                              os.environ['AWS_SECRET_ACCESS_KEY'])


class cmd_bootstrap_solr(Command):
    """
    Bootstraps a Solr sever for Fluidinfo.

    This installs dependencies and setup the necessary configuration files.

    This only bootstraps Solr. FluidDB, Postgres and other services require
    other commands.

    Example usage::
        bin/fluidinfo bootstrap-solr \\
            --server-name test.example.com \\
            --postgres-uri postgresql://test-pg.example.com:5432 \\
            $REMOTE_HOST
    """

    takes_options = [
        Option('server-name', type=str,
               help="The name of the whole Fluidinfo deployment."),
        Option('postgres-uri', type=str,
               help='The URI of the postgres server, by default '
                    'postgresql://localhost:5432/fluidinfo is used'),
        Option('num-shards', type=int,
               help='Number of shards that will be used for solr.'),
        Option('shard-id', type=int,
               help='The number of this particular shard.'),
    ]
    takes_args = ['host']
    _see_also = ['deploy']

    def run(self, host, server_name, postgres_uri=None, num_shards=None,
            shard_id=None):
        if server_name is None:
            server_name = host

        if postgres_uri is None:
            postgres_uri = 'postgresql://localhost:5432/fluidinfo'

        if (num_shards is None and shard_id is not None
                or shard_id is None and num_shards is not None):
            raise AttributeError('You must specify both num-shards and '
                                 'shard-id')

        if num_shards is None:
            num_shards = 1
            shard_id = 0

        assert shard_id < num_shards
        assert all(option is not None for option in
                   [postgres_uri, num_shards, shard_id])

        with settings(host_string=host):
            bootstrapSolr(server_name, postgres_uri, num_shards, shard_id)


class cmd_bootstrap_redis(Command):
    """
    Bootstraps a Redis sever for Fluidinfo.

    This installs dependencies and setup the necessary configuration files.

    This only bootstraps Redis. FluidDB, Postgres and other services require
    other commands.

    Example usage::
        bin/fluidinfo \\
            --server-name test.example.com \\
            bootstrap-redis $REMOTE_HOST
    """

    takes_args = ['host']
    takes_options = [
        Option('server-name', type=str,
               help="The name of the whole Fluidinfo deployment."),
    ]
    _see_also = ['deploy']

    def run(self, host, server_name):
        if server_name is None:
            server_name = host

        with settings(host_string=host):
            bootstrapRedis(server_name)


class cmd_bootstrap_frontend(Command):
    """
    Bootstraps the web server and proxy to work with FluidDB.

    This installs dependencies and setup the necessary configuration files.

    Example usage::
        bin/fluidinfo bootstrap-frontend \\
            --server-name test.example.com \\
            --public-ssl-cert-path ~/fluidinfo/ssl/fluidinfo.pem \\
            --private-ssl-cert-path ~/fluidinfo/ssl/fluidinfo.key \\
            $REMOTE_HOST
    """

    takes_args = ['host']
    takes_options = [
        Option('server-name', type=str,
               help="The name of the whole Fluidinfo deployment."),
        Option('server-port', type=int,
               help="The port for the Fluidinfo instance. Default is 80."),
        Option('public-ssl-cert-path', type=str,
               help='The filename of the public SSL certificate, such as '
                    'fluidinfo.pem.'),
        Option('private-ssl-cert-path', type=str,
               help='The filename of the private SSL certificate, such as '
                    'fluidinfo.key.'),
    ]
    _see_also = ['deploy']

    def run(self, host, server_name=None, server_port=80,
            public_ssl_cert_path=None, private_ssl_cert_path=None):
        if server_name is None:
            server_name = host
        with settings(host_string=host):
            bootstrapFrontend(server_name, server_port, public_ssl_cert_path,
                              private_ssl_cert_path)


class cmd_bootstrap_fluiddb(Command):
    """
    Bootstraps a FluidDB deployment.

    This installs dependencies, uploads the fluiddb source code and setup the
    necessary configuration files.

    This only bootstraps FluidDB. Postgres, Solr and other services require
    other commands.

    Example usage::
        bin/fluidinfo bootstrap-fluiddb \\
            --server-name test.example.com \\
            --postgres-uri \\
                postgres://fluidinfo:fluidinfo@$REMOTE_HOST:5432/fluidinfo \\
            --solr-url http://solr05.example.com:8080/solr/ \\
            --solr-shards  \\
            --create-schema true \\
            $REMOTE_HOST
    """

    takes_args = ['host']
    takes_options = [
        Option('server-name', type=str,
               help="The name of the whole Fluidinfo deployment."),
        Option('postgres-uri', type=str,
               help='The URI of the postgres server, by default '
                    'postgres://fluidinfo:fluidinfo@localhost/fluidinfo is '
                    'used'),
        Option('solr-url', type=str,
               help='The URL of the solr server, by default '
                    'http://localhost:8080/solr/ is used'),
        Option('solr-shards', type=str,
               help='All the solr shards, by default only the one in solr-url '
                    'is used'),
        Option('create-schema', type=bool,
               help='Reset the database and create the schema from scratch'),
        Option('solr-import', type=bool,
               help='Run a full import on solr.'),
    ]
    _see_also = ['deploy']

    def run(self, host, server_name=None, postgres_uri=None,
            solr_url=None, solr_shards=None, create_schema=None,
            solr_import=None):

        if server_name is None:
            server_name = host
        if postgres_uri is None:
            postgres_uri = 'postgres://fluidinfo:fluidinfo@localhost/fluidinfo'
        if solr_url is None:
            solr_url = 'http://localhost:8080/solr'
        if solr_shards is None:
            solr_shards = solr_url.replace('https://', '')
            solr_shards = solr_shards.replace('http://', '')
        if create_schema is None:
            if not confirm("You didn't set the --create-schema option. "
                           "The database won't be bootstrapped.\n"
                           'Continue anyway?'.format(postgres_uri)):
                return

        if solr_import is None:
            if not confirm("You didn't set the --solr-import option. "
                           "The solr index won't be imported for the first"
                           'time.\nContinue anyway?'):
                return

        with settings(host_string=host):
            bootstrapFluidDB(server_name, postgres_uri, solr_url, solr_shards,
                             createSchema=create_schema,
                             solrImport=solr_import)


class cmd_update_fluiddb(Command):
    """
    Updates a FluidDB deployment.

    This uploads the fluiddb source code and setup the necessary configuration
    files.

    This only updates FluidDB. Postgres, Solr and other services require
    other commands.

    Example usage::
        bin/fluidinfo update-fluiddb $REMOTE_HOST
    """

    takes_args = ['host']
    takes_options = [
        Option('server-name', type=str,
               help="The name of the whole Fluidinfo deployment."),
    ]
    _see_also = ['bootstrap-fluiddb']

    def run(self, host, server_name=None):

        if server_name is None:
            server_name = host

        branchName = local('git rev-parse --abbrev-ref HEAD', capture=True)

        if not re.search('deploy', branchName, re.IGNORECASE):
            if not confirm("Your current branch doesn't look like a deploy "
                           "branch. Continue anyway?"):
                return

        with settings(host_string=host):
            updateFluidDB(server_name)


class cmd_check_instance(Command):
    """Check and excercise the basic components of an instance.

    Usage::
        bin/fluidinfo check-instance \\
            --username fluiddb \\
            --password secret \\
            http[s]://$REMOTE_HOST[:port]
    """

    takes_args = ['host']
    takes_options = [
        Option('username', type=str,
               help="The username to use in the requests"),
        Option('password', type=str,
               help="The username to use in the requests"),
    ]
    _see_also = ['deploy']

    def run(self, host, username=None, password=None):
        if username is None:
            username = u'fluiddb'
        if password is None:
            password = u'secret'
        if host.find('://') == -1:
            host = 'http://' + host
        print 'Logging to', host
        fluiddb = Fluid(host)
        fluiddb.login(username, password)

        print 'Creating an object...',
        try:
            result = fluiddb.objects.post(u'test-object')
            objectID = result.value[u'id']
            assert result.status == 201
        except:
            print >>sys.stderr, 'FAILED'
            print_exc()
        else:
            print 'OK'

        tagname = 'test' + str(datetime.now().toordinal())

        print 'Creating a tag...',
        try:
            result = fluiddb.tags[username].post(tagname, None, True)
            assert result.status == 201
        except:
            print >>sys.stderr, 'FAILED'
            print_exc()
        else:
            print 'OK'

        print 'Creating a tag value...',
        try:
            path = '{0}/{1}'.format(username, tagname)
            result = fluiddb.about['test-object'][path].put(200)
            assert result.status == 204
        except:
            print >>sys.stderr, 'FAILED'
            print_exc()
        else:
            print 'OK'

        print 'Giving time to the DIH (2 minutes)...'
        time.sleep(120)

        print 'Making a solr query...',
        try:
            path = '{0}/{1}'.format(username, tagname)
            result = fluiddb.objects.get('{0} = 200'.format(path))
            print result.value[u'ids']
            assert result.value[u'ids'] == [objectID]
        except:
            print >>sys.stderr, 'FAILED'
            print_exc()
        else:
            print 'OK'

        print 'Removing a tag value...',
        try:
            path = '{0}/{1}'.format(username, tagname)
            result = fluiddb.about['test-object'][path].delete()
            assert result.status == 204
        except:
            print >>sys.stderr, 'FAILED'
            print_exc()
        else:
            print 'OK'

        print 'Removing a tag...',
        try:
            path = '{0}/{1}'.format(username, tagname)
            result = fluiddb.tags[path].delete()
            assert result.status == 204
        except:
            print >>sys.stderr, 'FAILED'
            print_exc()
        else:
            print 'OK'


class cmd_deploy(Command):
    """Deploy Fluidinfo on an Ubuntu server.

    The current branch is exported, copied to and configured on the remote
    host.  The branch is configured on the remote host using Virtualenv.

    The name of the remote host is used as the server name, by default.  Code
    bundles are stored in a /srv/<server-name> directory.  When deploying to
    an instance that will eventually have its name changed to something else,
    you must pass an explicit server name to ensure that the transition will be
    smooth.
    """

    takes_args = ['host']
    takes_options = [
        Option('server-name', type=str,
               help="The server name to use when deploying Fluidinfo."),
        Option('no-tests', help="Don't run the Fluidinfo test suite."),
        Option('no-patches', help="Don't apply DB patches automatically.")]

    def run(self, host, server_name=None, no_tests=None, no_patches=None):

        if server_name is None:
            server_name = host

        deploymentPath = os.path.join('/srv', server_name)
        with settings(host_string=host):
            ping()
            revision = prepareFluidinfo(not no_tests)
            deployFluidinfo(deploymentPath, revision)
            needsPatching = hasUnappliedDatabasePatches(deploymentPath,
                                                        revision)
            if needsPatching:
                stopFluidinfo()
                switchRevision(deploymentPath, revision)
                clearRedisCache(deploymentPath, revision)

                if no_patches is None:
                    applyDatabasePatches(deploymentPath, revision)
                    startFluidinfo()
                else:
                    print >> self.outf
                    print >> self.outf
                    print >> self.outf, '*** MANUAL FLUIDDB START REQUIRED ***'
                    print >> self.outf
                    print >> self.outf
            else:
                switchRevision(deploymentPath, revision)
                clearRedisCache(deploymentPath, revision)
                updateVersionTag(deploymentPath, revision)
                restartFluidinfo()


class cmd_load_test_server(Command):
    """Create a large volume of data to test a deployment."""

    takes_args = ['username', 'password', 'host']
    takes_options = [
        Option('max-connections', short_name='c', type=int,
               help='The maximum number of concurrent connections to open to '
                    'the server.  Default is 16.'),
        Option('no-tests', help="Don't run the Fluidinfo test suite."),
        Option('no-start', help="Don't start the Fluidinfo API service.")]

    def run(self, username, password, host, max_connections=None):
        setupLogging(self.outf)
        if max_connections is None:
            max_connections = 16
        endpoint = 'http://%s' % host
        generateLoad(username, password, endpoint, max_connections)


class cmd_pull_logs(Command):
    """Pull the API service logs from a Fluidinfo instance.

    Logs files are copied from the current code bundle on the specified HOST
    and copied to the local directory LOCAL_PATH.
    """

    takes_args = ['host', 'local_path?']
    takes_options = [
        Option('server-name', type=str,
               help='The server name used in the Fluidinfo deployment.  '
                    'Default is the host name.')]

    def run(self, host, local_path=None, server_name=None):
        if server_name is None:
            server_name = host
        if local_path is None:
            local_path = os.getcwd()
        if not os.path.exists(local_path):
            os.makedirs(local_path)
        logPath = os.path.join('/srv', server_name, 'current/var/log')
        remotePath = '%s:%s/fluidinfo-api*' % (host, logPath)
        local('rsync -e ssh -zahP --delete %s %s' % (remotePath, local_path),
              capture=False)


class cmd_load_logs(Command):
    """Load logs generated by API services for further analysis."""

    takes_args = ['path', 'database_uri']

    def run(self, path, database_uri):
        setupLogging(self.outf)
        store = setupStore(database_uri, 'logs')
        schema = logs.createSchema()
        logging.info('Creating schema')
        patchDatabase(store, schema)
        logging.info('Loading log file %s', path)
        loadLogs(path, store)
        logging.info('Finished loading log file %s', path)


class cmd_load_trace_logs(Command):
    """Load trace logs generated by API services for further analysis."""

    takes_args = ['path', 'database_uri']

    takes_options = [
        Option('old-format',
               help='Indicates if the file uses the old multilined format.')]

    def run(self, path, database_uri, old_format=None):
        setupLogging(self.outf)
        store = setupStore(database_uri, 'logs')
        schema = logs.createSchema()
        logging.info('Creating schema')
        patchDatabase(store, schema)
        logging.info('Loading trace logs from %s', path)
        loadTraceLogs(path, store, old_format)
        logging.info('Finished loading trace logs from %s', path)


class cmd_report_error_summary(Command):
    """Generate a summary report about log errors."""

    takes_args = ['database_uri']

    def run(self, database_uri):
        setupLogging(self.outf)
        store = setupStore(database_uri, 'logs')
        rows = reportErrorSummary(store)
        print_columns(self.outf, rows, shrink_index=2)
        print >> self.outf
        print '%s occurrences of %s errors' % (
            sum(int(item[0]) for item in rows), len(rows))


class cmd_report_error_tracebacks(Command):
    """Generate a report about log errors with tracebacks."""

    takes_args = ['database_uri']

    def run(self, database_uri):
        setupLogging(self.outf)
        store = setupStore(database_uri, 'logs')
        rows = list(reportErrorTracebacks(store))
        for count, exceptionClass, message, traceback in rows:
            if count > 1:
                print >> self.outf, '%s occurrences of %s: %s' % (
                    count, exceptionClass, message)
            else:
                print >> self.outf, '%s occurrence of %s: %s' % (
                    count, exceptionClass, message)
            print >> self.outf
            for line in traceback.splitlines():
                print >> self.outf, '   ', line
            print >> self.outf
            print >> self.outf
        print >> self.outf, '%s occurrences of %s errors' % (
            sum(item[0] for item in rows), len(rows))


class cmd_report_trace_log_summary(Command):
    """Generate a summary report about trace logs."""

    takes_args = ['database_uri']
    takes_options = [
        Option('limit', type=int,
               help='The number of trace logs to display.  Default is 15.')]

    def run(self, database_uri, limit=None):
        if limit is None:
            limit = 15
        setupLogging(self.outf)
        store = setupStore(database_uri, 'logs')
        rows = list(reportTraceLogSummary(store, limit))
        print_columns(self.outf, rows)
        print >> self.outf
        print 'Top %s slowest requests' % limit


class cmd_build_api_docs(Command):
    """Build the API documentation."""

    takes_args = ['template_path', 'output_path']

    def run(self, template_path, output_path):
        buildAPIDocumentation(template_path, output_path)


class cmd_import_dataset(Command):
    """Import a dataset directly into the database.

    The specified dataset is imported directly into the data without updating
    Solr.  The data import handler must be run when the import completes, to
    update the index in an efficient way.
    """

    takes_args = ['path*']
    takes_options = [
        Option('username', short_name='u', type=unicode,
               help='The name of the user to use to import data.'),
        Option('database-uri', type=str,
               help='The database URI.  Default is postgres:///fluidinfo.'),
        Option('batch-size', type=int,
               help='The batch size.  Default is 100.')]

    def run(self, path_list, username=None, database_uri=None,
            batch_size=None):
        if database_uri is None:
            database_uri = 'postgres:///fluidinfo'
        if batch_size is None:
            batch_size = 100
        if username is None:
            print >> self.outf, 'You must provide a username.'
            sys.exit(1)

        setConfig(setupConfig(None))
        setupLogging(self.outf)
        setupStore(database_uri, 'main')

        client = DatasetImporter(batch_size)
        for filename in path_list:
            with open(filename, 'r') as file:
                data = load(file)
                client.upload(username, data['objects'])


class cmd_delete_comment(Command):
    """Delete a comment, given its URL.

    Comment URLs look like:
    http://loveme.do/comment/fluidinfo.com/username/2012-08-03T22:04:13.698896.
    These can be obtained by clicking the small importer icon at the top
    right of each comment shown for an object in loveme.do.
    """

    takes_args = ['comment_url']
    takes_options = [
        Option('database-uri', type=str,
               help='The database URI.  Default is postgres:///fluidinfo.')]

    def _error(self, message):
        """Print an error message and exit.

        @param message: The C{str} error message to print.
        """
        print >> self.outf, message
        transaction.abort()
        sys.exit(1)

    def run(self, comment_url, database_uri=None):
        """Delete a comment, given its loveme.do URL.

        @param comment_url: A loveme.do comment URL, in the form
            http://loveme.do/comment/fluidinfo.com/terrycojones/
            2012-08-03T22:04:13.698896
        """
        database_uri = database_uri or 'postgres:///fluidinfo'
        setConfig(setupConfig(None))
        setupLogging(self.outf)
        setupStore(database_uri, 'main')

        try:
            importer, username, timestamp = parseCommentURL(comment_url)
        except ValueError as error:
            self._error(str(error))

        # Delete the comment & report status.
        count = CommentAPI(None).delete(importer, username, timestamp)

        if count == 0:
            self._error('Comment not found.')
        elif count == 1:
            transaction.commit()
            print >> self.outf, 'Comment deleted.'
            sys.exit(0)
        else:
            self._error('Unexpected return result (%r) trying to delete '
                        'comment.' % count)
