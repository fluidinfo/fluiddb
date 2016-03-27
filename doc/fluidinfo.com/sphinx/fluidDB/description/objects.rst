Objects
=======

Fluidinfo is conceptually very simple: it holds a large number of objects,
all of a single flexible kind, and it provides the means to create,
modify, and retrieve these objects.

A Fluidinfo object is just a collection of tags, usually with values.

As with other tagging systems, tags have names, such as ``tim/opinion``,
but unlike most tag systems, tags can also and usually do have values, such
as ``"very exciting"``. For now, think of an object as a container for
tags.

When objects are first created, they are completely empty.  Each is
assigned a unique identifier which can be used to carry out operations on
it, such as adding or removing tags.

There is no limit on the number of tags on an object.

Any application or user may create new objects at any time, and use them
for any purpose.


Objects have no owners!
-----------------------

This is the single most important property of Fluidinfo.

Any application can add tags to any object. There's no need to ask
permission.  When you create an object to store information, anyone else is
free to also add tags to that object. Note however that to do so they have
to be able to find the object (more on that later).

Permissions
-----------

Although objects are not owned, there is a strong and flexible
:doc:`permission system <permissions>` that applies to tags. The
permissions system prevents users from accessing or altering the tags of
other users - unless they have been given permission to do so.

This allows, for example, Sally to specify that Leo cannot see her
``sally/rating`` tags at all, and that Fiona can read but not change
or delete them.

The permissions system is one way in which Fluidinfo departs significantly
from the conceptual analogy with a wiki: Applications and users can never
change or delete data belonging to others, unless they have permission to
do so.

Example
-------

As a simple example, a Fluidinfo object might contain the following tags:

#. ``fluiddb/about`` with value http://bit.ly/wboQu

#. ``sally/rating`` with value ``6``

#. ``leo/rating`` with value ``8``

#. ``fiona/comment`` with value ``"I love this pic!"``

Here ``fluiddb``, ``sally``, ``leo`` and ``fiona`` are Fluidinfo users,
each of whom has a :doc:`namespace <namespaces>` in which to specify the
names of the tags they will add to objects.  Fluidinfo tags are described
in detail :doc:`here <tags>`.


Objects are never deleted
-------------------------

If all the tags on an object are removed, the empty object *does not go
away*. Fluidinfo objects are never deleted. This may seem odd at first, but it
makes good sense and is also useful. An object starts its life empty, so
there is no reason that an object which becomes empty later must be
removed. An empty object can be useful: an application may store its
identifier and use it for later communication with another application via
adding tags to it. Because objects are never deleted, an object identifier
can never become invalid.

Finding objects
---------------

Fluidinfo provides :doc:`a very simple query language <queries>` that
applications can use to find objects.

A simple example query is ``sally/rating > 5``.  This would result in the
above object being retrieved, provided that the user making the query had
read permission on ``sally/rating``. This is a second difference from a
wiki: The query language gives applications a way to target specific and
structured content within objects.

All information in Fluidinfo is on an equal footing
---------------------------------------------------

All tags on all objects are treated uniformly in Fluidinfo. There is no
distinction between the system user and any other user. Objects do not have
one special piece of "content" with the rest being considered metadata.
Fluidinfo makes absolutely no distinction between data and metadata (though
an application is free to do so, of course).

The permissions system is the sole arbiter of who may do what.  This
uniformity means Fluidinfo has a single API for creating information, it has
a single method of protecting information, and it has a single query
language for accessing information. All applications use these identical
tools.

..
   In fact, all the information that Fluidinfo maintains about users, tags,
   namespaces, permissions is stored right inside Fluidinfo.
