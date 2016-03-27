Query language
==============

Fluidinfo provides a simple query language that allows applications to search
for objects based on their tags' values. The following kinds of queries are
possible:

* **Equality & Inequality:** To find objects based on the numeric value of
  tags, e.g., ``tim/rating > 5``, exact textual values,
  e.g., ``geo/name = "Llandefalle"``, or boolean values,
  e.g. ``sara/owns = false``.

  You can use the backslash (``\``) escape character to specify the
  doublequote character (``"``) inside a term,
  e.g ``james/people = "John \"Hannibal\" Smith"``

* **Textual:** To find objects based on text matching of their tag values,
  e.g., ``sally/opinion matches "fantastic"``. Text matching is done with
  `Lucene <http://lucene.apache.org/java/docs/>`_. Currently, only complete
  words can be matched (case insensitively). The full matching capabilities
  and style of Lucene will soon be made available.

* **Presence:** Use ``has`` to request objects that have a given tag. For
  example, ``has sally/opinion``.

* **Set contents:** A tag on an object can hold a set of strings. For
  example, a tag called ``mary/product-reviews/keywords`` might be on an
  object with a value of ``[ "cool", "kids", "adventure" ]``. The
  ``contains`` operator can be used to select objects with a matching
  value. The query ``mary/product-reviews/keywords contains
  "kids"`` would match the object in this example.

* **Exclusion:** You can exclude objects with the ``except`` keyword. For
  example ``has nytimes.com/appeared except has james/seen``. The
  ``except`` operator performs a set difference.

* **Logic:** Query components can be combined with ``and`` and ``or``. For
  example, ``has sara/rating and tim/rating > 5``.

* **Grouping:** Parentheses can be used to group query components. For
  example, ``has sara/rating and (tim/rating > 5 or mike/rating > 7)``.

That's it!

Query result limits
-------------------

The main current limit is that queries may only return up to 1 million
objects.  If a query generates more than this, an error status is returned.
If you need a higher limit, please `email us <info@example.com>`_.
