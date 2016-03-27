# -*- coding: utf-8 -*-
import os
import random

from twisted.trial import unittest
from twisted.internet import defer
import txsolr
from txfluiddb.client import Endpoint, Object

from fluiddb.admin import util

util.requireEnvironmentVariables('FLUIDDB_ENDPOINT',
                                 'FLUIDDB_INDEXING_SERVER_URL')
FLUIDDB_URL = os.environ['FLUIDDB_ENDPOINT']
SOLR_URL = os.environ['FLUIDDB_INDEXING_SERVER_URL']


class TestIndexing(unittest.TestCase):
    """
    Tests text indexing
    """

    def setUp(self):
        self.fluiddb = Endpoint(FLUIDDB_URL)
        self.solr = txsolr.SolrClient(SOLR_URL)
        self.aboutTag = 'fluiddb/about'

    @defer.inlineCallbacks
    def test_aboutTagIndexation(self):
        """
        Create some objects in FluidDB with an about tag and then search
        in the Solr index to check if the the tags are indexed.
        """

        aboutTags = [u'short',
                     u'longer about description',
                     u'ワンピース']
        # First add the objects to FluidDB
        objectsByAbout = {}
        for about in aboutTags:
            obj = yield Object.create(self.fluiddb, about)
            objectsByAbout[about] = obj.uuid

        yield self.solr.commit()

        # Then search the objects in Solr
        for about in aboutTags:
            r = yield self.solr.search('path:%s AND value_fts:"%s"'
                                       % (self.aboutTag, about))
            self.assertTrue(r.results.numFound > 0)

            # checks that at least one of the returning object ids is one
            # of the objects we just added
            self.assertTrue(any(obj['fluiddb/id'] in objectsByAbout.values()
                                for obj in r.results.docs))

        defer.returnValue(None)

    @defer.inlineCallbacks
    def test_aboutTagsTermSearch(self):
        """
        Adds some objects to fluidDB with about tags. Then search terms (words)
        in the about tags.
        """

        aboutTags = [u'One Piece (ワンピース Wan Pīsu?) is a Japanese',
                     u'manga series written and illustrated by Eiichiro Oda',
                     u'that has been serialized in Weekly Shōnen Jump since',
                     u'August 4, 1997. The individual chapters are being',
                     u'published in tankōbon volumes by Shueisha']

        # First add the objects to FluidDB
        objectsByAbout = {}
        for about in aboutTags:
            obj = yield Object.create(self.fluiddb, about)
            objectsByAbout[about] = obj.uuid

        yield self.solr.commit()

        # Then search the objects in Solr
        for about in aboutTags:
            term = random.choice(about.split())
            r = yield self.solr.search('path:%s AND value_fts:"%s"' %
                                       (self.aboutTag, term))
            self.assertTrue(r.results.numFound > 0)

            # checks that at least one of the returning object ids is one
            # of the objects we just added
            self.assertTrue(any(obj['fluiddb/id'] in objectsByAbout.values()
                                for obj in r.results.docs))

        defer.returnValue(None)


class TestSearch(unittest.TestCase):

    def setUp(self):
        self.fluiddb = Endpoint(FLUIDDB_URL)
        self.solr = txsolr.SolrClient(SOLR_URL)

    @defer.inlineCallbacks
    def test_aboutTagSearch(self):
        """
        Creates a simple object with an about tag and then tries to get the
        object using a query with the "matches" operator.
        """

        aboutTag = 'description'
        obj = yield Object.create(self.fluiddb, aboutTag)

        # force Solr Commit
        yield self.solr.commit()

        query = 'fluiddb/about matches "%s"' % aboutTag
        results = yield Object.query(self.fluiddb, query)
        results = [o.uuid for o in results]

        self.assertTrue(len(results) > 0)
        self.assertIn(obj.uuid, results)

    @defer.inlineCallbacks
    def test_AboutTagSearchTerms(self):
        """
        Creates various objects with a phrase as about tag. Then query FluidDB
        using the "matches" operator on one of the words of the phrase.
        """

        aboutTags = [u'Haruhi Suzumiya (涼宮ハルヒ) is the',
                     u'general name for a series of light novels written',
                     u'by Nagaru Tanigawa and illustrated by Noizi Ito',
                     u'and subsequently adapted into other media. The story',
                     u'follows the title character, Haruhi Suzumiya']

        objectsByAbout = {}
        for about in aboutTags:
            obj = yield Object.create(self.fluiddb, about)
            objectsByAbout[about] = obj.uuid

        # Force Solr Commit
        yield self.solr.commit()

        for about in aboutTags:
            # chose any word of the phrase
            term = random.choice(about.split())

            query = 'fluiddb/about matches "%s"' % term
            results = yield Object.query(self.fluiddb, query)
            results = [o.uuid for o in results]

            self.assertTrue(len(results) > 0)
            self.assertIn(objectsByAbout[about], results)

    @defer.inlineCallbacks
    def test_AboutTagComplexSearchQuery(self):
        """
        Creates a simple object with an about tag and then tries to get the
        object using a composed query (with more than one operator) involving
        the "matches" operator.
        """

        aboutTag = 'my testing about tag'
        obj = yield Object.create(self.fluiddb, aboutTag)

        # force Solr Commit
        yield self.solr.commit()

        query = u'has fluiddb/about and fluiddb/about matches "%s"' % aboutTag
        results = yield Object.query(self.fluiddb, query)
        results = [o.uuid for o in results]

        self.assertTrue(len(results) > 0)
        self.assertIn(obj.uuid, results)
