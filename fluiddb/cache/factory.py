class CachingAPIFactory(object):
    """Factory creates concrete caching API instances."""

    def users(self):
        """Get a new L{UserAPI} instance."""
        from fluiddb.cache.user import CachingUserAPI
        return CachingUserAPI()

    def objects(self, user):
        """Get a new L{ObjectAPI} instance."""
        from fluiddb.cache.object import CachingObjectAPI
        return CachingObjectAPI(user)

    def namespaces(self, user):
        """Get a new L{NamespaceAPI} instance."""
        from fluiddb.cache.namespace import CachingNamespaceAPI
        return CachingNamespaceAPI(user)

    def tags(self, user):
        """Get a new L{TagAPI} instance."""
        from fluiddb.cache.tag import CachingTagAPI
        return CachingTagAPI(user)

    def tagValues(self, user):
        """Get a new L{TagValueAPI} instance."""
        from fluiddb.cache.value import CachingTagValueAPI
        return CachingTagValueAPI(user)

    def permissions(self, user):
        """Get a new L{PermissionAPI} instance."""
        from fluiddb.cache.permission import CachingPermissionAPI
        return CachingPermissionAPI(user)

    def permissionCheckers(self):
        """Get a new L{PermissionCheckerAPI} instance."""
        from fluiddb.cache.permission import CachingPermissionCheckerAPI
        return CachingPermissionCheckerAPI()

    def recentActivity(self):
        """Get a new L{RecentActivityAPI} instance."""
        from fluiddb.cache.recentactivity import CachingRecentActivityAPI
        return CachingRecentActivityAPI()
