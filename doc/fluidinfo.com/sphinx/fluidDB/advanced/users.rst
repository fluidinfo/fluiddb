Users
=====

.. _anon-user:


The anonymous user
------------------

Fluidinfo has an anonymous user called ``anon``. When an API request arrives
that doesn't provide authentication credentials, the request is run
as the ``anon`` user.

The ``anon`` user can never perform **create**, **update**, **delete** or
**control** actions. Apart from that, ``anon`` is a normal Fluidinfo user,
subject to normal permissions checking. It is possible for another user to
grant or withold access to the anonymous user by just using ``anon`` in the
exceptions list for an action (see the
`permissions documentation <../permissions.html>`_ for more details).
