Fluidinfo
=========

`Fluidinfo <http://fluidinfo.com/>`_ (formerly FluidDB) is a shared online
datastore based on tags with values. It allows anyone to store, organize,
query and share data about anything.

Documentation
-------------

Our `developer page <http://fluidinfo.com/developers/>`_ is a good starting
point on how to use Fluidinfo, and the API documentation is included in the
`doc/` directory.

For more information we recommend our book, `Getting Started with Fluidinfo
<http://shop.oreilly.com/product/0636920020738.do>`_ — or have a look at
the `blog <http://blogs.fluidinfo.com/>`_.

Deploying Fluidinfo
===================

Getting help
------------

Deployment is automated by commands provided by the `bin/fluidinfo` tool.
Please run the following commands to learn more about it::

  $ bin/fluidinfo help commands
  $ bin/fluidinfo help deployment

You can learn more about deployment by reading `DEPLOYMENT.rst`.

Configuring Fluidinfo
=====================

Fluidinfo uses configuration files to determine which database and index to
use, which port to run on, etc.

Configurations
--------------

Deployment configuration files are stored in directories under the
`deployment` directory.

Configuration file
------------------

The default configuration file (in
`deployment/default/fluidinfo/fluidinfo-api.conf.template`) looks
something like this::

  [service]
  temp-path = var/tmp
  max-threads = 4
  port = 9000

  [store]
  main-uri = postgres://fluidinfo:fluidinfo@localhost/fluidinfo-test

  [index]
  url = http://localhost:8080/solr
  shard = localhost:8080/solr

  [cache]
  host = 127.0.0.1
  port = 6379
  db = 0

  [oauth]
  access-secret =
  renewal-secret =
  renewal-token-duration = 168

See the docstring for ``fluiddb.application.setupConfig`` for information
about these and additional fields.


Running the API service
=======================

The API service is a stateless HTTP server that provides the public API to
Fluidinfo.  It can be run using a variety of topologies from single instance
deployments to many instance deployments.

Starting the API service
------------------------

The service is started with the `fluidinfo-api` command::

  $ bin/fluidinfo-api -n

This will start an API service running interactively on port 9000 and
configured with a default configuration.  When many API services are run they
must each listen on a unique port.  Port numbers can be explicitly specified
as the command-line option to override the default value::

  $ bin/fluidinfo-api -n --port 9001

This starts the API service with the default configuration on port 9001.


Using a particular configuration
--------------------------------

`bin/fluidinfo-api` runs with a default configuration unless a `--config`
command line option is passed::

  $ bin/fluidinfo-api --config /etc/fluidinfo/main.conf

If the path is relative the current working directory is used as the base.
See the docstring for `fluiddb.application.setupConfig` to learn more about
configuration file parameters.


Debugging OAuth2 interactions locally
-------------------------------------

By default, OAuth2 interactions require HTTPS requests and will fail if a
plain HTTP request is made.  You can pass an optional `--development` flag
which disables HTTPS checks for OAuth2 interactions to perform local testing
and debugging::

  $ bin/fluidinfo-api -n --development

Developing Fluidinfo
====================

Prerequisites
-------------

Fluidinfo requires Python 2.6+ and is designed, tested and hosted on Ubuntu
12.04 LTS.  Please install virtualenvwrapper to manage Python virtual
environments.  See http://www.doughellmann.com/projects/virtualenvwrapper

Having said that, the following instructions should work on the latest stable
Ubuntu release.

Install our source code
-----------------------

Your first step should be to visit https://github.com/fluidinfo/fluidinfo and
create a fork of the fluiddb project. Then::

    $ mkvirtualenv fluiddb
    $ cd YOUR-TOP-LEVEL-PROJECTS-DIR
    $ git clone git@github.com:YOUR-GITHUB-USERNAME/fluiddb.git
    $ cd fluiddb
    $ git remote add upstream git@github.com:fluidinfo/fluiddb.git

Note that internally we often still refer to the Fluidinfo source code as
"fluiddb". This helps to distinguish it from the company name and from
the "fluidinfo.com" web application.

Install dependencies
--------------------

Run the following command from the project root to get the dependencies::

    $ bin/check-dependencies

If you get complaints about GNU parallel make sure the following is in your
apt sources file (/etc/apt/sources.list.d)::

    deb http://ppa.launchpad.net/ieltonf/ppa/ubuntu oneiric main
    deb-src http://ppa.launchpad.net/ieltonf/ppa/ubuntu oneiric main

Finally, ensure that the PPA for Fluidinfo referenced in the same file is
pointing to ``lucid``::

    deb http://ppa.launchpad.net/fluidinfo/fluiddb/ubuntu lucid main
    deb-src http://ppa.launchpad.net/fluidinfo/fluiddb/ubuntu lucid main

Where possible, Fluidinfo uses package dependencies installed from Ubuntu
repositories.  In some cases, we rely on source dependencies, which are
installed by `pip` in a virtualenv. Continuing from above::

  $ make build

If you ever need to rebuild the dependencies, you can re-run `make build`.

Set up PostgreSQL
-----------------

Fluidinfo uses a PostgreSQL database to store information about users,
namespaces, tags and so on.  You'll need to create a database user for
Fluidinfo::

  $ make setup-postgres

Note: If you are using PostgreSQL 9.1, you should change the `bytea_output`
setting to `escape` in the file `/etc/postgresql/9.1/main/postgresql.conf`.

Running the tests
-----------------

All tests should pass::

  $ make check-all

`make check-all` starts Fluidinfo and runs all unit and integration tests.
You can also run `make check` or `make check-integration` to run just the
unit tests or just the integration tests.

Learning more
-------------

Now that you have all the moving parts in place, go and read the docstring in
`fluiddb.__init__`.  It provides a high-level overview of the system design.


License
=======

::

  Copyright 2007-2016 Fluidinfo, Inc.

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.
