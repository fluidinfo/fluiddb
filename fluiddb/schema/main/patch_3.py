"""
Migrate data from the permissions table to the new namespace_permissions and
tag_permissions tables, and then drop the permissions table (bug #814041).
"""

from collections import defaultdict

from fluiddb.data.permission import (
    NamespacePermission, Operation, Policy, TagPermission)


def apply(store):
    """Patch the database schema.

    @param store: The C{Store} to patch.
    """
    createNamespacePermissionsTable(store)
    createTagPermissionsTable(store)
    migratePermissions(store, 'namespaces', NamespacePermission,
                       Operation.NAMESPACE_OPERATIONS)
    migratePermissions(store, 'tags', TagPermission, Operation.TAG_OPERATIONS)
    store.execute('DROP TABLE permissions')


def createNamespacePermissionsTable(store):
    """Create the C{namespace_permissions} table.

    @param store: The C{Store} to patch.
    """
    statements = [
        """
        CREATE TABLE namespace_permissions (
            namespace_id INTEGER NOT NULL PRIMARY KEY
                REFERENCES namespaces ON DELETE CASCADE,
            create_policy BOOLEAN NOT NULL,
            create_exceptions INTEGER[] NOT NULL,
            update_policy BOOLEAN NOT NULL,
            update_exceptions INTEGER[] NOT NULL,
            delete_policy BOOLEAN NOT NULL,
            delete_exceptions INTEGER[] NOT NULL,
            list_policy BOOLEAN NOT NULL,
            list_exceptions INTEGER[] NOT NULL,
            control_policy BOOLEAN NOT NULL,
            control_exceptions INTEGER[] NOT NULL)
        """,
        """
        GRANT SELECT, UPDATE, INSERT, DELETE
            ON TABLE namespace_permissions TO fluidinfo
        """]
    for statement in statements:
        store.execute(statement)


def createTagPermissionsTable(store):
    """Create the C{tag_permissions} table.

    @param store: The C{Store} to patch.
    """
    statements = [
        """
        CREATE TABLE tag_permissions (
            tag_id INTEGER NOT NULL PRIMARY KEY
                REFERENCES tags ON DELETE CASCADE,
            update_policy BOOLEAN NOT NULL,
            update_exceptions INTEGER[] NOT NULL,
            delete_policy BOOLEAN NOT NULL,
            delete_exceptions INTEGER[] NOT NULL,
            control_policy BOOLEAN NOT NULL,
            control_exceptions INTEGER[] NOT NULL,
            write_value_policy BOOLEAN NOT NULL,
            write_value_exceptions INTEGER[] NOT NULL,
            read_value_policy BOOLEAN NOT NULL,
            read_value_exceptions INTEGER[] NOT NULL,
            delete_value_policy BOOLEAN NOT NULL,
            delete_value_exceptions INTEGER[] NOT NULL,
            control_value_policy BOOLEAN NOT NULL,
            control_value_exceptions INTEGER[] NOT NULL)
        """,
        """
        GRANT SELECT, UPDATE, INSERT, DELETE
            ON TABLE tag_permissions TO fluidinfo
        """]
    for statement in statements:
        store.execute(statement)


def migratePermissions(store, table, permissionClass, operations):
    """Migrate permissions.

    @param store: The C{Store} to migrate.
    @param table: The name of the table containing the protected entity.
    @param permissionClass: The type of permission to migrate data to.
    @param operations: The allowed L{Operation}s for C{permissionClass}.
    """
    values = defaultdict(list)
    result = store.execute("""
        SELECT %(table)s.id, %(table)s.creator_id, permissions.operation,
               permissions.policy, permissions.exceptions
            FROM %(table)s, permissions
            WHERE %(table)s.path = permissions.path
        """ % {'table': table})
    for tagID, userID, operation, policy, exceptions in result:
        operation = getOperation(operation, operations)
        if operation:
            policy = Policy.OPEN if policy else Policy.CLOSED
            values[(tagID, userID)].append((operation, policy, exceptions))

    i = 0
    for (tagID, userID), permissions in values.iteritems():
        permission = permissionClass(userID, tagID)
        for operation, policy, exceptions in permissions:
            permission.set(operation, policy, exceptions)
        store.add(permission)
        i += 1
        if not i % 100:
            store.commit()
    store.commit()


def getOperation(value, operations):
    """Get an L{Operation} from an C{int} representation.

    @param value: The C{int} operation value.
    @param operations: A sequence of possible L{Operation}s to match.
    @return: The matching L{Operation} or C{None} if one isn't available.
    """
    for operation in operations:
        if operation.id == value:
            return operation
