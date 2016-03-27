.. -*- coding: utf-8; -*-

Fluidinfo REST API
==================

This page documents information that is specific to the API.  We try
to adhere to the recommendations of `RFC 2616
<http://www.w3.org/Protocols/rfc2616/rfc2616.html>`_ and to the principles
of `REST <http://en.wikipedia.org/wiki/Representational_State_Transfer>`_.

API host and port
-----------------

.. Note that the host name given below must agree with the fluidDBHost
   variable in fluiddb/common/defaults.py

HTTP access is via ``fluiddb.fluidinfo.com`` on port ``80``. For
secure access via HTTPS, use port ``443``.

Detailed documentation of the HTTP URI hierarchy is provided at
`<http://api.fluidinfo.com/>`_.

Open-source libraries
---------------------

There are many open-source client-side libraries for Fluidinfo. The current
list can be `found on our website
<http://fluidinfo.com/developers/libs>`_. If you want a library for a
language that's not yet supported, why not write it yourself?  We'll be
happy to help. If you're interested, you should definitely check out the
`Fluidinfo Weekend of Code
<http://blogs.fluidinfo.com/fluidinfo/2009/09/17/fluiddb-weekend-of-code/>`_
offer.

API versions
------------

There is only a single version of the Fluidinfo API. It used to be possible
to request different API versions, but seeing as the Fluidinfo API is very
stable it was decided to drop this support in favor of simpler code.

.. _authentication:

Authentication and authorization
--------------------------------

During the alpha of Fluidinfo, applications must use `HTTP Basic
<http://en.wikipedia.org/wiki/Basic_access_authentication>`_ for
authentication. This can be done (insecurely) over a regular HTTP
connection, or securely via HTTPS. Credentials will normally be presented
on each request. If credentials are not sent, the request will be attempted
as the :ref:`anonymous user <anon-user>`.

An application that wants to carry out a particular action on behalf of a
particular Fluidinfo user will need to send that user's credentials.  When a
user gives their credentials to an application, they are allowing the
application to authenticate as them to Fluidinfo and are also authorizing the
application to make changes in Fluidinfo as them.

This is an unsatisfactory arrangement, not suitable for the longer term.
Following the alpha stage of Fluidinfo, we will provide for enhanced
authentication and a fine-grained authorization solution.

In the case of authorization, Fluidinfo has a strong built-in permissions
model on tags and namespaces.  This allows users to grant/restrict
permission for other users to carry out actions. Because applications are
users too, a user can pre-approve the actions that another (an application)
may take on their behalf.  Using this as the basis of an authorization
scheme, a user intending to use an application will visit a Fluidinfo site
to pre-approve an application to act on their behalf.

Unicode namespace and tag names
-------------------------------

The HTTP interface accepts payloads in `JSON <http://www.json.org/>`_. JSON
supports a unicode representation, so if your programming language has a
JSON library you likely will not have to think about unicode issues.

To send a unicode namespace or tag name as part of a URI however, you must
first encode it into a sequence of `UTF-8
<http://en.wikipedia.org/wiki/UTF-8>`_ octets, and then %-encode the result
according to `RFC2396 (section 2.4.1)
<http://www.ietf.org/rfc/rfc2396.txt>`_.

To give a simple example, suppose the Fluidinfo user ``sam`` has a
namespace called ``música``. To add a sub-namespace an application would
POST to ``sam/m%C3%BAsica``. That's because ``ú`` when converted to UTF-8
is the two octet sequence ``\xC3\xBA`` and when that is %-encoded it
becomes the 6-byte sequence ``%C3%BA``.


General request and response payloads
-------------------------------------

*Note: this section does not deal with tag values. For that see below.*

Many HTTP API methods expect to receive their arguments and/or to return
their results in a formatted payload.  Currently, the only supported format
is `JSON <http://www.json.org/>`_.

When sending method arguments in a JSON payload to Fluidinfo you must set the
``Content-Type`` HTTP header of your request to ``application/json``. You
must also send a ``Content-Length`` header containing the number of octets
in the serialized JSON.

If you are calling a method that returns JSON formatted results, you may
send an ``Accept`` header indicating the content types you are willing to
receive. Currently, the only recognized value is ``application/json``.
Seeing as this is also the default, it is also what you will get if you
send no ``Accept`` header or if you send an ``Accept`` header with ``*/*``.

If you make any sort of payload error, you will receive a ``400`` error
status (see below for details).

It is possible to send a checksum of payloads using the ``Content-MD5`` header.
Fluidinfo will check the payload and checksum and if it encounters a mismatch
return a ``412`` (Precondition failed) error. For more information please refer
to `RFC1864 <http://www.ietf.org/rfc/rfc1864.txt>`_ and
`RFC2616 (Section 14.15) <http://www.ietf.org/rfc/rfc2616.txt>`_.

.. _payloads-with-tag-values:

Payloads containing tag values
------------------------------

When doing a PUT or GET involving a tag value (`API details
<http://api.fluidinfo.com/fluidDB/api/*/objects/*>`_) you will use
``Content-Type`` and (optionally, for GET) ``Accept`` headers to specify
details of transmitted tag values. Before reading on, make sure you
understand the difference between *primitive* and *opaque*
:doc:`tag-values`.

Sending a tag value via PUT
^^^^^^^^^^^^^^^^^^^^^^^^^^^

*Primitive values*: To send a primitive tag value, first serialize it
(i.e., the null, boolean, int, float, string, or list of strings you wish
to send) as a single `JSON <http://www.json.org>`_ *value* (use a JSON *array*
in the case of a list of strings).  Many programming languages have a JSON
library available that can do this for you.  Send the JSON in the request
payload and set the ``Content-Length`` header to be the number of octets in
the payload.  To indicate that the payload contains a primitive value, you
must set the ``Content-Type`` header to
``application/vnd.fluiddb.value+json``. JSON is currently the only format
by which you can send a primitive tag value.

.. For convenience, if you omit ``Content-Type`` and also send an empty
   payload, Fluidinfo will set a ``null`` primitive value tag.

*Opaque values*: To send an opaque value, set the ``Content-Type`` header
to whatever is appropriate, put the tag content into the payload, and set
the ``Content-Length`` header to be the number of octets in the payload.
The ``Content-Type`` you use is up to you, as described in the document on
:doc:`tag-values`.

Retrieving a tag value via GET
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When you GET a tag on an object, the response will contain a
``Content-Type`` header to indicate the type of the tag value.

*Primitive values*: The ``Content-Type`` will be set to
``application/vnd.fluiddb.value+json`` and the payload will be a serialized
JSON object.

*Opaque values*: ``Content-Type`` will contain the type that was sent when
the tag was originally added via PUT. I.e., if you PUT an
``application/pdf`` tag onto an object, you will get ``application/pdf``
back on a subsequent GET.  The payload of the response will contain the tag
value.

Using an ``Accept`` header on a GET
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When retrieving tag values, you may *optionally* send an ``Accept`` header
to indicate what kinds of values you are willing to receive from Fluidinfo.
As detailed in `RFC2616
<http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14>`_, sending
no ``Accept`` header is equivalent to setting it to ``*/*``.
Here are some notes on the use of the ``Accept`` header:

* If you want to receive both primitive and opaque tag values and you can
  handle primitive values serialized as JSON, you never need to send an
  ``Accept`` header.

* The default ``Content-Type`` sent with primitive values is
  ``application/vnd.fluiddb.value+json``. It's also currently the *only*
  way to receive a primitive value. If we support another method in the
  future and you prefer that to JSON, you will need to use an ``Accept``
  header to make sure you get what you want.

* If you try to retrieve a tag whose type does not match the ``Accept``
  header in your request, you'll get a ``406 (Not acceptable)`` status.

Some ``Accept`` header examples:

* ``*/*``: accept any content type. Primitive values will be sent as
  serialized JSON objects with a ``Content-Type`` of
  ``application/vnd.fluiddb.value+json``.

* ``application/vnd.fluiddb.value+json``: only accept primitive values, as
  serialized JSON objects.

* ``audio/*``: only accept audio content, of any subtype.

.. _http-slash-values:

Getting the type of primitive tag values
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

When retrieving primitive tag values with a GET request, the response will
contain an ``X-FluidDB-Type`` header containing the type of the
requested value. The possible values for the header are:  ``int``,
``float``, ``boolean``, ``null``, ``string`` and ``list-of-strings``.

The ``X-FluidDB-Type`` header is also returned for HEAD requests for primitive
tag values.

Acting on tag values for objects matching a Fluidinfo query
-----------------------------------------------------------

The /values URI
^^^^^^^^^^^^^^^

Fluidinfo's HTTP API allows clients to act on multiple tag values on
objects with a single request to ``/values``.  Note that additions to the
``/values`` hierarchy are currently being contemplated. Please see the
:doc:`draft-values-spec` for the proposed enhancements.

GET
~~~

A simple way to retrieve multiple tag values is to put a Fluidinfo query and
a set of wanted tags in the URI. For example,

  ``GET /values?query=ali/rating>10&tag=ntoll/seen&tag=ali/met``

will return the values of the ``ntoll/seen`` and ``ali/met`` tags on
objects matching the Fluidinfo query ``ali/rating > 10``.  Note that the
values of tags used in the query will not be returned unless you request
them.

Response format
~~~~~~~~~~~~~~~

The ``GET`` response uses JSON dictionaries as much as possible to allow
for additional information to be compatibly added to results in future API
enhancements.  Below is an example response:

.. code-block:: javascript

  {
      "results" : {
          "id" : {
              "3b76f7b3-f234-4d3e-aabd-b6bd331e0a55" : {
                  "twitter.com/username" : {
                      "value" : "terrycojones"
                  },
                  "twitter.com/uid" : {
                      "value" : 42983,
                  }
              },

              "0a7e56df-3007-4dbc-ba98-4cc4db06ae17" : {
                  "terry/met" : {
                      "value" : false
                  },
                  "esteve/met" : {
                      "value" : true
                  },
                  "ali/friends" : {
                      "value" : [ "sam", "joe", "mary" ]
                  }
              }
          }
      }
  }


*Notes*

#. If an object does not have an instance of a tag mentioned, there will be
   no corresponding key in the dictionary of tags for that object.

#. If a tag value is primitive, the response dictionary will have a
   ``value`` key. If it is an opaque type, it will have ``value-type`` and
   ``size`` keys (but no ``value`` key). If you want to retrieve an opaque
   tag value, you will need to request it separately.

PUT
~~~

To set multiple tag values on objects, give one or more Fluidinfo queries
and their respective tag values in a JSON payload. For example,

  ``PUT /values``

with payload:

.. code-block:: javascript

  {
    "queries" : [
      [ "mike/rating > 5",
        {
          "ntoll/rating" : {
            "value" : 6
          },
          "ntoll/seen" : {
            "value" : true
          }
        }
      ],
      [ "fluiddb/about matches \"great\"",
        {
          "ntoll/rating" : {
            "value" : 10
          }
        }
      ],
      [ "fluiddb/id = \"6ed3e622-a6a6-4a7e-bb18-9d3440678851\"",
        {
          "mike/seen" : {
            "value" : true
        }
      ]
    ]
  }

will first put the given values of ntoll/rating and ntoll/seen onto all
objects matching the Fluidinfo query ntoll/rating > 5, then put the given
value of ntoll/rating onto objects matching the query fluiddb/about matches
"great", and finally update the mike/seen tag on the object with ID
6ed3e622-a6a6-4a7e-bb18-9d3440678851.

DELETE
~~~~~~

A simple way to remove multiple tag values from objects is to give a
Fluidinfo query and a set of tag paths in the URI. For example,

  ``DELETE /values?query=ali/rating>10&tag=ntoll/opinion``

will delete the ``ntoll/opinion`` tag from all objects matching the Fluidinfo
query ``ali/rating > 10``.  To delete the values of multiple tags, simply
repeat the ``tag`` argument in the URI.


.. _http-error-class:

Error information returned in HTTP headers
------------------------------------------

HTTP responses for requests that result in an error will (with one
exception) always contain ``X-FluidDB-Error-Class`` and
``X-FluidDB-Request-Id`` headers. (The exception is with ``401`` errors due
to sending an incorrect username / password combination.)

The ``X-FluidDB-Error-Class`` header will contain the name of the exception
class that was raised in Fluidinfo. The names give a very clear indication of
what went wrong.  The ``X-FluidDB-Error-Class`` header can be your best
guide to what's going on, especially with generic errors such as ``400 (Bad
request)``.

The ``X-FluidDB-Request-Id`` header will contain a unique random id that
you can tell us so we can easily locate logging information associated with
your API request.

Many of the Fluidinfo error classes have additional specific information
associated with them. Additional error information, if any, is returned in
other headers that start with ``X-FluidDB-Request-``.  The current list of
all such additional headers is:
``X-FluidDB-Action``,
``X-FluidDB-Argument``,
``X-FluidDB-Category``,
``X-FluidDB-Fieldname``,
``X-FluidDB-Message``,
``X-FluidDB-Name``,
``X-FluidDB-Path``,
``X-FluidDB-Query``,
``X-FluidDB-Rangetype``,
and
``X-FluidDB-Type``.

For example, a request specifying an unknown tag will receive an
``X-FluidDB-Error-Class`` header with value ``TNonexistentTag`` as well as
an ``X-FluidDB-Path`` header giving the path of the tag from the request.


General information on server status codes
------------------------------------------

The status codes returned by Fluidinfo calls are shown in the detailed `HTTP
API documentation <http://api.fluidinfo.com/>`_.  Here
though are some general comments on HTTP error statuses you might
encounter.

``400 (Bad request)``
^^^^^^^^^^^^^^^^^^^^^

.. Note: if you change the NAME (i.e., title) of this section, you MUST also
   change the addBadRequestPayload method in fluiddb/doc/api/http/apiDoc.py
   which has a link directly to this section.

There are a variety of simple request errors that will trigger a ``400``
error.  These are listed below. In parentheses after each is the value that
will be in the ``X-FluidDB-Error-Class`` header (see above section).

* Omitting a payload when one is required (``MissingPayload``).
* Omitting ``Content-Type`` or ``Content-Length`` headers when sending
  a request with a payload (``NoContentTypeHeader`` or
  ``NoContentLengthHeader``).
* Sending a payload whose length differs from the ``Content-Length`` header
  (``ContentLengthMismatch``).
* Sending a ``Content-Length`` header when there is no payload
  (``UnexpectedContentLengthHeader``).
* Sending an ``Accept`` header with an unknown value when a payload needs
  to be returned (``UnknownAcceptType``).
* Omitting a mandatory payload field / URI argument
  (``PayloadFieldMissing`` / ``MissingArgument``).
* Including an unexpected payload field / URI argument
  (``UnknownPayloadField`` / ``UnknownArgument``).
* Sending a payload in an unparseable format (``MalformedPayload``).
* Sending a payload field or URI argument with an unparseable value
  (``InvalidPayloadField``).
* Requesting an opaque tag value via JSONP (``UnwrappableBlob``).
* Sending a JSON object of unknown type (e.g., a formal JSON *object* whose
  serialization is ``{ "key" : "value"}``) when trying to set a primitive tag
  value on a Fluidinfo object. Instead, send the JSON representing just the
  value of the nul, int, float, bool, string, or list of strings
  (``UnsupportedJSONType``).
* Sending invalid UTF-8 in a URI argument (``InvalidUTF8Argument``).


``411 (Length required)``
^^^^^^^^^^^^^^^^^^^^^^^^^

If you omit a ``Content-Length`` header when sending a payload, you will
receive a ``411``.

``413 (Request entity too large)``
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Fluidinfo puts a limit on the number of objects that a query can return. This
is necessary because without a limit it would be simple to send queries
that returned all objects. The limit protects against accidents and denial
of service attacks.

The current query limit is 1 million objects. If your query (or any
intermediate sub-part of the query) exceeds this number, you will receive a
``413`` error.

.. _CORS_support:

Support for CORS
----------------

Fluidinfo has full support for `Cross-Origin Resource Sharing (CORS)
<http://en.wikipedia.org/wiki/Cross-Origin_Resource_Sharing>`_, which is
the preferred mechanism for allowing Javascript delivered by one server to
make calls to Fluidinfo.

.. _JSONP_support:

Support for JSONP
-----------------

`JSONP <http://en.wikipedia.org/wiki/JSON#JSONP>`_ is a trick that allows
Javascript running in a web browser to obtain data from a server other than
the one from which the browser initially downloaded the Javascript. JSONP
provides a way to get around this *same-origin policy*. As a concrete
example, suppose you visit a site called CoolApps and their HTML page
contains Javascript. Your browser downloads the Javascript and begins to
run it. The same-origin policy thereafter restricts that Javascript to only
making network connections back to the CoolApps site. So if the Javascript
application wants to interact with Fluidinfo, it cannot, unless the CoolApps
site implements a proxy to receive Fluidinfo API calls, pass them on, and
then return something that your browser can understand as Javascript.
That's a lot of work, and it's work that would need to be done by all
Javascript-using sites that wanted to interact with Fluidinfo.

JSONP takes advantage of the browser's willingness to load Javascript
*code* from other sites via the HTML ``script`` tag. If a page contains a
``<script src="http://fluiddb.fluidinfo.com/..."/>`` tag, a browser will
send a ``GET`` request to Fluidinfo, and try to evaluate the result as
Javascript.  With a little help from the Fluidinfo HTTP servers, this small
exception to the same-origin policy can be used to access the entire
Fluidinfo HTTP API.

First of all, the browser is expecting a Javascript result that it can
execute. To enable this, the author of the Javascript app arranges for the
content of the normal reply from Fluidinfo to be passed as an argument to a
Javascript function call. You do this by giving a ``callback`` argument in
the URL. For example, an HTML tag like ``<script
src="http://fluiddb.fluidinfo.com/objects/xxxx/mike/rating?callback=Window.alert"/>``
will result in a response from Fluidinfo with content ``Window.alert(6)`` if
the value of the ``mike/rating`` tag on the object ``xxxx`` is 6 and the
value was readable by everyone (the browser will send no authentication
details to Fluidinfo). Of course the Javascript application programmer will
likely want to call something more useful than ``Window.alert``.

This is a neat trick, but what if you want to do something other than a
``GET`` request?  It's easy: you just specify the HTTP verb you actually
want as another argument in the URL that you provide as the ``src``
tag in your HTML. Continuing our example, to delete the
``mike/rating`` tag, you'd use ``<script
src="http://fluiddb.fluidinfo.com/objects/xxxx/mike/rating?verb=DELETE"/>``. You
can even send a payload along with its length and type. E.g., ``<script
src="http://fluiddb.fluidinfo.com/objects/xxxx/mike/rating?verb=PUT&payload=great&payload-length=5&payload-type=text%2Fplain"/>``. In
addition, the payload can be encoded, in which case the encoding you used
must be specified via a ``payload-encoding`` argument.

Fluidinfo transforms these JSONP requests into normal requests. The
payload-length you send becomes the Content-length header in the
transformed request, payload-encoding becomes Content-encoding, and of
course the decoded payload becomes the payload of the new request.  The
``Content-type`` in the reply to JSONP requests is always set to
``text/javascript`` because that's what the browser will be expecting, as
it is expecting to receive and execute Javascript code.

With JSONP you have access to the entire Fluidinfo API, though there are some
details that must be kept in mind:

* JSONP requests are always subject to :ref:`normal Fluidinfo permissions
  checking <authentication>`. You can use ``<script
  src="http://username:password@fluiddb.example.com/...>`` in your
  requests, but this should be considered an insecure last resort as your
  credentials will be viewable by anyone using your Javascript application.

* If you try to send a large payload it may be truncated by an
  intermediary.  We did a little testing in late 2009 and the limit we ran
  into was about 12K characters in the URL. Note that there is no hard
  limit here, as client-side HTTP libraries may impose their own limit, you
  might be behind a proxy, and the Fluidinfo HTTP servers (based on `Twisted
  <http://twistedmatrix.com>`_) will also impose limitations. Because of
  the possibility of URI truncation, if you send a ``payload`` argument you
  are required to also send a ``payload-length``.

* If you try to get a tag from an object using JSONP and the value of the
  tag turns out to be opaque (see :doc:`tag-values`), you will receive a
  ``400`` error.  That's because it's not always clear how to send back an
  opaque (perhaps binary) tag value in a form suitable for a Javascript
  function call.

Using JSONP in other contexts
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

JSONP can be useful in non-Javascript contexts too. Applications may be
running in restrictive environments (e.g., behind proxies), or may be
constrained to use older HTTP libraries that do not support all HTTP verbs.
In these cases it may be possible to make Fluidinfo API calls using JSONP,
including sending authentication details.
