from fluiddb.data.namespace import getNamespaces
from fluiddb.data.permission import Operation, Policy
from fluiddb.data.user import getUsers
from fluiddb.model.namespace import NamespaceAPI


def apply(store):
    # Using model code in a patch isn't ideal, but writing this patch with
    # pure SQL will be heinous.
    for user in getUsers():
        if user.username in ('fluiddb', 'anon'):
            continue
        namespaces = NamespaceAPI(user)
        path = '%s/private' % user.username
        if not namespaces.get([path]):
            namespaces.create(
                [(path, u'Private namespace for user %s' % user.username)])
            namespace = getNamespaces(paths=[path]).one()
            permission = namespace.permission
            permission.set(Operation.LIST_NAMESPACE, Policy.CLOSED, [user.id])
