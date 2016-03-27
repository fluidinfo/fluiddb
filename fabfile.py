"""
This fabfile contains the recipe for automatically testing and deploying the
api.fluiddb.com website.

Fabfiles are strange and configuring them is sometimes a bit hit and miss,
but nevertheless the following functions are defined by fabric:

require - gets the appropriate settings (in our case only defined in live())
run - run a command on the remote server
local - run a command on your local machine
put - transfer a file
abort - aborts the run of the fabfile

I've commented the intentions behind each command so it should all make sense.

This script was written against Fabric 0.9.2.
"""
from __future__ import with_statement
from fabric.api import require, run, local, env, put
from datetime import datetime


def live():
    """
    Defines the live host.
    """
    RELEASE = datetime.today().strftime('%Y%m%d-%H%M%S')
    env.hosts = ['user@fluiddb.example.com']
    env.sitename = 'api.example.com'
    env.path = '%s-%s' % (env.sitename, RELEASE)


def build_docs():
    """
    Build HTML files from the FluidDB API registry.
    """
    local('make apidocs')
    local('make sphinxdocs')


def upload_website():
    """
    Upload static files to the server.
    """
    require('hosts', provided_by=[live])
    # upload
    run('mkdir /var/www/%(path)s' % env)
    run('mkdir /var/www/%(path)s/html' % env)
    run('mkdir /var/www/%(path)s/css' % env)
    put('doc/example.com/api/html/*', '/var/www/%(path)s/html' % env)
    put('doc/example.com/api/css/*', '/var/www/%(path)s/css' % env)
    put('doc/example.com/api/favicon.ico', '/var/www/%(path)s' % env)
    local('make -C doc/example.com/sphinx/fluidDB/ dist')


def configure_web_server():
    """
    Makes sure that the newly uploaded deployment is linked to the right
    place in the filesystem and the webserver restarts.
    """
    require('hosts', provided_by=[live])
    run('rm -rf /var/www/%(sitename)s' % env)
    run('ln -s /var/www/%(path)s /var/www/%(sitename)s' % env)


def deploy():
    """
    Wraps all the steps up to deploy to the live server.
    """
    build_docs()
    upload_website()
    configure_web_server()
