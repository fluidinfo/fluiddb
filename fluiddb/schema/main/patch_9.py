"""Add a new oauth_consumers table to store consumer keys and secrets."""


STATEMENTS = [
    """
    CREATE TABLE oauth_consumers (
        user_id INTEGER NOT NULL PRIMARY KEY REFERENCES users
            ON DELETE CASCADE,
        secret BYTEA NOT NULL,
        creation_time TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'UTC'))
    """,
    """
    GRANT SELECT, UPDATE, INSERT, DELETE
        ON TABLE oauth_consumers TO fluidinfo
    """,
]


def apply(store):
    print __doc__
    for statement in STATEMENTS:
        store.execute(statement)
