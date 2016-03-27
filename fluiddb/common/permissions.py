from fluiddb.common.defaults import (
    adminUsername, namespaceCategoryName,
    tagCategoryName, tagInstanceSetCategoryName,
    defaultNamespaceName, categories)

CREATE = 'create'
WRITE = 'write'
UPDATE = 'update'
DELETE = 'delete'
LIST = 'list'
CONTROL = 'control'
READ = 'read'

allActions = (CREATE, WRITE, UPDATE, DELETE, LIST, CONTROL, READ)

actionsByCategory = {
    namespaceCategoryName: (CREATE, UPDATE, DELETE, LIST, CONTROL),
    tagCategoryName: (UPDATE, DELETE, CONTROL),
    tagInstanceSetCategoryName: (WRITE, READ, DELETE, CONTROL),
}

CLOSED = 'closed'
OPEN = 'open'

policyAttrName = 'policy'
exceptionsAttrName = 'exceptions'
permissionNamespaceName = 'permission'


def categoryActionPairs():
    for category in (namespaceCategoryName,
                     tagCategoryName,
                     tagInstanceSetCategoryName):
        for action in actionsByCategory[category]:
            yield category, action


def allPermTagPaths():
    for category in categories:
        for action in actionsByCategory[category]:
            yield permTagPolicyPath(category, action)
            yield permTagExceptionsPath(category, action)


def allDefaultPermTagPaths():
    for category in categories:
        for action in actionsByCategory[category]:
            yield defaultPermTagPolicyPath(category, action)
            yield defaultPermTagExceptionsPath(category, action)


def exceptionPathFromPolicyPath(path):
    assert path[-1] == policyAttrName
    return path[:-1] + [exceptionsAttrName]


def isPermissionPath(path):
    """Return True for any path that is under the top-level of the
    permissions mamespace. Note that we don't test if the path exists, or
    is a namespace or tag. We don't care."""
    return (len(path) > 2 and
            path[0] == adminUsername and
            path[1] in categories and
            path[2] == permissionNamespaceName)


# Paths to permissions policy and exceptions tags. These tags
# hold the policy/exceptions for namespaces, tags, and tag
# instance sets. They sit on the object associated with the namespace,
# tag, or tag instance set.


def permTagNamespacePath(category):
    return [adminUsername, category, permissionNamespaceName]


def permTagPath(category, action):
    # We do not check to see if the action is valid for the category.
    return permTagNamespacePath(category) + [action]


def permTagPolicyPath(category, action):
    return permTagPath(category, action) + [policyAttrName]


def permTagExceptionsPath(category, action):
    return permTagPath(category, action) + [exceptionsAttrName]

# Paths to new user default policy and exceptions permission tags.
# These are the tags used to set a brand new user's permission
# defaults.  An instance of these lives on the admin user's object and the
# values are copied onto the new user's object, and assigned to the normal
# (above) tags. If you follow that, you'll see that there is only one
# instance of these tags in the whole of FluidDB - on the admin
# user's object.


def defaultPermTagNamespacePath(category):
    return [adminUsername, defaultNamespaceName, category,
            permissionNamespaceName]


def defaultPermTagPath(category, action):
    # We do not check to see if the action is valid for the category.
    return defaultPermTagNamespacePath(category) + [action]


def defaultPermTagPolicyPath(category, action):
    return defaultPermTagPath(category, action) + [policyAttrName]


def defaultPermTagExceptionsPath(category, action):
    return defaultPermTagPath(category, action) + [exceptionsAttrName]
