Namespaces
==========

Fluidinfo namespaces provide a simple hierarchical way of organizing names -
names of tags, and names of other (sub-)namespaces.

When a new user is created within Fluidinfo, a top-level namespace is created
for them. For example, if Tim chooses the Fluidinfo username ``tim``, a
top-level ``tim`` namespace is created for him.

Fluidinfo usernames are case insensitive.

Tim may then add a tag called ``rating`` within that namespace with the
intention of tagging objects with his ratings. With its name qualified by
his namespace, Tim's rating tag can be unambiguously referred to as
``tim/rating``. By using namespace and tag names, with components separated
by ``/``, we can avoid any conflict or confusion with other Fluidinfo rating
tags, e.g., ``sara/rating``.

Namespaces are hierarchical. Tim can later create a new namespace, for example
``books``, within his ``tim`` namespace, and in that namespace create an
``i-own`` tag. That tag would have a full name of ``tim/books/i-own``.  Tim
could use it to tag objects in Fluidinfo that correspond to books he owns.

Because objects in Fluidinfo are not owned, another user, Sara, would be free
to add her own information to the book objects Tim had tagged. Thus an
object might have both ``tim/books/i-own`` and ``sara/rating`` tags on it,
making it possible to ask Fluidinfo to find books with a high Sara rating but
which Tim does not own.

Applications are users too
--------------------------

When a developer writes a new application that uses Fluidinfo for storage,
the application is also assigned a top-level namespace. For example, a
mobile phone application which creates mazes for the user might have the
Fluidinfo namespace ``amazing``. It might create one Fluidinfo object for each
maze, perhaps tagging the objects with ``amazing/maze-id``.  It might keep
its high scores using a tag called ``amazing/high-scores``, and it could
record the time a user last played and whether the user had registered yet
by tagging the user's object with ``amazing/last-played`` and
``amazing/registered`` tags.


Finding namespaces
------------------

Just as with tags, when a Fluidinfo namespace is created, a
description may be provided. There is a Fluidinfo object associated
with the namespace and the description is added to it as a normal
tag. As a result it is possible to search on namespace descriptions
using a regular Fluidinfo query.
