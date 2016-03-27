Namespace and Tag names
=======================

Name restrictions
-----------------

Namespace and tag names must be composed of `Unicode
<http://en.wikipedia.org/wiki/Unicode>`_ letters, digits, colon, period,
hyphen and underscore.

Name length
-----------

There is no length limit imposed directly on namespace or tag names.
However the entire path to a tag, including all its containing namespaces
and ``/`` delimiters, is limited to 233 characters.  So for example, if a
user ``ntoll`` has a namespace called ``music`` and a tag in that namespace
called ``play-count``, the tag's full path is ``ntoll/music/play-count``,
which has a length of 22.

..
   Note: the above limit is no longer true, as we've dropped use of AMQP.
   but it's not clear what to replace this text with. I don't think we
   should make any extravagant promises which we may not be able to keep
   in the future due to different architectural constraints from components
   that we may start using.

Paths
-----

The full path of a namespace or tag is made by separating the name
components by slash characters.  There is no leading slash.

Usernames appear at the start of all paths
-------------------------------------------

All top-level namespaces correspond to Fluidinfo usernames. So for example,
``nick/gadgets/palm`` is a namespace (or tag) under the ``nick`` user's
top-level namespace.

Identical namespace and tag names within a namespace
----------------------------------------------------

Namespace and tag names within a namespace do not have to form disjoint
sets. I.e., a namespace can contain both a sub-namespace and a tag of the
same name.

For example, a user called Tim might have a namespace ``tim/opinion`` in
which he might create other tags or namespaces like
``tim/opinion/romance``. But Tim could also have a *tag* with name
``opinion`` (i.e., with path ``tim/opinion``) which he might put onto
objects to record general opinions. Here the name ``opinion`` is being used
in the ``tim`` namespace as both a namespace name and a tag name.
