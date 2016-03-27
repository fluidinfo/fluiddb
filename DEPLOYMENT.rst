=====================
Deployment procedures
=====================

These instructions describe how to use the ``bin/fluidinfo`` tool, in a
Fluidinfo branch, to perform deployment tasks.

0. Setting up the environment
=============================

First, Always be careful to check that you're running commands in the
correct branch, that your branch is up-to-date, and that you're in the right
virtualenv.

Most of the commands below expect the following settings to be
correctly configured in the environment::

  export AWS_ACCESS_KEY_ID=...
  export AWS_SECRET_ACCESS_KEY=...
  export EC2_PRIVATE_KEY=...
  export EC2_CERT=...
  export EC2_KEYPAIR=..
  export EC2_KEYPAIR_PATH=...

You might need to use EC2 command line tools for some operations,
make sure you have them installed::

  sudo apt-get install ec2-api-tools

1. Creating and preparing an instance for deployment
====================================================

Use the ``ec2-run-instances`` command to create a new instance::

  ec2-run-instances \
      --instance-type m1.small \
      -k $EC2_KEYPAIR \
      -z us-east-1a \
      -g default \
      ami-3fec7956

.. note:: - You can also use the Amazon EC2 Management Console do this.
          - Make sure you use the correct ami for Ubuntu 12.04 64 bits.
            This instructions won't work with other versions.
          - Depending on the setup you might need to use a different
            security group.

Use ``ec2-describe-instances`` to get the instance ID and hostname
of your new instance::

  ec2-describe-instances
  export REMOTE_HOST=...
  export INSTANCE_ID=...

Use the ``prepare-instance`` command to create a new user for your
instance and update the repositories and packages::

  bin/fluidinfo prepare-instance $REMOTE_HOST

.. note:: - This command will ask you for a password for the new user.
            Use it for sudo operations.
          - By default this command will use $USER as username, you can
            change it using the ``--username`` option.
          - By default this command will get your public SSH key from
            Launchpad, use the ``--ssh-key-url`` option to change that.

2. Configuring storage for the services
=======================================

You can skip this step if you're just deploying a small test instance.
Otherwise, you will need bigger storage for the different services.

You can use the ``create-disk`` command to create RAID10 arrays for storage::

  bin/fluidinfo create-disk \
      --instance-id $INSTANCE_ID \
      --num-volumes 4 \
      --volume-size 64 \
      --device-prefix /dev/sdi \
      --raid-device /dev/md1 \
      --mount-path /var/lib/postgresql \
      --name-prefix test-instance-psql

This will create 4 EBS volumes of 64GiB each one. They will be attached to
the specified instance as ``/dev/xvd{1-4}``. Then a RAID10 array of 128GiB will
be created on ``/dev/md1`` and finally it will be mounted on
``/var/lib/postgresql`` and added to ``/etc/fstab``.

Repeat the same operation for the other services using different devices and
mount points. For example:

- Solr: ``/var/lib/solr`` using ``/dev/sdj`` and ``/dev/md2``.
- Backup: ``/var/lib/postgresql/backup`` using ``/dev/sdk`` and ``/dev/md3``.
- Code: ``/srv`` using ``/dev/sdh`` and ``/dev/md4``.

.. note:: - If you use a ``--num-volumes`` value of 1. No RAID array will be
            created, and a single EBS volume will be mounted.
          - Save the volume IDs printed at the end of the command.

3a. Deploying on a single instance
==================================

Use the ``boostrap-*`` commands to install and configure the different
services.

PostgreSQL::

  bin/fluidinfo bootstrap-postgres \
      --server-name test.example.com \
      $REMOTE_HOST

Solr::

  bin/fluidinfo bootstrap-solr \
      --server-name test.example.com \
      $REMOTE_HOST

Redis::

  bin/fluidinfo bootstrap-redis \
      --server-name test.example.com \
      $REMOTE_HOST


FluidDB::

  bin/fluidinfo bootstrap-fluiddb \
    --server-name test.example.com \
    --create-schema true \
    --solr-import true \
    $REMOTE_HOST

Frontend (nginx, haproxy). Make sure you have the SSL cert files
(``fluidinfo.pem`` and ``fluidinfo.key``)::

  bin/fluidinfo bootstrap-frontend \
    --server-name test.example.com \
    --public-ssl-cert-path fluidinfo.pem \
    --private-ssl-cert-path fluidinfo.key \
    $REMOTE_HOST

.. note:: - If ``--server-name`` option is not provided, ``$REMOTE_HOST``
            will be used. However, it's highly recommend to use a server
            name.
          - Don't use these commands in different order.
          - These commands have more options, use
            ``bin/fluidinfo help <command>`` to see detailed documentation.


3b. Deploying on multiple instances
===================================

You can distribute the services on multiple instances. Here is an example of
how to deploy to three instances, one for PostgreSQL, another for Solr and
another for FluidDB + Redis + FrontEnd.

First, create the instances and prepare them using the steps described in
sections 1 and 2, but instead of using the default **security group** for the
instances, use ``fluidinfo-all-services``. You should end up with three host
names: ``$REMOTE_HOST_PG``, ``$REMOTE_HOST_SOLR`` and ``$REMOTE_HOST_FDB``.

Deploy PostgreSQL first on ``$REMOTE_HOST_PG``::

  bin/fluidinfo bootstrap-postgres \
      --server-name test.example.com \
      $REMOTE_HOST_PG

Then deploy Solr on ``$REMOTE_HOST_SOLR``. Note that the
``--postgres-uri`` option referencing the PostgreSQL instance is given::

  bin/fluidinfo bootstrap-solr \
      --server-name test.example.com \
      --postgres-uri postgresql://$REMOTE_HOST_PG:5432 \
      $REMOTE_HOST_SOLR

Deploy Redis on ``$REMOTE_HOST_FDB``::

  bin/fluidinfo bootstrap-redis \
      --server-name test.example.com \
      $REMOTE_HOST

Deploy FluidDB on ``$REMOTE_HOST_FDB`` too. Note that both the PostgreSQL and
Solr Instances are referenced::

  bin/fluidinfo bootstrap-fluiddb \
      --server-name test.example.com \
      --postgres-uri postgres://fluidinfo:fluidinfo@$REMOTE_HOST_PG:5432/fluidinfo \
      --solr-url http://$REMOTE_HOST_SOLR:8080/solr  \
      --create-schema true \
      --solr-import true \
      $REMOTE_HOST_FDB

Deploy the frontend on ``$REMOTE_HOST_FDB`` too::

  bin/fluidinfo bootstrap-frontend \
      --server-name test.example.com \
      --public-ssl-cert-path ~/fluidinfo/ssl/fluidinfo.pem \
      --private-ssl-cert-path ~/fluidinfo/ssl/fluidinfo.key \
       $REMOTE_HOST_FDB

.. note:: Currently, Fluiddb, Redis and the frontend  must run on the same
    instance. Support for distributing these components will be added
    in the future

3c. Deploying with multiple Solr shards
=======================================

You can configure Solr to run on multiple instances too. Repeat the same
initial steps of section 3b, but instead of creating a single Solr instance,
create three: ``$REMOTE_HOST_SOLR0``, ``$REMOTE_HOST_SOLR1`` and
``$REMOTE_HOST_SOLR2``

Deploy PostgreSQL as described in section 3b. Then deploy Solr on each of the
three machines created for it, using the ``--num-shards`` option to indicate
the number of shards and ``-shard-id`` to indicate the ID (starting from 0) of
the given shard::

  bin/fluidinfo bootstrap-solr \
    --server-name test.example.com \
    --postgres-uri postgresql://$REMOTE_HOST_PG:5432 \
    --num-shards 3 \
    --shard-id 0 \
    $REMOTE_HOST_SOLR0

  bin/fluidinfo bootstrap-solr \
    --server-name test.example.com \
    --postgres-uri postgresql://$REMOTE_HOST_PG:5432 \
    --num-shards 3 \
    --shard-id 1 \
    $REMOTE_HOST_SOLR1

  bin/fluidinfo bootstrap-solr \
    --server-name test.example.com \
    --postgres-uri postgresql://$REMOTE_HOST_PG:5432 \
    --num-shards 3 \
    --shard-id 2 \
    $REMOTE_HOST_SOLR2

Then deploy FluidDB using the first instance as Solr URL and specifying the
other shards using ``--solr-shards`` option. The ``--solr-shards`` option uses
the same format as the ``shards`` field in ``fluidinfo-api.conf`` file. Make
sure you **don't** prefix the shards with ``http://`` and don't forget the
``/solr`` part at the end of each shard::

  bin/fluidinfo bootstrap-fluiddb \
    --server-name test.example.com \
    --postgres-uri postgres://fluidinfo:fluidinfo@$REMOTE_HOST_PG:5432/fluidinfo \
    --solr-url http://$REMOTE_HOST_SOLR1:8080/solr  \
    --solr-shards $REMOTE_HOST_SOLR0:8080/solr,$REMOTE_HOST_SOLR1:8080/solr,$REMOTE_HOST_SOLR2:8080/solr \
    --create-schema true \
    --solr-import true \
    $REMOTE_HOST

Deploy the frontend as described in section 3b.

4. Testing a new instance
==========================

Use the ``check-instance`` command to exercise the system and check that
every subservice is working properly::

  bin/fluidinfo check-instance $REMOTE_HOST

.. note:: In case of a multiple instance deployment use the instance with the
    front end as ``$REMOTE_HOST``

5.Upgrade a Fluidinfo deployment
================================

Use the ``update-fluiddb`` command to update an existing deployment:

bin/fluidinfo update-fluiddb $REMOTE_HOST

**NOTE:** In the unlikely event that you've made changes to the Solr import handler, you will also need to rebuild the tagvaluetransformer.jar using ``ant jar``, copy the resulting file to ``/usr/share/solr/WEB-INF/lib`` and restart Tomcat.

6. Upgrade a Fluidinfo deployment with database patches
=======================================================

To be added...

7. Adding a Solr shard to an existing deployment
================================================

Not yet supported.

8. Deploying API documentation
==============================

To upload the latest API documentation to http://api.example.com::

  fab live deploy

9. Restoring the production database on a test instance
=======================================================

To be added...

10. Asking Solr to re-index everything
======================================

To clear and re-index the Solr database, hit
``http://${SOLR_SERVER}:${SOLR_PORT}/solr/dataimport?command=full-import&clean=true``
**once**. This will take anywhere from 20 seconds on the sandbox to many moons
on main. You can watch the progress at
``http://${SOLR_SERVER}:${SOLR_PORT}/solr/dataimport``. While this import is
running, search queries to FluidDB will return no or incomplete results.

Further information
===================

The code that contains deployment logic is in the ``fluiddb.scripts.commands``
and ``fluiddb.scripts.deployment`` modules.  Configuration files and templates
are in the ``resources`` directory.
