Tags
====

A Fluidinfo user, for example named Sara, can tag as many different objects
as she likes with her tags, using whatever values she likes. For example,
she might tag an object representing The Eiffel Tower, with a
``sara/opinion`` of ``beautiful`` and another object representing Quantum
Electrodynamics, with the ``sara/opinion`` of ``hard``.

Tag types
---------

Each of an object's tags has a type.  The values for a tag do not have to
be the same across all objects on which the tag appears.  For example,
there might be a numeric ``sara/opinion`` tag on one object, and a textual
``sara/opinion`` on another.  She might normally rate books on a 0-5 scale,
but also use some textual values, like "still reading", "abandoned" or
"can't make up my mind".

As another example, imagine a company storing resumes and putting a
``company.com/job-search/resume`` tag on a new Fluidinfo object for each job
applicant. The tag could hold the submitted resume regardless of its
document type. And because Fluidinfo offers an HTTP interface, the content of
a tag could be viewed directly in a web browser, with Fluidinfo delivering
the appropriate ``Content-type`` header for the tag.

Fluidinfo allows tags to hold numbers, text, images, spreadsheets, etc. ---
anything you want, in fact. You indicate the type of a tag when you create
it, and Fluidinfo will give it back when the tag is later requested.

More details on possible tag values, are given in `the advanced documentation
<advanced/tag-values.html>`_.

Permissions on tags
-------------------

The Fluidinfo :doc:`permissions system <permissions>` specifies permissions
for *all* occurrences of a tag on objects, not for tags occurrences on
objects individually.  So, for example, Sara can allow another user to read
her ``sara/rating`` and ``sara/comment`` tags, prevent another from reading
them, and can give a trusted friend permission to add those tags to new
objects, or to change existing values.  But she cannot give permission to
someone to read the ``sara/comment`` tag on one object but not
on another. I.e., the permission applies to the entire set of occurrences of
``sara/comment`` on objects.

Using and finding tags
----------------------

There is no limit to the number of tags that can be attached to an object.
For example, a book object might have ``sara/rating``, ``sara/opinion``,
``tim/opinion``, and ``mike/opinion`` as well as many other tags holding
information about title, price, number of stars, URLs, comments, page
numbers that users are up to, dates that users read it, etc.

Any tag may be placed on any object.  However, a particular tag, such as
``sara/opinion``, cannot be present multiple times on an object. I.e., Sara
cannot put two ``sara/opinion`` tags on the same object.

When a Fluidinfo tag is created, a description may be provided. There
is a Fluidinfo object associated with the tag and the description
simply becomes a tag on *that* object. As a result, it is also
possible to search on tag descriptions using a regular Fluidinfo
query.
