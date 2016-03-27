Alpha software
==============

Fluidinfo is currently in alpha. That means that

* We will almost certainly run into bugs.
* The alpha system will initially be slow.
* There are important pieces of functionality not yet supported.
* Fluidinfo will occasionally need to be taken down.

Although Fluidinfo is conceptually simple, implementing it as a distributed
system intended to scale introduces many complexities. In some ways we're
only just at the beginning, despite years of thinking and development.
There are also some important pieces, for example OAuth authorization,
that are currently absent but which we're planning to add.

API stability
-------------

One advantage of being conceptually simple is that the Fluidinfo API is very
stable.  While we have plans to add certain things to existing API methods,
these will be in the form of additional arguments or payload fields and
will most likely be backwards compatible. During the alpha phase however,
we will occasionally break backwards compatibility if we believe the
advantages in doing so are sufficient. This will be done with warning and
we'll very happily help you in making any needed code changes.

Thanks
------

We'd like to say thanks for trying out Fluidinfo, and for your understanding
and patience during the alpha period. Please feel free to send us any
suggestions, criticisms, etc. The best ways to do are by joining us in the
``#fluidinfo`` channel on ``irc.freenode.net``, or by joining the `Fluidinfo
users mailing list <fluiddb-users@googlegroups.com>`_.
