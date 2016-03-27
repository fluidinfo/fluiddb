The *about* tag
===============

Fluidinfo has a special tag known as the *about* tag.

When an application creates an object, it can (optionally) specify what it
intends the object to be about.  This is just a convention, but it is a
highly useful one as it allows users and applications certainty as to
what their tags will be associated with.

For example, suppose an application wishes to add new information about New
York to Fluidinfo. While that information could be added to *any* object at
all, it likely makes sense to put it somewhere where there is other
information about New York.  So an application might choose to create an
object with an about tag with the value ``New York``.

This is just an informal example. More likely, an application would put its
information onto an object whose about tag had a more canonical value, for
example ``http://en.wikipedia.org/wiki/New_York``. Information about a book
might be put onto an object about ``ISBN:0394705947``. Other possibilities
include ``NASDAQ:GOOG``, ``user@hostname.com``, ``user:jane``, ``ip
88.221.11.50``, ``WOEID 24865675``, etc.

The about tag is immutable
--------------------------

There are some special properties of the about tag:

* Once it is added to an object, it can never be altered.
* It can only be added when an object is first created.
* It is never removed from an object.
* It is owned by the Fluidinfo system.
* Each about tag value is unique (see below).

Together, these properties ensure that applications have a way to find a
permanent, useful, and canonical suggested place to put information about
something.

About tag values are unique
---------------------------

The about tag is only useful if only one object can have any given about
tag. Fluidinfo ensures that this condition is maintained. So when an
application asks for the object about, e.g., ``country:france``, it is
guaranteed that the result is the only object with that about tag.

Applications can move at their own speeds
-----------------------------------------

Because any about tag can be created by anyone, applications that follow
the same about tag conventions do not need to wait for one another, to ask
permission, or even to be aware of one another, before putting new
information into its most natural location. This allows them to create data
at their own pace, and guarantees that independent applications with
information about the same thing can naturally put that information onto
the same Fluidinfo object.


Web of things
-------------

The about tag makes it simple to use Fluidinfo as a metadata engine for
everything.  It gives disparate applications and users an obvious canonical
place to put information about the same thing.

You can ask Fluidinfo for the object about something, and immediately add any
metadata or personalization data you like to that object.  The Fluidinfo
query language can be used to retrieve the object based on its shared tags.

Obvious conventions, such as using URLs or ISBN numbers as about tags, will
arise quickly. You are also free to start your own.

In a sense Fluidinfo already has an object for *everything*. It's just a
matter of asking for it, at which point it will be created if it doesn't
already exist.  In this way, Fluidinfo provides support for what has
informally been called the `web of things
<http://en.wikipedia.org/wiki/Web_of_Things>`_.

It's only a convention
----------------------

It should be emphasized that use of the about tag is optional. It is
perfectly valid and common for applications to create objects that are not
formally about anything. For example, an object that is used to hold
information tying together other objects, or an object that is used for
temporary storage.

There is also no reason why an application, or set of applications, could
not start and use another tag for canonically identifying objects - and
publicize their convention for others to adopt, or do it privately.
