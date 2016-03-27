from zope.interface import Attribute, implements

from twisted.web import resource
from twisted.web.guard import BasicCredentialFactory
from twisted.web.resource import IResource
from twisted.cred.error import UnauthorizedLogin
from twisted.cred.portal import IRealm

from fluiddb.common import defaults
from fluiddb.util.oauth_credentials import OAuthCredentialFactory
from fluiddb.util.oauth2_credentials import OAuth2CredentialFactory
from fluiddb.web.objects import ObjectsResource
from fluiddb.web.tags import TagsResource
from fluiddb.web.users import UsersResource
from fluiddb.web.namespaces import NamespacesResource
from fluiddb.web.permissions import PermissionsResource
from fluiddb.web.about import AboutResource
from fluiddb.web.values import ValuesResource
from fluiddb.web.resource import (
    WSFEResource, NoResource, WSFEUnauthorizedResource)
from fluiddb.web.oauth import RenewOAuthTokenResource
from fluiddb.web.oauthecho import OAuthEchoResource
from fluiddb.web.recent import RecentActivityResource
from fluiddb.web.comment import CommentResource


class IWSFEResource(resource.IResource):
    pass


class IFacadeRealm(IRealm):
    facadeClient = Attribute('Facade client')


class WSFERealm(object):

    implements(IFacadeRealm)

    def requestAvatar(self, avatarId, mind, *interfaces):
        if IResource in interfaces:
            return IResource, RootResource(
                self.facadeClient, session=avatarId), lambda: None
        raise NotImplementedError()


class CrossdomainResource(WSFEResource):
    """
    A resource for supporting cross-domain requests.

    See http://www.adobe.com/devnet/articles/crossdomain_policy_file_spec.html
    """

    # XXX Ross Jempson (the Silverlight guy) says this works for him
    #
    # If you change this, you'll need to also change the test_crossdomain.py
    # test too.
    _xmlContents = '''<?xml version="1.0"?>
        <!DOCTYPE cross-domain-policy SYSTEM "http://www.macromedia.com/xml/
        dtds/cross-domain-policy.dtd">
        <cross-domain-policy>
        <allow-http-request-headers-from domain="*" headers="*"/>
        </cross-domain-policy>'''

    def deferred_render_GET(self, req):
        req.setHeader('Content-Type', 'text/xml')
        return str(self._xmlContents)


class RootResource(WSFEResource):

    _resources = {
        defaults.httpObjectCategoryName: ObjectsResource,
        defaults.httpUserCategoryName: UsersResource,
        defaults.httpTagCategoryName: TagsResource,
        defaults.httpNamespaceCategoryName: NamespacesResource,
        defaults.httpPermissionCategoryName: PermissionsResource,
        defaults.httpAboutCategoryName: AboutResource,
        defaults.httpValueCategoryName: ValuesResource,
        defaults.httpCrossdomainName: CrossdomainResource,
        'jsonrpc': CommentResource,
        'recent': RecentActivityResource,
    }

    def getChild(self, path, request):
        if isinstance(self.session, UnauthorizedLogin):
            factories = [BasicCredentialFactory('fluidinfo.com'),
                         OAuthCredentialFactory('fluidinfo.com'),
                         OAuth2CredentialFactory('fluidinfo.com')]
            return WSFEUnauthorizedResource(factories)

        # Add a unique id to the request so we can more easily trace its
        # progress in our log files. Note that we need to put an id on the
        # request even in the case that we're going to return NoResource,
        # as it's all logged.
        request._fluidDB_reqid = self.session.id
        self.session.http.trace(request)
        if path == 'oauthecho':
            return OAuthEchoResource(self.session)
        elif path == 'renew-oauth-token':
            return RenewOAuthTokenResource(self.session)
        try:
            resource = self._resources[path]
        except KeyError:
            return NoResource()
        else:
            return resource(self.facadeClient, self.session)
