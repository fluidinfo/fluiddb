from fluiddb.common.defaults import (
    sep, namespaceCategoryName, tagCategoryName, tagInstanceSetCategoryName)
from fluiddb.common import permissions

# Permission paths.


def permTagNamespacePath(category):
    return sep.join(permissions.permTagNamespacePath(category))


def permTagPolicyPath(category, action):
    return sep.join(permissions.permTagPolicyPath(category, action))


def permTagExceptionsPath(category, action):
    return sep.join(permissions.permTagExceptionsPath(category, action))

# Default permission paths.


def defaultPermTagNamespacePath(category):
    return sep.join(permissions.defaultPermTagNamespacePath(category))


def defaultPermTagPolicyPath(category, action):
    return sep.join(permissions.defaultPermTagPolicyPath(
        category, action))


def defaultPermTagExceptionsPath(category, action):
    return sep.join(permissions.defaultPermTagExceptionsPath(
        category, action))

# The following is the dict of permissions info that the Django view
# passes to the permissions.html template.

permissionsInfo = {
    'allPermTags': [
        sep.join(a) for a in permissions.allPermTagPaths()],
    'allDefaultPermTags': [
        sep.join(a) for a in permissions.allDefaultPermTagPaths()],
    'open': permissions.OPEN,
    'closed': permissions.CLOSED,
    'control': permissions.CONTROL,
    'create': permissions.CREATE,
    'write': permissions.WRITE,
    'delete': permissions.DELETE,
    'list': permissions.LIST,
    'read': permissions.READ,
    'update': permissions.UPDATE,

    'namespaceCategoryName': namespaceCategoryName,
    'tagCategoryName': tagCategoryName,
    'tagInstanceSetCategoryName': tagInstanceSetCategoryName,

    'permTagNamespacePath': permTagNamespacePath,
    'permTagPolicyPath': permTagPolicyPath,
    'permTagExceptionsPath': permTagExceptionsPath,

    'defaultPermTagNamespacePath': defaultPermTagNamespacePath,
    'defaultPermTagPolicyPath': defaultPermTagPolicyPath,
    'defaultPermTagExceptionsPath': defaultPermTagExceptionsPath,
}


### Local Variables:
### eval: (rename-buffer "permissions.py (api)")
### End:
