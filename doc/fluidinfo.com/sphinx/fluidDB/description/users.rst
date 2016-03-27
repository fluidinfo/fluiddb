Users
=====

When a new user (or application) is created in Fluidinfo, an object is made to
hold information for the user. Fluidinfo stores some information about the
user on this object.

The user is free to add more information to the object that represents
them. Because Fluidinfo objects are not owned, other users or applications
may do the same.

Social Networks
---------------

This makes it possible to build social networks inside Fluidinfo. As with all
information in Fluidinfo, these can be built without asking permission and
without needing to be anticipated. Because information can always be stored
in its most natural location, interesting searches combining information on
the same objects are immediately possible.

For example, suppose:

* A developer writes an application that extracts follower information from
  the `Twitter API <http://dev.twitter.com/>`_. When run by Fluidinfo
  user Jack, it puts a tag called ``jack/i-follow`` onto the objects
  of other Fluidinfo users.

  It is immediately possible to do interesting queries. For example, ``has
  jack/i-follow except has lisa/i-follow`` to see people Jack follows but
  whom Lisa does not.

* A second developer now writes a similar tool, perhaps pulling friend data
  out of Facebook, and putting ``USERNAME/fb-friend`` onto users' objects
  in Fluidinfo.  Searches across social networks are then possible. E.g.,
  show me who I follow on Twitter but do not have a friend on Facebook, or
  show me who two of my friends know in common but whom I do not follow on
  Twitter.

Fluidinfo allows any number of examples along these lines.  And because
objects are not owned, you don't need to wait for permission to try them
out - just add your data and start searching.  To see this in practice see
our `TechCrunch Disrupt presentation
<http://fluidinfo.com/developers/presentations#tc1>`_ which illustrates the
above using `Tickery <http://tickery.net>`_, `We Met At
<http://wemet.at>`_, and `Tunkrank <http://tunkrank.com>`_.

And much more
-------------

Any information at all can be put onto other users' objects. Think someone
is a spammer and want to alert others? Tag them, and use the presence of
your tag to avoid that user or their content when querying. Want to
indicate people you trust? Tag them, and use the tag in searches.

Not happy with Twitter's Suggested Users List? Why not make your own and do
searches that combine yours with other people's recommendations? Want to
put ratings onto tweets, or put your own measure of interestingness onto
users?  Just go ahead and do it. Then search on it, combine things, and
mash things up to your heart's content. See how to do this via
our article `Putting metadata onto tweets with FluidDB
<http://blogs.fluidinfo.com/fluidinfo/2009/12/01/putting-metadata-onto-tweets-with-fluiddb/>`_

Similarly, namespaces and tags can also be tagged and searched on. In this
way Fluidinfo allows for deep personalization and for the evolution of
reputation and trust.
