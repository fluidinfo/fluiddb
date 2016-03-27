import site
import os
from urlparse import urljoin

from net.grinder.script.Grinder import grinder
from net.grinder.plugin.http import HTTPRequest

from fom.session import Fluid
import objects
import about
import namespaces
import tags
import httplib2_monkeypatch


# We're using the modules only to avoid Pyflakes warnings. Sorry kittens.
_ = grinder
_ = site

# We monkeypatch httplib2 to use FOM with The Grinder. Sorry again kittens.
httplib2_monkeypatch.registerHook()


class TestRunner:
    def __init__(self):
        endpoint = os.environ['FLUIDDB_ENDPOINT']
        username = os.environ['FLUIDDB_ADMIN_USERNAME']
        password = os.environ['FLUIDDB_ADMIN_PASSWORD']
        self.solrURL = os.environ['FLUIDDB_INDEXING_SERVER_URL']

        self.fluiddb = Fluid(endpoint)
        self.fluiddb.login(username, password)

    def solrCommit(self):
        request = HTTPRequest()
        url = urljoin(self.solrURL, 'update')
        request.POST(url, '<commit />')

    def __call__(self):

        fluiddb = self.fluiddb
        testNamespace = 'fluiddb/testing'

        # CREATE
        objectId = objects.createRandomObject(fluiddb)
        aboutValue = about.createRandomObject(fluiddb)
        namespace = namespaces.createRandomNamespace(fluiddb, testNamespace)
        tag = tags.createRandomTag(fluiddb, testNamespace)

        self.solrCommit()

        #UPDATE
        objects.setRandomTagValueString(fluiddb, objectId, tag)
        about.setRandomTagValueString(fluiddb, aboutValue, tag)
        namespaces.updateNamespaceWithRandomDescription(fluiddb, namespace)
        tags.UpdateTagWithRandomDescription(fluiddb, tag)

        # READ
        objects.simpleEqualsQuery(fluiddb, aboutValue)
        objects.simpleMatchesQuery(fluiddb, aboutValue)
        objects.getObjectInfo(fluiddb, objectId)
        objects.getTagValue(fluiddb, objectId, tag)
        objects.hasTagValue(fluiddb, objectId, tag)
        about.getObjectInfo(fluiddb, aboutValue)
        about.getTagValue(fluiddb, aboutValue, tag)
        about.hasTagValue(fluiddb, aboutValue, tag)
        namespaces.getNamespaces(fluiddb, namespace)
        tags.getTagInfo(fluiddb, tag)

        #DELETE
        objects.deleteTagValue(fluiddb, objectId, tag)
        about.deleteTagValue(fluiddb, aboutValue, tag)
        namespaces.deleteNamespace(fluiddb, namespace)
        tags.deleteTag(fluiddb, tag)
