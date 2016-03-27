"""
Create a comments and comment_object_relation tables.
"""

STATEMENTS = [
    """
    CREATE TABLE comments (
        object_id UUID NOT NULL PRIMARY KEY,
        username TEXT NOT NULL,
        creation_time TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'UTC'))
    """,
    """
    GRANT SELECT, UPDATE, INSERT, DELETE
        ON TABLE comments TO fluidinfo
    """,

    """
    CREATE TABLE comment_object_link (
        comment_id UUID NOT NULL REFERENCES comments ON DELETE CASCADE,
        object_id UUID NOT NULL REFERENCES about_tag_values ON DELETE CASCADE,
        PRIMARY KEY (comment_id, object_id))
    """,
    """
    GRANT SELECT, UPDATE, INSERT, DELETE
        ON TABLE comment_object_link TO fluidinfo
    """,
]


def apply(store):
    print __doc__
    for statement in STATEMENTS:
        store.execute(statement)
