from fluiddb.api.authentication import FacadeAuthMixin
from fluiddb.api.namespace import FacadeNamespaceMixin
from fluiddb.api.object import FacadeObjectMixin
from fluiddb.api.permission import FacadePermissionMixin
from fluiddb.api.recentactivity import FacadeRecentActivityMixin
from fluiddb.api.tag import FacadeTagMixin
from fluiddb.api.user import FacadeUserMixin
from fluiddb.api.value import FacadeTagValueMixin


class Facade(FacadeAuthMixin, FacadeNamespaceMixin, FacadeObjectMixin,
             FacadePermissionMixin, FacadeTagMixin, FacadeTagValueMixin,
             FacadeUserMixin, FacadeRecentActivityMixin):
    """A shim to integrate the security layer with the web service frontend.

    This is a temporary structure to minimize disruption as we integrate new
    security and model layers with the web service frontend.  In the future,
    we'll refactor the web service frontend to use the security layer directly
    and the infrastructure here will go away.

    @param transact: The L{Transact} instance to use when running functions
        in a transaction thread.
    @param factory: The L{FluidinfoSessionFactory} to use when creating
        sessions.
    """

    def __init__(self, transact, factory):
        self._transact = transact
        self._factory = factory
