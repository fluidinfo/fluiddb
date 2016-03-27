from textwrap import dedent

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web import http

from fluiddb.doc.api.http import apiDoc
from fluiddb.doc.api.http.registry import (
    HTTPTopLevel, registry, HTTPUsage, HTTPExample, Argument, Return)
from fluiddb.web.payloads import buildPayload
from fluiddb.web.resource import WSFEResource, NoResource


class RecentActivityResource(WSFEResource):
    """Handler for the C{/recent} API endpoint.

    This handler will delegate the request to different handlers depending on
    the requested sub endpoint. See the L{getChild} for more information.
    """

    allowedMethods = ('GET', 'OPTIONS')
    isLeaf = False

    def getChild(self, name, request):
        """Returns a different L{Resource} depending on the requested child.

         - C{/recent/users} are handled by L{RecentUserActivityResource}.
         - C{/recent/objects} are handled by L{RecentObjectsActivityResource}.
         - C{/recent/about} are handled by L{RecentAboutActivityResource}.

        @param path: A UTF-8 C{str}, describing the child.
        @param request: A C{twisted.web.server.Request} specifying
            meta-information about the request that is being made for the
            child.
        @return: A L{Resource} object able to handle the given child.
        """
        argument = '/'.join(request.postpath)

        if name == '':
            return self
        elif name == 'users':
            return RecentUsersActivityResource(self.facadeClient, self.session)
        elif name == 'objects':
            return RecentObjectsActivityResource(self.facadeClient,
                                                 self.session)
        elif name == 'about':
            return RecentAboutActivityResource(self.facadeClient,
                                               self.session, argument)
        else:
            return NoResource()


class RecentObjectsActivityResource(WSFEResource):
    """Handler for the C{/recent/objects} API endpoint.

    @param session: The L{FluidinfoSession} instance to use while handling a
        request.
    @param facadeClient: A L{Facade} instance.
    """

    allowedMethods = ('GET', 'OPTIONS')
    isLeaf = False

    def getChild(self, name, request):
        """Returns a different L{Resource} depending on the requested child.

        - C{/recent/objects} are handled by L{RecentObjectsActivityResource}.
        - C{/recent/objects/id} are handled by L{RecentObjectActivityResource}.

        @param path: A UTF-8 C{str}, describing the child.
        @param request: A C{twisted.web.server.Request} specifying
            meta-information about the request that is being made for the
            child.
        @return: A L{Resource} object able to handle the given child.
        """
        if name == '':
            return self
        else:
            return RecentObjectActivityResource(self.facadeClient,
                                                self.session, name)

    @inlineCallbacks
    def deferred_render_GET(self, request):
        """Render a response to a C{GET} request to C{recent/objects}

        @param request: A C{twisted.web.server.Request} specifying
            meta-information about the request.
        @return: A C{deferred} which fires with a JSON payload with the
            information about recent activity for the given object.
        """
        usage = registry.findUsage('recent', 'GET',
                                   RecentObjectsActivityResource)
        registry.checkRequest(usage, request)
        query = request.args['query'][0]

        recentActivity = yield self.facadeClient.getRecentActivityForQuery(
            self.session, query)

        body = buildPayload('application/json', recentActivity)
        request.setHeader('Content-length', str(len(body)))
        request.setHeader('Content-type', 'application/json')
        request.setResponseCode(http.OK)
        returnValue(body)


class RecentObjectActivityResource(WSFEResource):
    """Handler for the C{/recent/objects} API endpoint.

    @param session: The L{FluidinfoSession} instance to use while handling a
        request.
    @param facadeClient: A L{Facade} instance.
    @param objectID: An UTF-8 C{str} with the object ID to get recent activity
        for.
    """

    allowedMethods = ('GET', 'OPTIONS')
    isLeaf = True

    def __init__(self, facadeClient, session, objectID):
        WSFEResource.__init__(self, facadeClient, session)
        self.objectID = objectID

    @inlineCallbacks
    def deferred_render_GET(self, request):
        """Render a response to a C{GET} request to C{recent/objects}

        @param request: a C{twisted.web.server.Request} specifying
            meta-information about the request.
        @return: A C{deferred} which fires with a JSON payload with the
            information about recent activity for the given object.
        """
        usage = registry.findUsage('recent', 'GET',
                                   RecentObjectActivityResource)
        registry.checkRequest(usage, request)

        recentActivity = yield self.facadeClient.getRecentObjectActivity(
            self.session, self.objectID)

        body = buildPayload('application/json', recentActivity)
        request.setHeader('Content-length', str(len(body)))
        request.setHeader('Content-type', 'application/json')
        request.setResponseCode(http.OK)
        returnValue(body)


class RecentAboutActivityResource(WSFEResource):
    """Handler for the C{/recent/about} API endpoint.

    @param session: The L{FluidinfoSession} instance to use while handling a
        request.
    @param facadeClient: A L{Facade} instance.
    @param about: An UTF-8 C{str} with the about value of the object to get
        recent activity for.
    """

    allowedMethods = ('GET',)
    isLeaf = True

    def __init__(self, facadeClient, session, about):
        WSFEResource.__init__(self, facadeClient, session)
        self.about = about

    @inlineCallbacks
    def deferred_render_GET(self, request):
        """Render a response to a C{GET} request to C{recent/about}

        @param request: a C{twisted.web.server.Request} specifying
            meta-information about the request.
        @return: A C{deferred} which fires with a JSON payload with the
            information about recent activity for the given object.
        """
        recentActivity = yield self.facadeClient.getRecentAboutActivity(
            self.session, self.about)

        body = buildPayload('application/json', recentActivity)
        request.setHeader('Content-length', str(len(body)))
        request.setHeader('Content-type', 'application/json')
        request.setResponseCode(http.OK)
        returnValue(body)


class RecentUsersActivityResource(WSFEResource):
    """Handler for the C{/recent/users} API endpoint.

    @param session: The L{FluidinfoSession} instance to use while handling a
        request.
    @param facadeClient: A L{Facade} instance.
    """

    allowedMethods = ('GET', 'OPTIONS')
    isLeaf = False

    def getChild(self, name, request):
        """Returns a different L{Resource} depending on the requested child.

        - C{/recent/objects} are handled by L{RecentObjectsActivityResource}.
        - C{/recent/objects/id} are handled by L{RecentObjectActivityResource}.

        @param path: A UTF-8 C{str}, describing the child.
        @param request: A C{twisted.web.server.Request} specifying
            meta-information about the request that is being made for the
            child.
        @return: A L{Resource} object able to handle the given child.
        """
        if name == '':
            return self
        else:
            return RecentUserActivityResource(self.facadeClient,
                                              self.session, name)

    @inlineCallbacks
    def deferred_render_GET(self, request):
        """Render a response to a C{GET} request to C{recent/objects}

        @param request: A C{twisted.web.server.Request} specifying
            meta-information about the request.
        @return: A C{deferred} which fires with a JSON payload with the
            information about recent activity for the given object.
        """
        usage = registry.findUsage('recent', 'GET',
                                   RecentObjectsActivityResource)
        registry.checkRequest(usage, request)
        query = request.args['query'][0]

        recentActivity = yield self.facadeClient.getRecentUserActivityForQuery(
            self.session, query)

        body = buildPayload('application/json', recentActivity)
        request.setHeader('Content-length', str(len(body)))
        request.setHeader('Content-type', 'application/json')
        request.setResponseCode(http.OK)
        returnValue(body)


class RecentUserActivityResource(WSFEResource):
    """Handler for the C{/recent/users} API endpoint.

    @param session: The L{FluidinfoSession} instance to use while handling a
        request.
    @param facadeClient: A L{Facade} instance.
    @param username: An UTF-8 C{str} with the username to get recent activity
        for.
    """

    allowedMethods = ('GET', 'OPTIONS')
    isLeaf = True

    def __init__(self, facadeClient, session, username):
        WSFEResource.__init__(self, facadeClient, session)
        self.username = username

    @inlineCallbacks
    def deferred_render_GET(self, request):
        """Render a response to a C{GET} request to C{recent/users}

        @param request: A C{twisted.web.server.Request} specifying
            meta-information about the request.
        @return: A C{deferred} which fires with a JSON payload with the
            information about recent activity for the given user.
        """
        recentActivity = yield self.facadeClient.getRecentUserActivity(
            self.session, self.username)

        body = buildPayload('application/json', recentActivity)
        request.setHeader('Content-length', str(len(body)))
        request.setHeader('Content-type', 'application/json')
        request.setResponseCode(http.OK)
        returnValue(body)

# API DOCUMENTATION

# GET on  /recent
topLevel = HTTPTopLevel('recent', 'GET')
topLevel.description = dedent("""
    The GET method on recent is used to retrieve information about the latest
    updated tag values on a given object or user.""")
registry.register(topLevel)

# GET on /recent/objects
usage = HTTPUsage('/objects', dedent("""
    To request information on the latest tag values on the objects returned by
    a given query"""))
usage.resourceClass = RecentObjectsActivityResource
usage.addArgument(Argument(
    'query',
    dedent("""
    A query string specifying what sorts of objects to get recent activity for.
    The query language is described <a
    href="http://doc.fluidinfo.com/fluidDB/queries.html">here</a>. You must
    convert your query to UTF-8 and then <a href="http://en.wikipedia.org/wiki
    /Percent-encoding">
     percent-encode</a> it before adding it to the request URI
     """),
    'string',
    default=None,
    mandatory=True))
topLevel.addUsage(usage)

request = dedent("""
    GET /recent/objects?query=has+bob%2Ffollows HTTP/1.1
    Authorization: Basic XXXXXXXX""")
response = dedent("""
    HTTP/1.1 200 OK
    Content-Length: 1027
    Date: Mon, 02 Aug 2010 13:16:09 GMT
    Content-Type: application/json

    [ { "about" : "http://en.wikipedia.org/wiki/Billion_laughs",
        "id" : "63a5413d-2e0f-4078-9c04-00e58a727478",
        "tag" : "bob/like",
        "updated-at" : "2012-02-22T19:21:50.208654",
        "username" : "bob",
        "value" : null
      },
      { "about" : "shake shack",
        "id" : "91ec45ca-31b3-4c26-b480-27985f1ed902",
        "tag" : "terrycojones/image",
        "updated-at" : "2012-02-22T04:18:38.093100",
        "username" : "terrycojones",
        "value" : "http://imgur.com/gallery/c2JdZ"
      },
      { "about" : "https://twitter.com/#!/terrycojones/status/1721...",
        "id" : "f054aa74-21f4-404d-9540-e7de4afda035",
        "tag" : "mike/comment",
        "updated-at" : "2012-02-22T04:03:31.850967",
        "username" : "mike",
        "value" : "I had to annotate my own tweet about annotating tweets."
      },
     { "about" : "http://www.sublimetext.com/",
        "id" : "362f95bd-5429-4a3d-90f7-576860ea7bac",
        "tag" : "ceronman/comment",
        "updated-at" : "2012-02-22T15:00:16.957497",
        "username" : "ceronman",
        "value" : "Very cool text editor."
      }]""")

description = dedent("""
    Retrieve information about recent values on objects followed by bob.""")
usage.addExample(HTTPExample(request, response, description))

usage.addReturn(Return(apiDoc.BAD_REQUEST, 'If no query is given.'))
usage.addReturn(Return(apiDoc.BAD_REQUEST,
                       'The query string was not valid UTF-8.'))
usage.addReturn(Return(apiDoc.BAD_REQUEST,
                       'If the query string could not be parsed.'))
usage.addReturn(Return(apiDoc.BAD_REQUEST,
                       'If the query returns to many objects.'))
usage.addReturn(Return(apiDoc.NOT_FOUND,
                       'If one or more of the tags or namespaces present '
                       'in the query do not exist.'))
usage.addReturn(Return(apiDoc.UNAUTHORIZED,
                       'If the user does not have ' + apiDoc.READ +
                       ' permission on a tag whose value is needed '
                       'to satisfy the query.'))
apiDoc.addOkOtherwise(usage)

# GET on /recent/objects/<id>
usage = HTTPUsage('/objects/' + apiDoc.ID, dedent("""
    To request information on the latest tag values on a particular object
    given its objectID"""))
usage.resourceClass = RecentObjectActivityResource
topLevel.addUsage(usage)

# Example

request = dedent("""
    GET /recent/objects/5a4823a4-26b4-495c-9a29-a1e830a1b153 HTTP/1.1
    Authorization: Basic XXXXXXXX""")

response = dedent("""
    HTTP/1.1 200 OK
    Content-Length: 494
    Date: Mon, 02 Aug 2010 13:16:09 GMT
    Content-Type: application/json

    [ { "about" : "Birds",
        "id" : "5a4823a4-26b4-495c-9a29-a1e830a1b153",
        "tag" : "bob/test",
        "updated-at" : "2012-02-13T17:22:58.389364",
        "username" : "bob",
        "value" : [ "One", "Two", "Three" ]
      },
      { "about" : "Birds",
        "id" : "5a4823a4-26b4-495c-9a29-a1e830a1b153",
        "tag" : "fred/test_ogg",
        "updated-at" : "2012-01-03T23:44:28.463887",
        "username" : "fred",
        "value" : {
            "value-type" : "audio/ogg",
            "size" : 239367
          }
      } ]""")

description = dedent("""
    Retrieve information about recent tag values for the object
    5a4823a4-26b4-495c-9a29-a1e830a1b153.""")

usage.addExample(HTTPExample(request, response, description))
usage.addReturn(Return(apiDoc.BAD_REQUEST, 'If the id is not a valid UUID.'))
apiDoc.addOkOtherwise(usage)

# GET on /recent/about/<about>
usage = HTTPUsage('/about/' + apiDoc.ABOUTSTR, dedent("""
    To request information on the latest tag values on a particular object
    given its %s value""" % apiDoc.ABOUT_TAG))
usage.resourceClass = RecentAboutActivityResource
topLevel.addUsage(usage)

# Example

request = dedent("""
    GET /recent/about/Birds HTTP/1.1
    Authorization: Basic XXXXXXXX""")

response = dedent("""
    HTTP/1.1 200 OK
    Content-Length: 703
    Date: Mon, 02 Aug 2010 13:16:09 GMT
    Content-Type: application/json

    [ { "about" : "Birds",
        "id" : "5a4823a4-26b4-495c-9a29-a1e830a1b153",
        "tag" : "bob/test",
        "updated-at" : "2012-02-13T17:22:58.389364",
        "username" : "bob",
        "value" : [ "One", "Two", "Three" ]
      },
      { "about" : "Birds",
        "id" : "5a4823a4-26b4-495c-9a29-a1e830a1b153",
        "tag" : "fred/film",
        "updated-at" : "2011-12-02T04:21:02.588383",
        "username" : "fred",
        "value" : "The Birds by Alfred Hitchcock"
      } ]""")

description = dedent("""
    Retrieve information about recent tag values on the object "Birds".""")
usage.addExample(HTTPExample(request, response, description))
apiDoc.addOkOtherwise(usage)

# GET on /recent/users
usage = HTTPUsage('/users', dedent("""
    To request information on the latest tag values by the users whose objects
    are returned by a given query"""))
usage.resourceClass = RecentUsersActivityResource
usage.addArgument(Argument(
    'query',
    dedent("""
    A query string specifying what sorts of user objects to get recent activity
    for. The query language is described <a
    href="http://doc.fluidinfo.com/fluidDB/queries.html">here</a>. You must
    convert your query to UTF-8 and then <a href="http://en.wikipedia.org/wiki
    /Percent-encoding">
     percent-encode</a> it before adding it to the request URI
     """),
    'string',
    default=None,
    mandatory=True))
topLevel.addUsage(usage)

request = dedent("""
    GET /recent/object?query=has+bob%2Ffollows HTTP/1.1
    Authorization: Basic XXXXXXXX""")
response = dedent("""
    HTTP/1.1 200 OK
    Content-Length: 1027
    Date: Mon, 02 Aug 2010 13:16:09 GMT
    Content-Type: application/json

    [ { "about" : "http://en.wikipedia.org/wiki/Billion_laughs",
        "id" : "63a5413d-2e0f-4078-9c04-00e58a727478",
        "tag" : "bob/like",
        "updated-at" : "2012-02-22T19:21:50.208654",
        "username" : "bob",
        "value" : null
      },
      { "about" : "shake shack",
        "id" : "91ec45ca-31b3-4c26-b480-27985f1ed902",
        "tag" : "terrycojones/image",
        "updated-at" : "2012-02-22T04:18:38.093100",
        "username" : "terrycojones",
        "value" : "http://imgur.com/gallery/c2JdZ"
      },
      { "about" : "https://twitter.com/#!/terrycojones/status/1721...",
        "id" : "f054aa74-21f4-404d-9540-e7de4afda035",
        "tag" : "mike/comment",
        "updated-at" : "2012-02-22T04:03:31.850967",
        "username" : "mike",
        "value" : "I had to annotate my own tweet about annotating tweets."
      },
     { "about" : "http://www.sublimetext.com/",
        "id" : "362f95bd-5429-4a3d-90f7-576860ea7bac",
        "tag" : "ceronman/comment",
        "updated-at" : "2012-02-22T15:00:16.957497",
        "username" : "ceronman",
        "value" : "Very cool text editor."
      }]""")

description = dedent("""
    Retrieve information about recent values by users followed by bob.""")
usage.addExample(HTTPExample(request, response, description))

usage.addReturn(Return(apiDoc.BAD_REQUEST, 'If no query is given.'))
usage.addReturn(Return(apiDoc.BAD_REQUEST,
                       'The query string was not valid UTF-8.'))
usage.addReturn(Return(apiDoc.BAD_REQUEST,
                       'If the query string could not be parsed.'))
usage.addReturn(Return(apiDoc.BAD_REQUEST,
                       'If the query returns to many objects.'))
usage.addReturn(Return(apiDoc.NOT_FOUND,
                       'If one or more of the tags or namespaces present '
                       'in the query do not exist.'))
usage.addReturn(Return(apiDoc.UNAUTHORIZED,
                       'If the user does not have ' + apiDoc.READ +
                       ' permission on a tag whose value is needed '
                       'to satisfy the query.'))
apiDoc.addOkOtherwise(usage)

# GET on /recent/users/<username>
usage = HTTPUsage('/users/' + apiDoc.USERNAME, dedent("""
    To request information on the latest tag values created or updated by a
    given user."""))
usage.resourceClass = RecentUserActivityResource
topLevel.addUsage(usage)

# Example

request = dedent("""
    GET /recent/users/bob HTTP/1.1
    Authorization: Basic XXXXXXXX""")

response = dedent("""
    HTTP/1.1 200 OK
    Content-Length: 520
    Date: Mon, 02 Aug 2010 13:16:09 GMT
    Content-Type: application/json

    [ { "about" : "american pie",
        "id" : "f6ee212b-c46a-4de6-988f-5a42b89c1e6f",
        "tag" : "bob/rating",
        "updated-at" : "2012-02-14T06:51:13.557860",
        "username" : "bob",
        "value" : 4
      },
      { "about" : "american pie",
        "id" : "f6ee212b-c46a-4de6-988f-5a42b89c1e6f",
        "tag" : "bob/favorite-scene",
        "updated-at" : "2012-02-14T06:50:55.703272",
        "username" : "bob",
        "value" : "http://www.youtube.com/watch?v=Zf_iE5D8nIQ"
      },
      { "about" : "the cake store",
        "id" : "435ba13a-255b-4baf-9609-6caaed72f049",
        "tag" : "bob/lat-long",
        "updated-at" : "2012-02-14T06:44:14.621746",
        "username" : "bob",
        "value" : [ "51.436889", "-0.049438" ]
      } ]""")

description = dedent("""
    Retrieve information about recent tag values created by bob.""")
usage.addExample(HTTPExample(request, response, description))

apiDoc.addUserNotFound(usage)
apiDoc.addOkOtherwise(usage)
