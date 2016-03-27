"""
Rename indexes, foreign key constraints and sequences to match the plural
table names (bug #803390).
"""


ABOUT_TAG_VALUES_STATEMENTS = [
    """
    ALTER INDEX about_tag_value_pkey RENAME TO about_tag_values_pkey
    """,

    """
    ALTER INDEX about_tag_value_value_key RENAME TO about_tag_values_value_key
    """,
]


NAMESPACES_STATEMENTS = [
    """
    ALTER SEQUENCE namespace_id_seq RENAME TO namespaces_id_seq
    """,

    """
    ALTER INDEX namespace_pkey RENAME TO namespaces_pkey
    """,

    """
    ALTER INDEX namespace_object_id_key RENAME TO namespaces_object_id_key
    """,

    """
    ALTER INDEX namespace_path_key RENAME TO namespaces_path_key
    """,

    """
    ALTER TABLE namespaces DROP CONSTRAINT namespace_creator_id_fkey
    """,

    """
    ALTER TABLE namespaces
        ADD CONSTRAINT namespaces_creator_id_fkey
            FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE CASCADE
    """,

    """
    ALTER TABLE namespaces DROP CONSTRAINT namespace_parent_id_fkey
    """,

    """
    ALTER TABLE namespaces
        ADD CONSTRAINT namespaces_parent_id_fkey
            FOREIGN KEY (parent_id) REFERENCES namespaces(id) ON DELETE CASCADE
    """,
]


PERMISSIONS_STATEMENTS = [
    """
    ALTER SEQUENCE permission_id_seq RENAME TO permissions_id_seq
    """,

    """
    ALTER INDEX permission_pkey RENAME TO permissions_pkey
    """,

    """
    ALTER INDEX permission_path_key RENAME TO permissions_path_key
    """,
]


TAGS_STATEMENTS = [
    """
    ALTER SEQUENCE tag_id_seq RENAME TO tags_id_seq
    """,

    """
    ALTER INDEX tag_pkey RENAME TO tags_pkey
    """,

    """
    ALTER INDEX tag_object_id_key RENAME TO tags_object_id_key
    """,

    """
    ALTER INDEX tag_path_key RENAME TO tags_path_key
    """,

    """
    ALTER TABLE tags DROP CONSTRAINT tag_creator_id_fkey
    """,

    """
    ALTER TABLE tags
        ADD CONSTRAINT tags_creator_id_fkey
            FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE CASCADE
    """,

    """
    ALTER TABLE tags DROP CONSTRAINT tag_namespace_id_fkey
    """,

    """
    ALTER TABLE tags
        ADD CONSTRAINT tags_namespace_id_fkey
            FOREIGN KEY (namespace_id) REFERENCES namespaces(id)
                ON DELETE CASCADE
    """,
]


TAG_VALUES_STATEMENTS = [
    """
    ALTER SEQUENCE tag_value_id_seq RENAME TO tag_values_id_seq
    """,

    """
    ALTER INDEX tag_value_pkey RENAME TO tag_values_pkey
    """,

    """
    ALTER INDEX tag_value_tag_id_key RENAME TO tag_values_tag_id_key
    """,

    """
    ALTER INDEX tag_value_object_id_idx RENAME TO tag_values_object_id_idx
    """,

    """
    ALTER TABLE tag_values DROP CONSTRAINT tag_value_creator_id_fkey
    """,

    """
    ALTER TABLE tags
        ADD CONSTRAINT tag_values_creator_id_fkey
            FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE CASCADE
    """,

    """
    ALTER TABLE tag_values DROP CONSTRAINT tag_value_tag_id_fkey
    """,

    """
    ALTER TABLE tag_values
        ADD CONSTRAINT tag_values_tag_id_fkey
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
    """,
]


USER_POLICIES_STATEMENTS = [
    """
    ALTER SEQUENCE user_policy_id_seq RENAME TO user_policies_id_seq
    """,

    """
    ALTER INDEX user_policy_pkey RENAME TO user_policies_pkey
    """,

    """
    ALTER INDEX user_policy_user_id_key RENAME TO user_policies_user_id_key
    """,

    """
    ALTER TABLE user_policies DROP CONSTRAINT user_policy_user_id_fkey
    """,

    """
    ALTER TABLE user_policies
        ADD CONSTRAINT user_policy_user_id_fkey
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    """,
]


USER_STATEMENTS = [
    """
    ALTER SEQUENCE user_id_seq RENAME TO users_id_seq
    """,

    """
    ALTER INDEX user_pkey RENAME TO users_pkey
    """,

    """
    ALTER INDEX user_object_id_key RENAME TO users_object_id_key
    """,

    """
    ALTER INDEX user_username_key RENAME TO users_username_key
    """,
]


def apply(store):
    print __doc__
    for statements in (ABOUT_TAG_VALUES_STATEMENTS, NAMESPACES_STATEMENTS,
                       PERMISSIONS_STATEMENTS, TAGS_STATEMENTS,
                       TAG_VALUES_STATEMENTS, USER_POLICIES_STATEMENTS,
                       USER_STATEMENTS):
        for statement in statements:
            store.execute(statement)
