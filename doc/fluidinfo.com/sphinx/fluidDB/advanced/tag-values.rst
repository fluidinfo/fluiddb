Tag values
==========

Fluidinfo offers a wide range of possible values for tags.  These can be
divided into two categories: primitive and opaque.

.. _primitive-values:

Primitive values
----------------

These are values that Fluidinfo understands natively, and which you can most
usefully query on.  The full list is as follows:

* *null*: A null value is useful when you want to tag something but don't
  need the tag to have a value. For example, you might want to put a
  ``james/seen`` tag onto web page objects you've seen. These objects can
  then be retrieved using a query such as ``has james/seen``.

* *boolean*: A true or false value.

* *int*: An integer.

* *float*: A floating-point number.

* *string*: A string of Unicode characters.

* *set of strings*: A set of Unicode strings. This is similar to tags in a
  more traditional sense.

If you are using the :doc:`http`, you will use a special
``Content-Type`` header to PUT/GET primitive values. Details can be found
:ref:`here <payloads-with-tag-values>`.

.. _opaque-values:

Opaque values
-------------

You can store any kind of information you like in an opaque tag value. Each
such tag on an object has type information in the form of a `MIME
<http://en.wikipedia.org/wiki/MIME>`_ type.  Because Fluidinfo treats these
tags as opaque values, you cannot perform any search querying on them,
apart from using ``has`` and ``except`` to select or exclude objects with
opaque tag values.  This applies even to opaque tags with types like
``text/plain``. Even though such a tag probably holds a string, Fluidinfo
will still treat it opaquely. If you want to pass a string and have it
treated as such, i.e., for text indexing or equality comparisons, pass it
as a primitive value.

Fluidinfo allows you to specify any MIME type information you like -
including types you invent for your own purposes.  When you add a tag with
a specific MIME type to an object, Fluidinfo remembers the type and returns
it when the tag is later requested.  To give some examples, you could add a
tag to an object with type ``application/pdf`` or ``audio/mp3`` or your own
``my-app/preferences``.

When using the :doc:`http`, type information is transmitted in the HTTP
``Content-Type`` header.
