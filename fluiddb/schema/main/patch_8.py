"""Add a creation_time column to the twitter_users table (issue #1289)."""

STATEMENTS = [
    """
    ALTER TABLE twitter_users
        ADD COLUMN creation_time TIMESTAMP NOT NULL
            DEFAULT (now() AT TIME ZONE 'UTC')
    """,
]


def apply(store):
    print __doc__
    for statement in STATEMENTS:
        store.execute(statement)
