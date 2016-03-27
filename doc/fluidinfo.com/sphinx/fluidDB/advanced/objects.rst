Objects
=======

Identifiers
-----------

The unique identifiers associated with Fluidinfo objects are random `UUID
<http://en.wikipedia.org/wiki/UUID#Version_4_.28random.29>`_\ s.  These are
passed to and from the Fluidinfo API as strings (as part of the request URI
in the HTTP API), in the form
``xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx``. Here each ``x`` represents a
single hexadecimal digit and the ``y`` represents a hexadecimal digit from
the set `{8,9,A,B}`.

Users, namespaces, and tags have an associated object
-----------------------------------------------------

Each time a user, a namespace, or a tag is created, a new Fluidinfo object
is created to hold information about it.

In the case of a namespace or tag, the object will have tags giving its
path and description. In the case of a user, the username and other
information is stored on the object.

These objects play an important role in Fluidinfo. Not only are they the
place where Fluidinfo stores its own information about users, namespaces and
tags, but others can put information onto these objects too.

If you write an application that deals with Fluidinfo users, namespaces, or
tags, these objects will often be the best place to store your information.

For example, an application that used the `Twitter
<http://www.twitter.com>`_ API to get a user's followers could put the fact
that ``A`` is following ``B`` onto the Fluidinfo object for user ``B``.  Or
if you write an iPhone application that allows a user to upload their
latitude and longitude, an obvious place to put that information is on the
user's Fluidinfo object.
