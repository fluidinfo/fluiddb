Built-in namespaces and tags
============================

Here is a brief description of namespaces and tags in Fluidinfo that the
system uses to manage itself. You will probably find some of them useful
too.

The fluiddb user
----------------

There is a user called ``fluiddb`` with a top-level namespace called
``fluiddb``. This user is just like any other user, though with permission
to act on any namespace or tag.

The about tag
-------------

The about tag has a path of ``fluiddb/about``. To find an object with a
given about value, you can do a Fluidinfo query on this tag. For example,
``fluiddb/about = "http://www.nytimes.com"``.

Usernames
----------

There is a tag called ``fluiddb/users/username`` whose values contain
Fluidinfo usernames. This tag can be found on each object corresponding to a
user.  So to find the object for a given user, you can send a query such as
``fluiddb/users/username = "david"``.

Note that in order for this query to work, you *must* test against the user
name in lower case. That's because usernames in Fluidinfo are case
insensitive and are converted to lower case for storage.

There is also a tag called ``fluiddb/users/name`` which holds the name of
the user in real life. This tag may not be present on all user objects, or
may be empty. But if a Fluidinfo user has provided their name, this is where
you can find it (i.e., this tag will be on the object corresponding to the
user, and its value will be the user's name).

Tags about namespaces
---------------------

The tag ``fluiddb/namespaces/path`` can be found on objects that correspond
to Fluidinfo namespaces. Its value is the full path name of the namespace. So
to find the object corresponding to a namespace ``george/books``, you could
do a query ``fluiddb/namespaces/path = "george/books"``.

Similarly, the tag ``fluiddb/namespaces/description`` can also be found on
objects that correspond to namespaces. Its value is the description of the
namespace (often given when the namespace is created).

Tags about tags
---------------

Just as with namespaces, there are two tags that hold information about
other tags. These tags are named ``fluiddb/tags/path`` and
``fluiddb/tags/description``, and they function in a manner analogous to
the tags for namespaces.

Permissions tags
----------------

There are also permissions tags corresponding to all the actions that can
be attempted on namespaces and tags. A full description of these can be
found `here <http://api.fluidinfo.com/html/permissions.html>`_. Please note
that it is *not* necessary to read that page in order to understand Fluidinfo
and its permissions system. Neither is it necessary to read the full
description in order to use the :doc:`http`. The description is
there for people who want to fully understand the Fluidinfo permissions
system.
