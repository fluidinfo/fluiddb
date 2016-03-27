.. -*- coding: utf-8; -*-

Architecture
============

Fluidinfo has been designed to scale dynamically. All aspects - storage,
organization, and query processing - have been designed and built in a
modular fashion, as services in a message-passing architecture. Storage is
tag-oriented. This results in something that resembles a `column store
<http://en.wikipedia.org/wiki/Column-oriented_DBMS>`_ in which tags are
fully independent of one another. Fluidinfo has been designed to make simple
queries fast, and to eliminate query complexity by using an extremely
limited query language whose execution can be trivially parallelized.

Fluidinfo operation is centralized
----------------------------------

Although storage and computation within Fluidinfo are highly distributed, its
administration and organization is centralized. There is a strong reason
for this: Fluidinfo is principally concerned with making it possible to
combine, augment, and search across information coming from multiple
sources. That's the whole point.

So for the time being, the coordination of Fluidinfo is centralized. We have
of course given thought to federalization and have some ideas as to how
that might be done.


Software components
-------------------

Fluidinfo relies in part upon the following open-source components:

* `Ubuntu <http://www.ubuntu.com/>`_ `GNU <http://www.gnu.org>`_/`Linux <http://www.linux.org>`_
* `Python <http://www.python.org/>`_
* `Twisted <http://www.twistedmatrix.com/>`_
* `PostgreSQL <http://www.postgresql.org/>`_
* `Lucene <http://lucene.apache.org/>`_ via `Solr <http://lucene.apache.org/solr/>`_


Open source
-----------

We plan to open source Fluidinfo, though the timetable for doing so has not
been set.

We contributed Twisted support to the Thrift project and we are part of the
Thrift team, an `Apache Incubator <http://incubator.apache.org/>`_ project.
We have also open-sourced `txAMQP <https://launchpad.net/txamqp>`_.
txAMQP has been adopted by a
number of other projects, some of which you can easily find via your
preferred search engine.


Where to now?
-------------

Hopefully you now have a good understanding of what makes Fluidinfo
special. Here a few suggestions to continue exploring Fluidinfo.

* Sign up for a Fluidinfo account `here
  <http://www.fluidinfo.com/accounts/new>`_ and start experimenting in the
  `Fluidinfo Explorer <http://explorer.fluidinfo.com>`_.
* Check out `initial reactions <mentions.html>`_ to Fluidinfo.
* Learn about the technical details in our discussion of `advanced
  concepts <advanced/index.html>`_.
