from storm.locals import Storm, List, Int

from fluiddb.data.store import getMainStore
from fluiddb.data.namespace import Namespace
from fluiddb.data.tag import Tag
from fluiddb.util.constant import Constant, ConstantEnum, EnumBase


class Operation(EnumBase):
    """An enumeration to represent different permission operations.

    @cvar CREATE_NAMESPACE: Create namespaces or tags in a given namespace.
    @cvar UPDATE_NAMESPACE: Change the properties of a namespace.
    @cvar DELETE_NAMESPACE: Delete the namespace, which must be empty.
    @cvar LIST_NAMESPACE: See a list of contained namespaces and tag names.
    @cvar CONTROL_NAMESPACE: Change permissions for a namespace.

    @cvar UPDATE_TAG: Change the properties of the tag.
    @cvar DELETE_TAG: Delete the entire tag and removing it from all objects.
    @cvar CONTROL_TAG: Change permissions for a tag.

    @cvar WRITE_TAG_VALUE: Add a tag to an object, or change an exiting one.
    @cvar READ_TAG_VALUE: Read the value of a tag on an object.
    @cvar DELETE_TAG_VALUE: Remove a tag from an object.
    @cvar CONTROL_TAG_VALUE: Change permissions for a tag-values.

    @cvar CREATE_USER: Create a user.
    @cvar DELETE_USER: Delete a user.
    @cvar UPDATE_USER: Update user details.

    @cvar CREATE_OBJECT: Create an object.

    @cvar TAG_OPERATIONS: A C{list} of all tag related operations.
    @cvar NAMESPACE_OPERATIONS: A C{list} of all namespace related operations.
    @cvar PATH_OPERATIONS: A C{list} of tag and namespace operations.
    @cvar CONTROL_OPERATIONS: A C{list} of all C{CONTROL} operations.
    @cvar ALLOWED_ANONYMOUS_OPERATIONS: A C{list} of operations that a user
        with L{Role.ANONYMOUS} can perform.
    """

    CREATE_NAMESPACE = Constant(1, 'CREATE_NAMESPACE')
    UPDATE_NAMESPACE = Constant(2, 'UPDATE_NAMESPACE')
    DELETE_NAMESPACE = Constant(3, 'DELETE_NAMESPACE')
    LIST_NAMESPACE = Constant(4, 'LIST_NAMESPACE')
    CONTROL_NAMESPACE = Constant(5, 'CONTROL_NAMESPACE')

    UPDATE_TAG = Constant(6, 'UPDATE_TAG')
    DELETE_TAG = Constant(7, 'DELETE_TAG')
    CONTROL_TAG = Constant(8, 'CONTROL_TAG')

    WRITE_TAG_VALUE = Constant(9, 'WRITE_TAG_VALUE')
    READ_TAG_VALUE = Constant(10, 'READ_TAG_VALUE')
    DELETE_TAG_VALUE = Constant(11, 'DELETE_TAG_VALUE')
    CONTROL_TAG_VALUE = Constant(12, 'CONTROL_TAG_VALUE')

    CREATE_USER = Constant(13, 'CREATE_USER')
    DELETE_USER = Constant(14, 'DELETE_USER')
    UPDATE_USER = Constant(15, 'UPDATE_USER')

    CREATE_OBJECT = Constant(17, 'CREATE_OBJECT')

    TAG_OPERATIONS = [UPDATE_TAG, DELETE_TAG, WRITE_TAG_VALUE, READ_TAG_VALUE,
                      DELETE_TAG_VALUE, CONTROL_TAG, CONTROL_TAG_VALUE]

    NAMESPACE_OPERATIONS = [CREATE_NAMESPACE, UPDATE_NAMESPACE,
                            DELETE_NAMESPACE, LIST_NAMESPACE,
                            CONTROL_NAMESPACE]

    PATH_OPERATIONS = TAG_OPERATIONS + NAMESPACE_OPERATIONS

    USER_OPERATIONS = [CREATE_USER, DELETE_USER, UPDATE_USER]

    CONTROL_OPERATIONS = [CONTROL_NAMESPACE, CONTROL_TAG, CONTROL_TAG_VALUE]

    ALLOWED_ANONYMOUS_OPERATIONS = [LIST_NAMESPACE, READ_TAG_VALUE]


class Policy(EnumBase):
    """Permission policy for a given operation.

    @cvar OPEN: Access is granted.
    @cvar CLOSED: Access is denied.
    """
    OPEN = Constant(True, 'OPEN')
    CLOSED = Constant(False, 'CLOSED')


class PermissionBase(object):
    """Base for classes that store permission details.

    Each permission defines access to an entity, such as a L{Namespace} or
    L{Tag}, for a particular L{Operation} and has a L{Policy} that can be open
    or closed.  The L{User.id}s in the exceptions list are excluded from the
    policy.  That is, if a user appears in the list of exceptions and the
    policy is L{Policy.OPEN}, permission for a given operation on a path will
    be denied.  On the other hand, if the permission is L{Policy.CLOSED} and a
    user is in the exceptions list, permission to perform the requested
    operation will be granted.
    """

    def allow(self, operation, userID):
        """Determine if a user can perform an operation.

        @param userID: The L{User.id} of the user requesting access.
        @param operation: The L{Operation} the user wishes to perform.
        @raise RuntimeError: Raised if the operation is not valid for this
            permission.
        @return: C{True} if access is granted or C{False} if access is denied.
        """
        policy, exceptions = self.get(operation)
        return ((policy is Policy.CLOSED and userID in exceptions) or
                (policy is Policy.OPEN and userID not in exceptions))

    def get(self, operation):
        """Get the L{Policy} and exceptions list for an L{Operation}.

        @param operation: The L{Operation} to get values for.
        @raise RuntimeError: Raised if the operation is not valid for this
            permission.
        @return: A C{(Policy, exceptions)} 2-tuple for the specified
            L{Operation}.
        """
        if operation not in self.operations:
            raise RuntimeError('%s is an invalid operation for this '
                               'permission.' % operation)
        policyName = '%sPolicy' % self.operations[operation]
        exceptionsName = '%sExceptions' % self.operations[operation]
        policy = getattr(self, policyName)
        exceptions = getattr(self, exceptionsName)
        return policy, exceptions

    def set(self, operation, policy, exceptions):
        """Update the L{Policy} and exceptions list for an L{Operation}.

        @param operation: The L{Operation} to set values for.
        @param policy: The L{Policy} to set.
        @param exceptions: The L{User.id}s in the exceptions C{list}.
        @raise RuntimeError: Raised if the operation is not valid for this
            permission.
        """
        if operation not in self.operations:
            raise RuntimeError('%s is an invalid operation for this '
                               'permission.' % operation)
        policyName = '%sPolicy' % self.operations[operation]
        exceptionsName = '%sExceptions' % self.operations[operation]
        setattr(self, policyName, policy)
        setattr(self, exceptionsName, exceptions)


class NamespacePermission(Storm, PermissionBase):
    """The permissions for a L{Namespace}.

    A L{NamespacePermission} is initially created with the system-wide default
    permissions for {Namespace} L{Operation}s:

     - L{Operation.CREATE_NAMESPACE} is L{Policy.CLOSED} with the owner of the
       L{Namespace} in the exception list.
     - L{Operation.UPDATE_NAMESPACE} is L{Policy.CLOSED} with the owner of the
       L{Namespace} in the exception list.
     - L{Operation.DELETE_NAMESPACE} is L{Policy.CLOSED} with the owner of the
       L{Namespace} in the exception list.
     - L{Operation.LIST_NAMESPACE} is L{Policy.OPEN} with an empty exception
       list.
     - L{Operation.CONTROL_NAMESPACE} is L{Policy.CLOSED} with the owner of
       the L{Namespace} in the exception list.

    @param userID: The L{User.id} that created the L{Namespace} and, thus,
        this permission.
    @param namespaceID: The L{Namespace.id} to associate permissions with.
    @param createPolicy: The L{Operation.CREATE_NAMESPACE} L{Policy}.
    @param createExceptions: The exceptions for L{Operation.CREATE_NAMESPACE}.
    @param updatePolicy: The L{Operation.UPDATE_NAMESPACE} L{Policy}.
    @param updateExceptions: The exceptions for L{Operation.UPDATE_NAMESPACE}.
    @param deletePolicy: The L{Operation.DELETE_NAMESPACE} L{Policy}.
    @param deleteExceptions: The exceptions for L{Operation.DELETE_NAMESPACE}.
    @param listPolicy: The L{Operation.LIST_NAMESPACE} L{Policy}.
    @param listExceptions: The exceptions for L{Operation.LIST_NAMESPACE}.
    @param controlPolicy: The L{Operation.CONTROL_NAMESPACE} L{Policy}.
    @param controlExceptions: The exceptions for
        L{Operation.CONTROL_NAMESPACE}.
    """

    __storm_table__ = 'namespace_permissions'

    namespaceID = Int('namespace_id', primary=True, allow_none=False)
    createPolicy = ConstantEnum('create_policy', enum_class=Policy,
                                allow_none=False)
    createExceptions = List('create_exceptions', type=Int(), allow_none=False)
    updatePolicy = ConstantEnum('update_policy', enum_class=Policy,
                                allow_none=False)
    updateExceptions = List('update_exceptions', type=Int(), allow_none=False)
    deletePolicy = ConstantEnum('delete_policy', enum_class=Policy,
                                allow_none=False)
    deleteExceptions = List('delete_exceptions', type=Int(), allow_none=False)
    listPolicy = ConstantEnum('list_policy', enum_class=Policy,
                              allow_none=False)
    listExceptions = List('list_exceptions', type=Int(), allow_none=False)
    controlPolicy = ConstantEnum('control_policy', enum_class=Policy,
                                 allow_none=False)
    controlExceptions = List('control_exceptions', type=Int(),
                             allow_none=False)

    operations = {Operation.CREATE_NAMESPACE: "create",
                  Operation.UPDATE_NAMESPACE: "update",
                  Operation.DELETE_NAMESPACE: "delete",
                  Operation.LIST_NAMESPACE: "list",
                  Operation.CONTROL_NAMESPACE: "control"}

    def __init__(self, userID, namespaceID):
        self.namespaceID = namespaceID
        self.set(Operation.CREATE_NAMESPACE, Policy.CLOSED, [userID])
        self.set(Operation.UPDATE_NAMESPACE, Policy.CLOSED, [userID])
        self.set(Operation.DELETE_NAMESPACE, Policy.CLOSED, [userID])
        self.set(Operation.LIST_NAMESPACE, Policy.OPEN, [])
        self.set(Operation.CONTROL_NAMESPACE, Policy.CLOSED, [userID])


def createNamespacePermission(namespace, permissionTemplate=None):
    """Create a L{NamespacePermission}.

    @param namespace: The L{Namespace} to create permissions for.
    @param permissionTemplate: The L{NamespacePermission} to use as a template
        for this one.  By default, permissions are set using the system-wide
        policy.
    @return: A new L{NamespacePermission} instance.
    """
    store = getMainStore()
    permission = NamespacePermission(namespace.creator.id, namespace.id)

    if permissionTemplate:
        for operation in NamespacePermission.operations.iterkeys():
            policy, exceptions = permissionTemplate.get(operation)
            permission.set(operation, policy, exceptions)

    return store.add(permission)


def getNamespacePermissions(paths):
    """Get L{Namespace}s and L{NamespacePermission}s for the specified paths.

    @param paths: A sequence of L{Namespace.path}s to get L{Namespace}s and
        L{NamespacePermission}s for.
    @return: A C{ResultSet} yielding C{(Namespace, NamespacePermission)}
        2-tuples for the specified L{Namespace.path}s.
    """
    store = getMainStore()
    return store.find((Namespace, NamespacePermission),
                      NamespacePermission.namespaceID == Namespace.id,
                      Namespace.path.is_in(paths))


class TagPermission(Storm, PermissionBase):
    """The permissions for a L{Tag}.

    A L{TagPermission} is initially created with the system-wide default
    permissions for {Tag} L{Operation}s:

     - L{Operation.UPDATE_TAG} is L{Policy.CLOSED} with the owner of the
       L{Tag} in the exception list.
     - L{Operation.DELETE_TAG} is L{Policy.CLOSED} with the owner of the
       L{Tag} in the exception list.
     - L{Operation.CONTROL_TAG} is L{Policy.CLOSED} with the owner of the
       L{Tag} in the exception list.
     - L{Operation.WRITE_TAG_VALUE} is L{Policy.CLOSED} with the owner of the
       L{Tag} in the exception list.
     - L{Operation.READ_TAG_VALUE} is L{Policy.OPEN} with an empty exception
       list.
     - L{Operation.CONTROL_TAG_VALUE} is L{Policy.CLOSED} with the owner of
       the L{Tag} in the exception list.

    @param userID: The L{User.id} that created the L{Tag} and, thus, this
        permission.
    @param tagID: The L{Tag.id} to associate permissions with.
    @param updatePolicy: The for the L{Operation.UPDATE_TAG} L{Policy}.
    @param updateExceptions: The exceptions for L{Operation.UPDATE_TAG}.
    @param deletePolicy: The for the L{Operation.DELETE_TAG} L{Policy}.
    @param deleteExceptions: The exceptions for L{Operation.DELETE_TAG}.
    @param controlPolicy: The for the L{Operation.CONTROL_TAG} L{Policy}.
    @param controlExceptions: The exceptions for L{Operation.CONTROL_TAG}.
    @param writeValuePolicy: The for the L{Operation.WRITE_TAG_VALUE}
        L{Policy}.
    @param writeValueExceptions: The exceptions for
        L{Operation.WRITE_TAG_VALUE}.
    @param readValuePolicy: The for the L{Operation.READ_TAG_VALUE} L{Policy}.
    @param readValueExceptions: The exceptions for L{Operation.READ_TAG_VALUE}.
    @param deleteValuePolicy: The for the L{Operation.DELETE_TAG_VALUE}
        L{Policy}.
    @param deleteValueExceptions: The exceptions for
        L{Operation.DELETE_TAG_VALUE}.
    @param controlValuePolicy: The for the L{Operation.CONTROL_TAG_VALUE}
        L{Policy}.
    @param controlValueExceptions: The exceptions for
        L{Operation.CONTROL_TAG_VALUE}.
    """

    __storm_table__ = 'tag_permissions'

    tagID = Int('tag_id', primary=True, allow_none=False)
    updatePolicy = ConstantEnum('update_policy', enum_class=Policy,
                                allow_none=False)
    updateExceptions = List('update_exceptions', type=Int(), allow_none=False)
    deletePolicy = ConstantEnum('delete_policy', enum_class=Policy,
                                allow_none=False)
    deleteExceptions = List('delete_exceptions', type=Int(), allow_none=False)
    controlPolicy = ConstantEnum('control_policy', enum_class=Policy,
                                 allow_none=False)
    controlExceptions = List('control_exceptions', type=Int(),
                             allow_none=False)
    writeValuePolicy = ConstantEnum('write_value_policy', enum_class=Policy,
                                    allow_none=False)
    writeValueExceptions = List('write_value_exceptions', type=Int(),
                                allow_none=False)
    readValuePolicy = ConstantEnum('read_value_policy', enum_class=Policy,
                                   allow_none=False)
    readValueExceptions = List('read_value_exceptions', type=Int(),
                               allow_none=False)
    deleteValuePolicy = ConstantEnum('delete_value_policy', enum_class=Policy,
                                     allow_none=False)
    deleteValueExceptions = List('delete_value_exceptions', type=Int(),
                                 allow_none=False)
    controlValuePolicy = ConstantEnum('control_value_policy',
                                      enum_class=Policy, allow_none=False)
    controlValueExceptions = List('control_value_exceptions', type=Int(),
                                  allow_none=False)

    operations = {Operation.UPDATE_TAG: "update",
                  Operation.DELETE_TAG: "delete",
                  Operation.CONTROL_TAG: "control",
                  Operation.WRITE_TAG_VALUE: "writeValue",
                  Operation.READ_TAG_VALUE: "readValue",
                  Operation.DELETE_TAG_VALUE: "deleteValue",
                  Operation.CONTROL_TAG_VALUE: "controlValue"}

    def __init__(self, userID, tagID):
        self.tagID = tagID
        self.set(Operation.UPDATE_TAG, Policy.CLOSED, [userID])
        self.set(Operation.DELETE_TAG, Policy.CLOSED, [userID])
        self.set(Operation.CONTROL_TAG, Policy.CLOSED, [userID])
        self.set(Operation.WRITE_TAG_VALUE, Policy.CLOSED, [userID])
        self.set(Operation.READ_TAG_VALUE, Policy.OPEN, [])
        self.set(Operation.DELETE_TAG_VALUE, Policy.CLOSED, [userID])
        self.set(Operation.CONTROL_TAG_VALUE, Policy.CLOSED, [userID])


def createTagPermission(tag):
    """Create a L{TagPermission}.

    Permissions are inherited as follows:

     - L{Operation.UPDATE_TAG} inherits its L{Policy} and exceptions list from
       the permissions for L{Operation.UPDATE_NAMESPACE}.
     - L{Operation.DELETE_TAG} inherits its L{Policy} and exceptions list from
       the permissions for L{Operation.DELETE_NAMESPACE}.
     - L{Operation.CONTROL_TAG} inherits its L{Policy} and exceptions list
       from the permissions for L{Operation.CONTROL_NAMESPACE}.
     - L{Operation.WRITE_TAG_VALUE} inherits its L{Policy} and exceptions list
       from the permissions for L{Operation.UPDATE_NAMESPACE}.
     - L{Operation.READ_TAG_VALUE} inherits its L{Policy} and exceptions list
       from the permissions for L{Operation.LIST_NAMESPACE}.
     - L{Operation.DELETE_TAG_VALUE} inherits its L{Policy} and exceptions
       list from the permissions for L{Operation.DELETE_NAMESPACE}.
     - L{Operation.CONTROL_TAG_VALUE} inherits its L{Policy} and exceptions
       list from the permissions for L{Operation.CONTROL_NAMESPACE}.

    @param tag: The L{Tag} to create permissions for.
    @return: A new L{TagPermission} instance.
    """
    store = getMainStore()
    permission = TagPermission(tag.namespace.creator.id, tag.id)
    permissionTemplate = tag.namespace.permission
    if permissionTemplate is not None:
        for operation in TAG_PERMISSION_INHERITANCE_MAP.iterkeys():
            matchingOperation = TAG_PERMISSION_INHERITANCE_MAP.get(operation)
            policy, exceptions = permissionTemplate.get(matchingOperation)
            permission.set(operation, policy, exceptions)
    return store.add(permission)


TAG_PERMISSION_INHERITANCE_MAP = {
    Operation.UPDATE_TAG: Operation.CREATE_NAMESPACE,
    Operation.DELETE_TAG: Operation.CREATE_NAMESPACE,
    Operation.CONTROL_TAG: Operation.CONTROL_NAMESPACE,
    Operation.WRITE_TAG_VALUE: Operation.CREATE_NAMESPACE,
    Operation.READ_TAG_VALUE: Operation.LIST_NAMESPACE,
    Operation.DELETE_TAG_VALUE: Operation.CREATE_NAMESPACE,
    Operation.CONTROL_TAG_VALUE: Operation.CONTROL_NAMESPACE}


def getTagPermissions(paths):
    """Get L{Tag}s and L{TagPermission}s for the specified paths.

    @param paths: A sequence of L{Tag.path}s to get L{Tag}s and
        L{TagPermission}s for.
    @return: A C{ResultSet} yielding C{(Tag, TagPermission)} 2-tuples for the
        specified L{Tag.path}s.
    """
    store = getMainStore()
    return store.find((Tag, TagPermission),
                      TagPermission.tagID == Tag.id,
                      Tag.path.is_in(paths))
