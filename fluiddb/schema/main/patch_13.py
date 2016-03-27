"""Add a new objects table to track updates or deletes to tag values."""


STATEMENTS = [
    """
    CREATE TABLE objects (
        object_id UUID PRIMARY KEY,
        update_time TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'UTC'))
    """,
    """
    GRANT SELECT, UPDATE, INSERT, DELETE
        ON TABLE objects TO fluidinfo
    """,
    """
    INSERT INTO objects(object_id, update_time)
        SELECT object_id, MAX(creation_time) FROM tag_values
        GROUP BY tag_values.object_id;
    """,
]


def apply(store):
    print __doc__
    for statement in STATEMENTS:
        store.execute(statement)
