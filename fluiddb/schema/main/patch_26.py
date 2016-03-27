"""Creates the tables to store opaque values."""


STATEMENTS = [
    """
    CREATE TABLE opaque_values (
        file_id BYTEA NOT NULL PRIMARY KEY,
        content BYTEA NOT NULL)
    """,

    """
    CREATE TABLE opaque_value_link (
        value_id INTEGER NOT NULL REFERENCES tag_values ON DELETE CASCADE,
        file_id BYTEA NOT NULL REFERENCES opaque_values ON DELETE RESTRICT,
        PRIMARY KEY (value_id, file_id))
    """
]


def apply(store):
    print __doc__
    for statement in STATEMENTS:
        store.execute(statement)
