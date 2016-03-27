# All paths that have to do with permissions are in permissions.py

from fluiddb.common import queues
from fluiddb.common.defaults import (
    adminUsername, namespaceCategoryName, tagCategoryName, aboutTagName,
    pathTagName, descriptionTagName, usernameTagName, passwordTagName,
    nameTagName, emailTagName, adminUserNamespaceName,
    activationTokenTagName, createdAtTagName)
from fluiddb.common.types_thrift.ttypes import TInvalidPath

maxPathLength = (queues.maxQueueNameLength -
                 max(len(queues.makeTagQueue('')),
                     len(queues.makeNamespaceQueue(''))))


def checkPath(path):
    if len(path) > maxPathLength:
        raise TInvalidPath()


def aboutPath():
    return [adminUsername, aboutTagName]


def categoryPath(category):
    # TODO: This should really be called categoryPathPath.
    if category == namespaceCategoryName:
        return [adminUsername, category, pathTagName]
    else:
        # This case catches tagCategoryName and
        # defaults.tagInstanceSetCategoryName. We do no error
        # checking.
        return [adminUsername, tagCategoryName, pathTagName]


def categoryDescriptionPath(category):
    if category == namespaceCategoryName:
        return [adminUsername, category, descriptionTagName]
    else:
        # This case catches tagCategoryName and
        # defaults.tagInstanceSetCategoryName. We do no error
        # checking.
        return [adminUsername, tagCategoryName, descriptionTagName]


def usernamePath():
    return [adminUsername, adminUserNamespaceName, usernameTagName]


def namePath():
    return [adminUsername, adminUserNamespaceName, nameTagName]


def passwordPath():
    return [adminUsername, adminUserNamespaceName, passwordTagName]


def emailPath():
    return [adminUsername, adminUserNamespaceName, emailTagName]


def activationTokenPath():
    return [adminUsername, adminUserNamespaceName, activationTokenTagName]


def createdAtPath():
    return [adminUsername, adminUserNamespaceName, createdAtTagName]
