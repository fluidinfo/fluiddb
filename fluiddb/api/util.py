from fluiddb.data.permission import Operation


CATEGORY_AND_ACTION_BY_OPERATION = {
    Operation.CREATE_NAMESPACE: (u'namespaces', u'create'),
    Operation.UPDATE_NAMESPACE: (u'namespaces', u'update'),
    Operation.DELETE_NAMESPACE: (u'namespaces', u'delete'),
    Operation.LIST_NAMESPACE: (u'namespaces', u'list'),
    Operation.CONTROL_NAMESPACE: (u'namespaces', u'control'),
    Operation.UPDATE_TAG: (u'tags', u'update'),
    Operation.DELETE_TAG: (u'tags', u'delete'),
    Operation.CONTROL_TAG: (u'tags', u'control'),
    Operation.WRITE_TAG_VALUE: (u'tag-values', u'write'),
    Operation.READ_TAG_VALUE: (u'tag-values', u'read'),
    Operation.DELETE_TAG_VALUE: (u'tag-values', u'delete'),
    Operation.CONTROL_TAG_VALUE: (u'tag-values', u'control'),
    Operation.CREATE_USER: (u'users', 'create'),
    Operation.DELETE_USER: (u'users', 'delete'),
    Operation.UPDATE_USER: (u'users', 'update'),
    Operation.CREATE_OBJECT: (u'objects', 'create')}


OPERATION_BY_ACTION = {
    (u'namespaces', u'create'): Operation.CREATE_NAMESPACE,
    (u'namespaces', u'update'): Operation.UPDATE_NAMESPACE,
    (u'namespaces', u'delete'): Operation.DELETE_NAMESPACE,
    (u'namespaces', u'list'): Operation.LIST_NAMESPACE,
    (u'namespaces', u'control'): Operation.CONTROL_NAMESPACE,
    (u'tags', u'update'): Operation.UPDATE_TAG,
    (u'tags', u'delete'): Operation.DELETE_TAG,
    (u'tags', u'control'): Operation.CONTROL_TAG,
    # 'create' is provided for backwards compatibility.  The preferred action
    # is 'write'.
    (u'tag-values', u'create'): Operation.WRITE_TAG_VALUE,
    (u'tag-values', u'write'): Operation.WRITE_TAG_VALUE,
    (u'tag-values', u'read'): Operation.READ_TAG_VALUE,
    (u'tag-values', u'delete'): Operation.DELETE_TAG_VALUE,
    (u'tag-values', u'control'): Operation.CONTROL_TAG_VALUE,
}


def getOperation(category, action):
    """Get an L{Operation} value for the given C{category} and C{action}.

    @param category: The category of the operation.
    @param action: The action for the category.
    @return: An L{Operation} value.
    """
    return OPERATION_BY_ACTION[(category, action)]


def getCategoryAndAction(operation):
    """Returns a category and action for a given L{Operation} value.

    @param operation: An L{Operation} value.
    @return: A C{(category, action)} 2-tuple.
    """
    return CATEGORY_AND_ACTION_BY_OPERATION[operation]
