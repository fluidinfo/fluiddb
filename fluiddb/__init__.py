"""Fluidinfo is an online information storage and search platform.

Its design supports shared openly-writable metadata of any type and about
anything, provides modern writable APIs, and allows data to be branded with
domain names.  The code base contains the logic for a stateless API service,
as well as for operational tools to automate deployment, manage the database,
manage the index, etc.  The main logic for Fluidinfo is in several packages
that form a stack of layers, each with a distinct function:

 - L{fluiddb.data} is at the bottom of the stack and contains low-level data
   access logic for validating and managing data in the database and the
   index.

 - L{fluiddb.model} uses the functionality provided by the data layer to
   provide batch-oriented access to data in the system.  It contains the
   business logic for Fluidinfo and exposes it in the form of L{UserAPI},
   L{ObjectAPI}, L{NamespaceAPI}, L{TagAPI}, L{TagValueAPI}, L{PermissionAPI}
   and L{UserPolicyAPI} classes.

 - L{fluiddb.cache} caches the results produced by the model layer and exposes
   them to the security layer.  For all intents and purposes, this layer
   provides the same APIs as the model layer, and should be indistinguishable
   (other than it should provide a nice performance boost).

 - L{fluiddb.security} is a proxy layer for the model layer that performs
   security checks before allowing calls to propagate down the stack.  It
   provides access to the model in the form of L{SecureUserAPI},
   L{SecureObjectAPI}, L{SecureNamespaceAPI}, L{SecureTagAPI},
   L{SecureTagValueAPI}, L{SecurePermissionAPI} and L{SecureUserPolicyAPI}
   classes.

 - L{fluiddb.api} contains a L{Facade<fluiddb.api.facade.Facade>}
   implementation that is compatible with the web-service frontend.  The
   functionality that translates requests into secure model requests resides
   here.

 - L{fluiddb.web} is the web-service frontend.  It contains logic related to
   handling HTTP requests and dispatching them to the correct method on the
   L{Facade<fluiddb.api.facade.Facade>}.

The L{fluiddb.application} module contains the startup logic used to bootstrap
an instance of the API service.  Several other packages provide supporting
functionality:

 - L{fluiddb.query} contains the query grammar and the logic needed to parse
   a query string into an abstract syntax tree.

 - L{fluiddb.schema} contains the SQL statements and database patches needed
   to create the schema in the database.

 - L{fluiddb.scripts} contains operational tools in the form of
   L{fluiddb.scripts.commands} that can be used to manage Fluidinfo
   deployment, manage the database schema, manage users, etc.

 - L{fluiddb.testing} provides testing tools in the form of test resources
   that can be used to easily prepare the database, the index, capture
   logging, etc. and in the form of test doubles that can be used in place
   of real implementations to make testing easier or more complete.

 - L{fluiddb.util} provides functionality that isn't particularly
   Fluidinfo-specific, but is needed nonetheless.  The code here could
   probably be moved out of Fluidinfo into a standalone project.
"""
