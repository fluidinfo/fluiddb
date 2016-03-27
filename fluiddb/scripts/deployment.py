from ConfigParser import RawConfigParser
from datetime import datetime
from getpass import getpass
import logging
import os
import time
import random
import crypt

from boto.ec2.connection import EC2Connection
from boto.exception import EC2ResponseError
from fabric.context_managers import cd, settings
from fabric.contrib.files import sed, exists
from fabric.operations import local, put, sudo, run, reboot, get
from fabric.state import env
from string import ascii_letters, digits


def _hashPassword(password):
    """Return {password} hashed with a random salt."""
    charset = './' + ascii_letters + digits
    return crypt.crypt(password, ''.join(random.sample(charset, 2)))


def createDisk(instanceID, devicePrefix, raidDevice, numVolumes, volumeSize,
               mountPath, namePrefix):
    """Create a new disk for storage using a RAID array or a single EBS volume.

    @param instanceID: The AWS instance ID to create the disk on.
        e.g. 'i-bf948fce'
    @param devicePrefix: The prefix used for devices for volumes.
        e.g. '/dev/sdn1'.
    @param raidDevice: If the disk is going to be a RAID array, specify the
        device to use for the RAID.
        e.g '/dev/md6'
    @param numVolumes: The number of EBS volumes to create.
        More than 1 will create a RAID array.
    @param volumeSize: The size in GiB for each volume.
    @param mountPath: The path where the new disk is going to be mounted.
        e.g '/var/lib/fluidinfo/test'
    @param: owner: The user who will be the owner of the mounted disk.
        e.g. 'fluidinfo'
    """
    assert numVolumes > 0
    assert 0 < volumeSize < 1000
    if numVolumes > 1:
        assert raidDevice is not None

    print 'Getting instance information.'
    ec2 = EC2Connection()
    instance = ec2.get_all_instances([instanceID])[0].instances[0]
    zone = instance.placement

    volumes = []
    for i in range(numVolumes):
        device = devicePrefix + str(i + 1)
        print 'Creating volume for', device
        volume = ec2.create_volume(volumeSize, zone)
        volume.attach(instanceID, device)
        volumes.append(volume)
        if namePrefix is not None:
            volume.add_tag(
                'Name', '{0} ({1})'.format(namePrefix, device.split('/')[-1]))

    pendingVolumes = set(volumes)
    while pendingVolumes:
        print 'Attaching volumes.', len(pendingVolumes), 'remaining.'
        time.sleep(1)
        for volume in list(pendingVolumes):
            try:
                volume.update()
            except EC2ResponseError:
                print 'Response error.'
                print "Don't panic, this usually happens, trying again."
            if volume.attachment_state() == u'attached':
                pendingVolumes.remove(volume)

    print 'All volumes attached: ', ''.join(volume.id for volume in volumes)

    env.host_string = instance.dns_name

    if len(volumes) > 1:
        sudo('DEBIAN_FRONTEND=noninteractive apt-get install -y mdadm')
        print 'Creating RAID array.'
        devices = [volume.attach_data.device.replace('/dev/sd', '/dev/xvd')
                   for volume in volumes]
        devices = ' '.join(devices)
        sudo('mdadm --create {0} --level raid10 --auto=yes --assume-clean '
             '--raid-devices {1} {2}'.format(raidDevice, numVolumes, devices))
        sudo('echo DEVICE {0} >> /etc/mdadm/mdadm.conf'.format(devices))
        sudo('mdadm --detail --scan | grep {0} | '
             'sudo tee -a /etc/mdadm/mdadm.conf'.format(raidDevice))

        # Tell the kernel to use the specified configurationg, otherwise it
        # will use something like /dev/md127
        sudo('update-initramfs -u')

        device = raidDevice
    else:
        device = volumes[0].attach_data.device.replace('/dev/sd', '/dev/xvd')

    print 'Formating device.'
    sudo('mkfs.ext4 {0}'.format(device))
    sudo('echo "{0} {1} ext4 noatime 0 0" >> /etc/fstab'.format(device,
                                                                mountPath))

    print 'Mounting device.'
    sudo('mkdir -p {0}'.format(mountPath))
    sudo('mount %s' % mountPath)
    print 'Success.'


def bootstrapFluidDB(serverName, databaseURI, solrURL, solrShards,
                     createSchema=None, solrImport=None):
    """Bootstraps a fluidDB deployment.

    This installs dependencies, uploads the fluiddb source code and sets up
    the necessary configuration files.

    This only bootstraps FluidDB. Postgres, Solr and other services require
    other commands.

    """
    # Install requirements

    sudo('DEBIAN_FRONTEND=noninteractive apt-get install -y '
         'bzr git postgresql-server-dev-9.1 python-dev python-pip '
         'python-virtualenv make logrotate openntpd')

    # Create a 'fluidinfo' user
    sudo('sudo adduser --system --home /var/lib/fluidinfo '
         '             --gecos "Fluidinfo,,," --disabled-password '
         '             --shell /bin/bash fluidinfo')
    sudo('chown -R fluidinfo /var/lib/fluidinfo')

    # Upload and set up the code.
    deploymentPath = os.path.join('/srv', serverName)
    revision = datetime.utcnow().strftime('%Y%m%d-%H%M')
    revisionPath = os.path.join(deploymentPath, revision)

    sudo('mkdir -p {0}'.format(revisionPath))
    sudo('chown -R fluidinfo {0}'.format(deploymentPath))

    local('git archive --prefix=fluidinfo/ -v --format tar HEAD | '
          'bzip2 > fluidinfo.tar.bz2')
    put('fluidinfo.tar.bz2')
    sudo('cp fluidinfo.tar.bz2 {0}'.format(revisionPath))

    with cd(revisionPath):
        sudo('chown -R fluidinfo {0}'.format(revisionPath))
        sudo('chown fluidinfo fluidinfo.tar.bz2')
        sudo('tar jxvf fluidinfo.tar.bz2', user='fluidinfo')
        sudo('mkdir -p var/log var/log/trace var/run var/tmp',
             user='fluidinfo')

    with cd(os.path.join(revisionPath, 'fluidinfo')):
        sudo('virtualenv .', user='fluidinfo')
        sudo('mkdir -p /var/lib/fluidinfo/pip-cache', user='fluidinfo')
        sudo('./bin/pip install --use-mirrors '
             '--download-cache=/var/lib/fluidinfo/pip-cache '
             '--log /tmp/pip.log '
             '-r requirements.txt', user='fluidinfo')
        if createSchema:
            sudo('bin/python bin/fluidinfo '
                 '    bootstrap-database {0}'.format(databaseURI),
                 user='fluidinfo')
        # We use this to make sure that the database is properly configured.
        sudo('bin/python bin/fluidinfo '
             '    patch-status {0}'.format(databaseURI),
             user='fluidinfo')

        # Run full DIH on all solr shards.
        if solrImport:
            for shard in solrShards.split(','):
                run('curl http://{0}/dataimport?command=full-import&'
                    'clean=true&commit=true&optimize=false'.format(shard))

        # On successful completion, clean up /tmp
        sudo('rm -f /tmp/pip.log')

    # Copy and setup configuration files.
    deployConfigFiles(
        {'deployment-path': deploymentPath,
         'server-name': serverName,
         'revision-path': revisionPath,
         'solr-url': solrURL,
         'solr-shards': solrShards,
         'postgres-uri': databaseURI},

        ('fluidinfo/fluidinfo-api.conf.template',
            '{revision-path}/fluidinfo-api.conf'),

        ('logrotate/fluidinfo-api.template',
            '/etc/logrotate.d/fluidinfo-api'),

        ('upstart/fluidinfo-api.conf.template',
            '/etc/init/fluidinfo-api.conf'),

        ('upstart/fluidinfo-api-node.conf.template',
            '/etc/init/fluidinfo-api-node.conf'),

        ('ntpd/ntpd.conf',
            '/etc/openntpd/ntpd.conf'))

    with cd(deploymentPath):
        sudo('ln -fs {0} current'.format(revision))
    sudo('/etc/init.d/openntpd restart')
    sudo('start fluidinfo-api')


def updateFluidDB(serverName):
    """Update a FluidDB deployment.

    This installs dependencies, uploads the fluiddb source code and sets up
    the necessary configuration files.

    This only updates FluidDB. Postgres, Solr and other services require
    other commands.

    If the server is new, you should use L{bootstrapFluidDB} instead.

    """
    # Upload and set up the code.
    deploymentPath = os.path.join('/srv', serverName)
    revision = datetime.utcnow().strftime('%Y%m%d-%H%M')
    revisionPath = os.path.join(deploymentPath, revision)

    sudo('mkdir -p {0}'.format(revisionPath))

    local('git archive --prefix=fluidinfo/ -v --format tar HEAD | '
          'bzip2 > fluidinfo.tar.bz2')
    put('fluidinfo.tar.bz2', revisionPath, use_sudo=True)

    with cd(revisionPath):
        sudo('mkdir -p var/log var/log/trace var/run var/tmp')
        sudo('chown -R fluidinfo {0}'.format(revisionPath))
        sudo('tar jxvf fluidinfo.tar.bz2', user='fluidinfo')

    with cd(os.path.join(revisionPath, 'fluidinfo')):
        sudo('virtualenv .', user='fluidinfo')
        sudo('mkdir -p /var/lib/fluidinfo/pip-cache', user='fluidinfo')
        sudo('./bin/pip install --use-mirrors '
             '--download-cache=/var/lib/fluidinfo/pip-cache '
             '--log /tmp/pip.log '
             '-r requirements.txt', user='fluidinfo')
        # On successful completion, clean up /tmp
        sudo('rm -f /tmp/pip.log')

    get(os.path.join(deploymentPath, 'current', 'fluidinfo-api.conf'),
        'fluidinfo-api.conf')
    config = RawConfigParser()
    with open('fluidinfo-api.conf', 'r') as configFile:
        config.readfp(configFile)

    # Copy and set up configuration files.
    deployConfigFiles(
        {'deployment-path': deploymentPath,
         'server-name': serverName,
         'revision-path': revisionPath,
         'solr-url': config.get('index', 'url'),
         'solr-shards': config.get('index', 'shards'),
         'postgres-uri': config.get('store', 'main-uri')},

        ('fluidinfo/fluidinfo-api.conf.template',
            '{revision-path}/fluidinfo-api.conf'))

    local('rm fluidinfo-api.conf')

    # TODO: check patches.
    # TODO: update version tag.

    with cd(deploymentPath):
        sudo('rm current')
        sudo('ln -fs {0} current'.format(revision))

    for port in range(9001, 9009):
        sudo('restart fluidinfo-api-node PORT=%d' % port)


def bootstrapPostgres(serverName, awsAccessKey=None, awsSecretKey=None):
    """Bootstraps Postgres to work with FluidDB.

    This installs dependencies and sets up the necessary configuration files.

    This only bootstraps Postgres. FluidDB, Solr and other services require
    other commands.
    """
    # Install requirements
    sudo('DEBIAN_FRONTEND=noninteractive apt-get install -y '
         'postgresql-9.1')

    sudo('/etc/init.d/postgresql stop')

    sudo('mkdir -p /var/lib/postgresql/scripts')
    sudo('mkdir -p /var/lib/postgresql/backup')

    deploymentPath = os.path.join('/srv', serverName)
    deployConfigFiles(
        {'server-name': serverName,
         'aws-access-key': awsAccessKey,
         'aws-secret-key': awsSecretKey,
         'deployment-path': deploymentPath},

        ('postgres/postgresql.conf',
            '/etc/postgresql/9.1/main/postgresql.conf'),

        ('postgres/pg_hba.conf',
            '/etc/postgresql/9.1/main/pg_hba.conf'),

        ('postgres/backup.sh.template',
            '/var/lib/postgresql/scripts/backup.sh'),

        ('postgres/clean-dirty-objects.sh',
            '/var/lib/postgresql/scripts/clean-dirty-objects.sh'),

        ('postgres/crontab',
            '/var/lib/postgresql/scripts/crontab'),

        ('s3/boto.cfg.template', '/etc/boto.cfg'))

    sudo('chown -R postgres:postgres /var/lib/postgresql/scripts')
    sudo('chown -R postgres:postgres /var/lib/postgresql/backup')

    sudo('chmod +x /var/lib/postgresql/scripts/backup.sh')
    sudo('chmod +x /var/lib/postgresql/scripts/clean-dirty-objects.sh')
    sudo('crontab -u postgres /var/lib/postgresql/scripts/crontab')

    sudo('/etc/init.d/postgresql start')
    # Configure postgres
    sudo('createuser -D -R -S -w fluidinfo', user='postgres')
    sudo('createdb fluidinfo -O fluidinfo', user='postgres')
    sudo("""echo "ALTER ROLE fluidinfo WITH ENCRYPTED PASSWORD 'fluidinfo'" |
            psql fluidinfo""", user='postgres')


def bootstrapSolr(serverName, databaseURI, numShards, shardID):
    """Bootstraps Solr to work with FluidDB.

    This installs dependencies and sets up the necessary configuration files.

    This only bootstraps Solr. FluidDB, Postgres and other services require
    other commands.
    """
    # Install requirements
    sudo('DEBIAN_FRONTEND=noninteractive apt-get install -y '
         'ant junit4 libpg-java solr-common solr-tomcat tomcat6 '
         'openjdk-6-jdk libcommons-lang-java libvelocity-tools-java')

    location = "https://launchpad.net/~fluidinfo/+archive/fluiddb/+files/"
    packages = [
        'libnoggit-java_0.1-SNAPSHOT%2Bsvn1143083-1~ppa1~lucid2_all.deb',
        'solr-common_3.4.0-0~ppa3~lucid2_all.deb',
        'solr-tomcat_3.4.0-0~ppa3~lucid2_all.deb'
    ]

    for package in packages:
        sudo('curl -L {0} > /tmp/{1}'.format(location + package, package))
        sudo('dpkg -i /tmp/{0}'.format(package))
        sudo('rm -f /tmp/{0}'.format(package))

    # Upload and set up the code.
    local('tar -jcvf solr.tar.bz2 build.xml java')
    put('solr.tar.bz2')
    run('tar -jxvf solr.tar.bz2')
    run('ant jar')
    sudo('ln -fs /usr/share/java/postgresql.jar /usr/share/solr/WEB-INF/lib/')
    sudo('ln -fs /usr/share/java/noggit.jar /usr/share/solr/WEB-INF/lib/')

    deployConfigFiles(
        {'postgres-uri': databaseURI,
         'server-name': serverName,
         'num-shards': str(numShards),
         'shard-id': str(shardID)},

        ('solr/schema.xml', '/etc/solr/conf/schema.xml'),
        ('solr/solrconfig.xml', '/etc/solr/conf/solrconfig.xml'),
        ('solr/dataimport.properties', '/etc/solr/conf/dataimport.properties'),
        ('solr/data-config.xml.template', '/etc/solr/conf/data-config.xml'),
        ('solr/web.xml', '/etc/solr/web.xml'))

    sudo('chown tomcat6:tomcat6 /etc/solr/conf/dataimport.properties')
    sudo('cp dist/tagvaluetransformer.jar /usr/share/solr/WEB-INF/lib')
    sudo('/etc/init.d/tomcat6 restart')


def bootstrapRedis(serverName):
    """Bootstraps Redis to work with FluidDB.

    This installs dependencies and sets up the necessary configuration
    files.

    This only bootstraps Redis. FluidDB, Postgres and other services require
    other commands.

    """
    # Install requirements
    sudo('DEBIAN_FRONTEND=noninteractive apt-get install -y '
         'redis-server')

    deployConfigFiles(
        {'server-name': serverName},

        ('redis/redis.conf', '/etc/redis/redis.conf'))


def bootstrapFrontend(serverName, serverPort, sslPublicCertPath,
                      sslPrivateCertPath):
    """Bootstraps the web server and proxy to work with FluidDB.

    This installs dependencies and sets up the necessary configuration
    files.

    """
    # Upload files
    put(sslPublicCertPath, 'fluidinfo.pem')
    put(sslPrivateCertPath, 'fluidinfo.key')

    # Install requirements.
    sudo('DEBIAN_FRONTEND=noninteractive apt-get install -y nginx haproxy')

    # Set up haproxy.
    sudo('/etc/init.d/haproxy stop')
    deployConfigFiles(
        {'server-name': serverName},

        ('haproxy/haproxy.cfg', '/etc/haproxy/haproxy.cfg'),
        ('haproxy/haproxy-default', '/etc/default/haproxy'))

    sudo('mkdir -p ../var/run/haproxy')
    sudo('chown haproxy:haproxy ../var/run/haproxy')
    sudo('/etc/init.d/haproxy start')
    sudo('curl --silent http://127.0.0.1:9000 > /dev/null && echo Works!')

    # Set up nginx.
    sudo('/etc/init.d/nginx stop')
    sudo('mkdir -p /etc/nginx/ssl')
    sudo('mv fluidinfo.pem /etc/nginx/ssl')
    sudo('chmod 600 /etc/nginx/ssl/fluidinfo.pem')
    sudo('mkdir -p /var/lib/fluidinfo/logs')

    sudo('mv fluidinfo.key /etc/nginx/ssl')
    sudo('chmod 600 /etc/nginx/ssl/fluidinfo.key')
    deployConfigFiles(
        {'server-name': serverName},

        ('nginx/fluidinfo-secure.conf.template',
            '/etc/nginx/sites-available/{server-name}'))

    sudo('ln -sf /etc/nginx/sites-available/{0} '
         '/etc/nginx/sites-enabled/{0}'.format(serverName))
    sudo('rm -f /etc/nginx/sites-enabled/default')
    sudo('/etc/init.d/nginx start')
    time.sleep(1)
    sudo('curl --silent http://127.0.0.1:%d > /dev/null && echo Works!'
         % serverPort)


def deployConfigFiles(templateData, *files):
    """
    Deploy configuration files, filling template fields with real deployment
    data.

    @param templateData: A C{dict} with the data to fill the templates.
    @param *files: A list C{(source, destination)} with information about what
        files to copy
    """
    serverName = templateData['server-name']

    for origin, destination in files:
        specificFilename = os.path.join('deployment', serverName, origin)
        defaultFilename = os.path.join('deployment', 'default', origin)
        origin = (specificFilename
                  if os.path.exists(specificFilename)
                  else defaultFilename)
        destination = destination.format(**templateData)
        put(origin, destination, use_sudo=True)

        for key, value in templateData.iteritems():
            sed(destination, '\{\{ %s \}\}' % key, value.replace('.', r'\.'),
                use_sudo=True)


def authorizeSshKey(username, sshId):
    """Add specified SSH public key to the user's ~/.ssh/authorized_keys.
    If there is no such file, one will be created for the user.

    @param username: The name of the user whose authorized_keys is being
                     updated.
    @param sshId: Path to SSH public key (usually ~/.ssh/id_rsa.pub)
    """
    with settings(user='ubuntu',
                  key_filename=os.environ['EC2_KEYPAIR_PATH']):
        sshPath = os.path.join('~%s' % username, '.ssh')
        sudo('mkdir -p %s' % sshPath)
        sudo('chmod 700 %s' % sshPath)
        sudo('chown %s:%s %s' % (username, username, sshPath))
        authorizedKeysPath = os.path.join(sshPath, 'authorized_keys')
        pubKey = open(sshId, 'r').readline().strip()
        sudo("echo '%s' >> %s" % (pubKey, authorizedKeysPath))
        sudo('chmod 600 %s' % authorizedKeysPath)
        sudo('chown %s:%s %s' % (username, username, authorizedKeysPath))


def addAdmin(username, sshId, user, identity):
    """Add a user with admin privileges to an Ubuntu server.

    @param username: The name of the new user.
    @param sshId: Path to SSH public key (usually ~/.ssh/id_rsa.pub)
    @param user: Optionally, the user to connect as.
    @param identity: Optionally, the SSH identity to use when connecting.
    """
    if identity:
        env.key_filename = identity
    if user:
        env.user = user
    sudo('adduser --disabled-password --gecos ",,," %s' % username)
    sudo('usermod -p "" %s' % username)
    sudo('chage -d 0 %s' % username)
    sudo('gpasswd --add %s admin' % username)
    authorizeSshKey(username, sshId)


def prepareInstance(username, sshId):
    """Prepare an instance updating the packages and creating a new user.

    @param username: The name of the new user.
    @param sshId: Path to SSH public key (usually ~/.ssh/id_rsa.pub)
    """
    print os.environ['EC2_KEYPAIR_PATH']
    with settings(user='ubuntu',
                  key_filename=os.environ['EC2_KEYPAIR_PATH']):
        password = getpass('Enter a new password for user %s:' % username)
        password2 = getpass('Enter the password a again:')
        if password != password2:
            raise RuntimeError("Passwords don't match")
        sudo('adduser --disabled-password --gecos ",,," %s' % username)
        cryptedPassword = _hashPassword(password)
        sudo('usermod --password %s %s' % (cryptedPassword, username))
        sudo('gpasswd --add %s admin' % username)
        authorizeSshKey(username, sshId)
        sudo('apt-get update')
        sudo('DEBIAN_FRONTEND=noninteractive apt-get dist-upgrade -y')
        if exists('/var/run/reboot-required'):
            reboot()


def ping():
    """Ping the server."""
    sudo('pwd')


def prepareFluidinfo(runTests):
    """Prepare a Fluidinfo source tarball using the local branch.

    @param runTests: A flag to determine if the test suite should be run.
    @return: The name of the revision being deployed as a string matching the
        format, C{<date>-<time>}.
    """
    if runTests:
        local('make build-clean build', capture=False)
        local('make check-all', capture=False)

    local('git archive --prefix=fluidinfo/ -v --format tar HEAD | '
          'bzip2 > fluidinfo.tar.bz2')
    return datetime.utcnow().strftime('%Y%m%d-%H%M')


def installDevelopmentPackageDependencies():
    """Install package dependencies needed to compile C extensions."""
    sudo('DEBIAN_FRONTEND=noninteractive '
         'apt-get install -y gcc python-all-dev')


def uninstallDevelopmentPackageDependencies():
    """Uninstall package dependencies needed to compile C extensions."""
    sudo('DEBIAN_FRONTEND=noninteractive '
         'apt-get remove -y --purge gcc python-all-dev')
    sudo('DEBIAN_FRONTEND=noninteractive '
         'apt-get autoremove -y')


def stopStorageServices():
    """Stop PostgreSQL and Solr services."""
    sudo('/etc/init.d/tomcat6 stop')
    sudo('/etc/init.d/postgresql-8.4 stop')


def startStorageServices():
    """Start PostgreSQL and Solr services."""
    sudo('/etc/init.d/tomcat6 start')
    sudo('/etc/init.d/postgresql-8.4 start')


def deployFluidinfo(deploymentPath, revision):
    """Deploy Fluidinfo source code to the remote server.

    @param deploymentPath: The path to deploy Fluidinfo in.
    @param revision: The C{str} revision of the branch being deployed.
    """
    homePath = os.path.join('/home', env.user)
    revisionPath = os.path.join(deploymentPath, revision)
    sudo('mkdir -p %s' % revisionPath)
    put('fluidinfo.tar.bz2', homePath)
    filePath = os.path.join(homePath, 'fluidinfo.tar.bz2')
    sudo('cp %s %s' % (filePath, revisionPath))

    with cd(revisionPath):
        sudo('chown -R fluidinfo %s' % revisionPath)
        sudo('chown fluidinfo fluidinfo.tar.bz2')
        sudo('tar jxvf fluidinfo.tar.bz2', user='fluidinfo')
        sudo('mkdir -p var/log var/log/trace var/run var/tmp',
             user='fluidinfo')

    with cd(os.path.join(revisionPath, 'fluidinfo')):
        sudo('virtualenv .', user='fluidinfo')
        sudo('./bin/pip install --use-mirrors '
             '--download-cache=/var/lib/fluidinfo/source-dependencies '
             '-r requirements.txt', user='fluidinfo')

    ## Copy configuration files

    serverName = os.path.basename(deploymentPath)
    templateData = {'deployment-path': deploymentPath,
                    'server-name': serverName}
    fileCopies = [
        ('fluidinfo/fluidinfo-api.conf.template', '../fluidinfo-api.conf'),
        ('cron/postgres-crontab.template', '../scripts/postgres-crontab'),
        ('cron/fluidinfo-crontab.template', '../scripts/fluidinfo-crontab'),

        ('cron/backup-postgresql.sh.template',
            '../scripts/backup-postgresql.sh'),

        ('cron/metrics.sh', '../scripts/metrics.sh'),
        ('cron/time-fluidinfo.py', '../scripts/time-fluidinfo.py'),
        ('cron/solr-optimize.sh', '../scripts/solr-optimize.sh')

        # TODO: Copy configuration files for nginx, haproxy, logrotate and
        # upstart, these require service restarts if files have changed.
    ]

    with cd(os.path.join(revisionPath, 'fluidinfo')):
        sudo('mkdir ../scripts')

        for origin, destination in fileCopies:
            specificFilename = os.path.join('deployment', serverName, origin)
            defaultFilename = os.path.join('deployment', 'default', origin)
            origin = (specificFilename
                      if os.path.exists(specificFilename)
                      else defaultFilename)

            sudo('cp {origin} {destination}'.format(**locals()))

            for key, value in templateData.iteritems():
                value = value.replace('.', r'\.').replace('/', '\/')
                expression = r's/{{ %s }}/%s/g' % (key, value)
                sudo("sed -i -e '%s' %s" % (expression, destination))

        sudo('chmod +x ../scripts/backup-postgresql.sh')
        sudo('crontab -u postgres ../scripts/postgres-crontab')
        sudo('crontab -u fluidinfo ../scripts/fluidinfo-crontab')


def switchRevision(deploymentPath, revision):
    """Set the Fluidinfo deployment to a particular revision."""
    with cd(deploymentPath):
        sudo('rm -f current')
        sudo('ln -s %s current' % revision)


def startFluidinfo():
    """Start the pool of Fluidinfo API services."""
    sudo('start fluidinfo-api')
    sudo('/etc/init.d/haproxy start')
    sudo('/etc/init.d/nginx start')


def stopFluidinfo():
    """Stop the pool of Fluidinfo API services."""
    for port in range(9001, 9009):
        sudo('stop fluidinfo-api-node PORT=%d || true' % port)
    sudo('/etc/init.d/nginx stop')
    sudo('/etc/init.d/haproxy stop')


def restartFluidinfo():
    """Restart the pool of Fluidinfo API services without downtime.

    Also send a SIGUSR1 to Nginx to make it reopen log files (in the new code
    bundle directory).
    """
    for port in range(9001, 9009):
        sudo('stop fluidinfo-api-node PORT=%d || true' % port)
        sudo('start fluidinfo-api-node PORT=%d' % port)
    with settings(warn_only=True):
        sudo('kill -USR1 $(cat /var/run/nginx.pid)')


def updateVersionTag(deploymentPath, revision):
    """Updates the fluiddb/version tag for changes in the API.

    @param deploymentPath: The path to deploy Fluidinfo in.
    @param revision: The C{str} revision of the branch being deployed.
    """
    fluidinfoPath = os.path.join(deploymentPath, revision, 'fluidinfo')
    with cd(fluidinfoPath):
        with open('deployment/api-version.txt') as versionFile:
            version = versionFile.read()
            sudo('bin/python bin/fluidinfo update-version-tag '
                 'postgres:///fluidinfo '
                 '%s' % version,
                 user='fluidinfo')


def clearRedisCache(deploymentPath, revision):
    """Clear redis cache after deployment.

    @param deploymentPath: The path to deploy Fluidinfo in.
    @param revision: The C{str} revision of the branch being deployed.
    """
    fluidinfoPath = os.path.join(deploymentPath, revision, 'fluidinfo')
    with cd(fluidinfoPath):
        sudo('bin/python bin/fluidinfo clear-cache', user='fluidinfo')


def hasUnappliedDatabasePatches(deploymentPath, revision):
    """Determine if there are database patches to apply.

    @param deploymentPath: The path to deploy Fluidinfo in.
    @param revision: The C{str} revision of the branch being deployed.
    @return: C{True} if there are outstanding patches, otherwise C{False}.
    """
    path = os.path.join(deploymentPath, revision, 'fluidinfo')
    with cd(path):
        with settings(warn_only=True):
            out = sudo('bin/python bin/fluidinfo '
                       'patch-status postgres:///fluidinfo', user='fluidinfo')
            return out.return_code != 0


def applyDatabasePatches(deploymentPath, revision):
    """Apply database patches.

    The PostgreSQL database will be backed up before patches are applied,
    which means this could potentially take some time to run.

    @param deploymentPath: The path to deploy Fluidinfo in.
    @param revision: The C{str} revision of the branch being deployed.
    """
    path = os.path.join(deploymentPath, revision, 'fluidinfo')
    postgresBackupScript = os.path.join(deploymentPath, revision,
                                        'scripts', 'backup-postgresql.sh')
    with cd(path):
        with settings(warn_only=True):
            sudo('killall psql', user='postgres')
            logging.info('Backing up the Postgres database.')
            sudo(postgresBackupScript, user='postgres')
            sudo('bin/python bin/fluidinfo '
                 'patch-database postgres:///fluidinfo', user='fluidinfo')
