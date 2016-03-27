class APIFactory(object):
    """Factory creates concrete model API instances."""

    def users(self):
        """Get a new L{UserAPI} instance."""
        from fluiddb.model.user import UserAPI
        return UserAPI()

    def objects(self, user):
        """Get a new L{ObjectAPI} instance."""
        from fluiddb.model.object import ObjectAPI
        return ObjectAPI(user)

    def namespaces(self, user):
        """Get a new L{NamespaceAPI} instance."""
        from fluiddb.model.namespace import NamespaceAPI
        return NamespaceAPI(user)

    def tags(self, user):
        """Get a new L{TagAPI} instance."""
        from fluiddb.model.tag import TagAPI
        return TagAPI(user)

    def tagValues(self, user):
        """Get a new L{TagValueAPI} instance."""
        from fluiddb.model.value import TagValueAPI
        return TagValueAPI(user)

    def permissions(self, user):
        """Get a new L{PermissionAPI} instance."""
        from fluiddb.model.permission import PermissionAPI
        return PermissionAPI(user)

    def permissionCheckers(self):
        """Get a new L{PermissionCheckerAPI} instance."""
        from fluiddb.model.permission import PermissionCheckerAPI
        return PermissionCheckerAPI()

    def recentActivity(self):
        """Get a new L{RecentActivityAPI} instance."""
        from fluiddb.model.recentactivity import RecentActivityAPI
        return RecentActivityAPI()
