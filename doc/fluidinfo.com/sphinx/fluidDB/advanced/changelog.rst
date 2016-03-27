.. -*- coding: utf-8; -*-

.. |incompatible| image:: _static/warning.png
    :align: bottom

Change Log
==========

Below, in reverse chronological order, you'll find the API changes we've
made to Fluidinfo. The icon |incompatible| is used to indicate changes that
are not backward compatible.

Please note that this change log is deliberately brief. To fully understand
the changes and how they may affect your code, *please follow the links to
the relevant details*.

Changes 2012/09/20
------------------

The Fluidinfo sandbox has been deactivated as it was only in very light use
and was not being maintained as regularly as we had intended.

HTTP API changes 2012/03/05
---------------------------

Added a new ``/recent`` endpoint.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

This new endpoint allows the user to get information about the latest tag
values created on a particular object or by a particular user.

Changed the default ``fluiddb/about`` value for users.
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Objects representing Fluidinfo users now will use the ``@<username>`` pattern
for ``fluiddb/about`` value instead of the old ``Object for the user named
<username>`` pattern. All the values on the old objects have been migrated.

Added new illegal queries.
^^^^^^^^^^^^^^^^^^^^^^^^^^

The following queries are now illegal in Fluidinfo: ``has fluiddb/about`` and
``fluiddb/about matches ""``. These queries produce too many results.

HTTP API changes 2012/02/13
---------------------------

Added an ``updated-at`` field to ``/values`` ``GET`` response format
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

An ``updated-at`` has been added to the response value of ``/values`` ``GET``
showing an ISO 8601 datetime string with the last modification date of a given
value.

HTTP API changes 2011/08/02
---------------------------

Namespaces and tags are created automatically
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When a namespace or tag is created, or a tag value is stored, missing
intermediate namespaces and tags are created automatically.  The user must
have permission to create child namespaces and tags on the parent namespace,
othewise an HTTP 401 is returned.

Namespaces and tags inherit their permissions
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

New namespaces and tags inherit their permissions from those set on their
parent namespace.  A new namespace or tag created with a parent namespace that
has permissions set to keep data private will be private.  As a result of this
change /policies has been removed.


HTTP API changes 2011/07/30
---------------------------

Fixed problem with ``Access-Control-Allow-Headers``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It was not possible to send `Cross-Origin Resource Sharing (CORS)
<http://en.wikipedia.org/wiki/Cross-Origin_Resource_Sharing>`_ requests to
Fluidinfo using a Webkit based browser because of a pre-flight request
problem.

Webkit based browsers only allow headers listed in the
``Access-Control-Allow-Headers`` header returned in the pre-flight request
to be used in the subsequent request. According to the CORS specification
``Content-Type`` does not need to be listed in
``Access-Control-Allow-Headers`` and should work no matter what. This is a
bug in Webkit browsers.

Unfortunately, the side effect was that CORS requests didn't work for users
of such browsers, so we're now including ``Content-Type`` in the header as
part of the pre-flight response. Thanks to IRC user ErrGe for pointing out
this problem.


HTTP API changes 2011/07/27
---------------------------

Fixed problem with double quotes in ``/about`` about values
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Fluidinfo was giving a ``400 (Bad request)`` error for ``/about`` requests
with double quotes in the about value. E.g., ``GET
/about/the%20"best"%20idea``. This has been fixed.

HTTP API changes 2011/07/24
---------------------------

Added ``WWW-Authenticate`` header to 401 (Unauthorized) responses
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We are now sending a ``WWW-Authenticate`` header with value ``Basic
realm="Fluidinfo"`` on all ``401 (Unauthorized)`` responses, as mandated by
section 1.2 of `RFC2616 <http://www.ietf.org/rfc/rfc2617.txt>`_. Thanks to
IRC user ErrGe for pointing out this omission.

HTTP API changes 2011/03/10
---------------------------

Added ``X-FluidDB-Type`` header to ``/objects`` and ``/about`` responses
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``GET`` and ``HEAD`` methods on /objects and /about used to get a
primitive tag value now contain an ``X-FluidDB-Type`` header indicating the
type of the requested value. :ref:`Details <payloads-with-tag-values>`.
Many thanks to `Xavier Noria <http://twitter.com/fxn>`_ for suggesting this
change.

Changed ``/values`` ``PUT`` payload format
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``PUT`` method on /values now allows setting tag values on objects
matching multiple queries passed in the payload. The less powerful old
approach of sending a query in the URI is still supported for backwards
compatibility, but is no longer documented.  :ref:`Details
<http-slash-values>`.

FluidDB to Fluidinfo name change 2011/02/04
-------------------------------------------

We have stopped using the name FluidDB, in favor of Fluidinfo. The
documentation has been updated accordingly. For the reasoning behind this
change, please see the `blog post announcement
<http://blogs.fluidinfo.com/>`_.

HTTP API changes 2010/12/06
---------------------------

Fixed wrong ``/values`` ``GET`` response format
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The ``id`` key was being left out in the response dictionary for ``GET``
requests on /values.

HTTP API changes 2010/11/08
---------------------------

``SEE`` permission replaced with ``READ``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We have simplified the permissions system slightly and are now using only
the ``READ`` permission on tags to decide whether API calls accessing tag
values should be allowed to proceed. Anything that used the ``SEE``
permission now uses ``READ``. E.g., when you do a ``GET`` on an object to
retrieve the names of its tags, you will only receive those for which you
have ``READ`` permission. Many thanks to `Jamu Kakar
<http://twitter.com/jkakar>`_ for suggesting this simplification.

``/values`` added to HTTP API
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is now possible to manipulate multiple tag values in a single API
request to ``/values``. :ref:`Details <http-slash-values>`.

|incompatible| Deleting a tag instance now always returns ``204``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Trying to DELETE a tag value from an object that did not have that tag
formerly resulted in a ``404 (Not found)`` status. This has been changed to
simply return the non-error ``204 (No Content)`` status of a DELETE in which
the tag was present on the object.

``/about`` added to HTTP API
^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is now possible to access Fluidinfo objects that have a ``fluiddb/about``
tag via HTTP requests to URI that start with ``/about``. For example, the
object about Barcelona can be reached directly via ``/about/Barcelona``.
The behavior of ``/about``, when given an about value, is exactly like that
of ``/objects`` when given an object id. For more information, see the API
docs at `<http://api.fluidinfo.com/>`_.  Many thanks to `Holger Dürer
<http://twitter.com/hd42>`_ for suggesting ``/about``.

``Content-MD5`` header for checking payload content
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is now possible to send a checksum of a payload to Fluidinfo via the
``Content-MD5`` header. Fluidinfo will attempt to validate the checksum with the
payload and return a ``412`` (Precondition failed) error in the case of a
mismatch. Please see `RFC1864 <http://www.ietf.org/rfc/rfc1864.txt>`_ and
`RFC2616 (Section 14.15) <http://www.ietf.org/rfc/rfc2616.txt>`_.

HTTP API changes 2010/08/26
---------------------------

PUT of primitive values with a charset being treated as opaque
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Daniel A. Nagy reported that his browser was appending ``;charset=utf-8``
to the ``Content-type`` header on his tag value PUT requests with primitive
value types. I.e., he'd put ``application/vnd.fluiddb.value+json`` in the
request ``Content-type`` header and his browser would change that to
``application/vnd.fluiddb.value+json; charset=utf-8``, causing Fluidinfo to
treat the value as opaque. After some discussion on the #Fluidinfo channel on
``irc.freenode.net`` it was decided that Fluidinfo should ignore anything
following an initial ``application/vnd.fluiddb.value+json`` in
``Content-type`` headers. Other ``Content-type`` header values will be
stored and returned as-is, as usual. Thanks Daniel.

The fix results in a small improvement: the ``Content-type`` returned in a
GET on an opaque type will be identical in case to the one originally given
in the PUT.  Formerly, all content types were converted to lower case, but
there is no reason for Fluidinfo to alter what it is given.

HTTP API changes 2010/08/25
---------------------------

HEAD requests were setting ``Content-Length`` to zero
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

All ``HEAD`` requests for tag values were receiving a ``Content-Length``
header containing ``0``. This has been fixed. Thanks to Rooslan S. Khayrov
for pointing this out.

HTTP API changes 2010/08/11
---------------------------

``crossdomain.xml`` request support
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Flash and Silverlight clients request a file called ``crossdomain.xml``
which lets them access resources from multiple domains. This is now
supported. Thanks to Ross Jempson for the suggestion and testing.

``500`` error when a different user sets a tag value with same type
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
When an existing tag value was changed on an object and the new value had
the same type but the request came from a different user than the one who
had set the original value, we were returning a ``500 (Internal server
error)`` error. This is now fixed.

|incompatible| Support for versions in the HTTP API has been dropped
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

To reduce internal complexity, and because the Fluidinfo API is expected to
be very stable, API version numbers sent in HTTP requests are no longer
supported.  If you send a request containing a version number, you will now
receive a ``404 (Not Found)``.

HTTP API changes 2010/01/09
---------------------------

This release mainly contains internal changes to Fluidinfo, which are not
visible to API users. There are no backwards incompatible changes.  Changes
visible to HTTP API users are the following:

JSONP support
^^^^^^^^^^^^^

Fluidinfo now supports JSONP. This allows Fluidinfo Javascript applications to
avoid the single-origin policy of web browsers by using an HTML ``script``
tag. :ref:`Details <JSONP_support>`.

HEAD requests now return Content-Type and Content-Length headers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When making a ``HEAD`` request to get information about a tag on an object,
we were not sending ``Content-Type`` or ``Content-Length`` headers as
`RFC 2616
<http://www.w3.org/Protocols/rfc2616/rfc2616-sec9.html#sec9.4>`_ implies
we should have. `Reported
<http://bugs.fluidinfo.com/fluiddb/issue17>`_ by `Nicholas Tollervey
<http://ntoll.org/contact>`_.

``500`` error when sending credentials for a non-existent user
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We were not cleanly handling the processing of requests that sent a
non-existent username in the credentials. This now results in a ``401
(Unauthorized)``.

``500`` error when retrieving a namespace or tag with no description
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When doing a ``GET`` on a namespace or tag and specifying that the
description also be returned, a ``500`` error was being returned if the
namespace or tag had no description. This is now fixed.  Reported by
`Otoburb <http://twitter.com/otoburb>`_ and `Nicholas Tollervey
<http://ntoll.org/contact>`_.


HTTP API changes 2009/10/14
---------------------------

Correct handling of ``Accept`` header
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We were not doing general handling of the ``Accept`` header on requests
that return their results in a JSON dictionary payload. In particular,
sending ``*/*`` was getting a ``400 (Bad request)`` error, `as reported
<http://bugs.fluidinfo.com/fluiddb/issue15>`_ by `Nicholas Tollervey
<http://ntoll.org/contact>`_.

``500`` error when sending an incorrect value in a new tag description
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We were not doing thorough checking of the types sent for method arguments
passed in a JSON dictionary. For example, passing a JSON ``null`` value as
the description of a new tag would produce a ``500 (Internal server
error)``. This has been fixed - we now check the types of all arguments in
all JSON dict payloads in all requests and responses.

|incompatible| PUT/GET of tag values has been simplified
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

**Note: This change only affects PUT and GET of tag values.**

*Old behavior*: We were using an optional ``format`` argument to allow tag
values to be set and retrieved in a JSON dictionary. The way we were doing
it proved confusing to almost everyone.

*New behavior*: The ``format`` argument is now gone. The caller simply uses
``Content-Type`` header to describe the payload, and the special
content-type value ``application/vnd.fluiddb.value+json`` can be used to
send / receive primitive Fluidinfo values (e.g., boolean, int, etc) as JSON.
On a GET you may (optionally) indicate what types are acceptable using an
``Accept`` header.

*What you need to change*: Anywhere you were using a ``format`` argument,
and anywhere you were making a JSON dictionary with a ``value`` key.

*What you do not need to change*: the general sending of arguments to
methods in JSON dictionaries or receiving method results in a JSON
dictionary. This change *only* affects tag values, i.e., PUT and GET
methods on ``/objects/ns1/ns2/tag``.

To properly understand this change, please take the time to understand the
difference between :ref:`primitive <primitive-values>` and :ref:`opaque
<opaque-values>` values, and then read the section on :ref:`payloads with
tag values <payloads-with-tag-values>`.

Thanks to `Holger Dürer <http://twitter.com/hd42>`_ for pushing us to
reconsider and simplify this behavior.

|incompatible| Error information is now returned in HTTP headers
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

We have changed how Fluidinfo responds when an error occurs.

*Old behavior*: We used to send a JSON dictionary payload with an
``errorClass`` key containing the specific class of error.  This seemed too
heavyweight and it also required the application to have a JSON parser.

*New behavior*: We now send a ``X-FluidDB-Error-Class`` HTTP header. This
contains the same value as was being sent in the JSON ``errorClass`` key.
We also send a ``X-FluidDB-Request-Id`` header to help us locate specifics
of requests.  :ref:`Details <http-error-class>`.

Posting to /objects with "application/json; charset=utf-8"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It was formerly not possible to use an HTTP header of ``Content-type:
"application/json; charset=utf-8"`` when sending a JSON payload with an
``about`` string in creating a new object. This is fixed. Reported by
`Emanuel Carnevale <http://twitter.com/onigiri>`_.

Setting tag value using "text/plain; charset=utf-8"
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Although it was possible to set a string tag value with ``text/plain``
content type, using a charset specifier did not work. This is fixed.
Reported by `Holger Dürer <http://twitter.com/hd42>`_.

Payloads may be omitted when all fields are optional
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When sending methods arguments in a JSON dictionary payload, the payload
was always required - even if all its fields were optional and you didn't
need any of them. This was most obvious in the case of POST on ``/objects``
when no ``about`` value was needed. This has been fixed: the empty JSON
dictionary payload is no longer required.

Adding an instance of a tag to a non-existent object
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Fluidinfo used to return a ``500 (Internal server error)`` when the caller
tried to add a tag to an object id that didn't exist. This has been fixed.
Reported by `Nicholas Radcliffe <http://twitter.com/njr0>`_.

Boolean and null tag values fully supported
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You can now send (PUT) a Boolean and null tag values and GET the value
back. These were formerly causing a ``500 (Internal server error)``.
Reported by `Nicholas Radcliffe <http://twitter.com/njr0>`_.

Unparsable queries causing a 500 error
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Some invalid queries that could not be parsed were causing a ``500
(Internal server error)``.



HTTP API changes 2009/08/24
---------------------------

Payload no longer needed on GET /objects request
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

You no longer need to send a JSON payload when doing a ``GET`` request on
``/objects/ID``. That was a poor design decision; in fact some HTTP
libraries (e.g., .NET) don't even provide for sending a payload with a
``GET``.

Tag paths now properly shown on GET /objects/ID
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

There was a bug, first discovered by `Seo Sanghyeon
<http://twitter.com/sanxiyn>`_, wherein doing a ``GET`` on
``/objects/ID`` did not show the objects tags in the ``tagPaths`` key of
the JSON response. That has now been fixed. See `issue 6
<http://bugs.fluidinfo.com/fluiddb/issue6>`_.

Periods and colons are now legal in namespace and tag names
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

It is now possible to use periods and colons in namespace and tag names.
Hyphen and underscore are also still available, of course, as well as
letters and digits.
