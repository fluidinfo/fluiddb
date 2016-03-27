"""Convert the twitter_users.uid column from TEXT to INTEGER."""


STATEMENTS = [
    """
    ALTER TABLE twitter_users DROP CONSTRAINT twitter_users_uid_key
    """,
    """
    ALTER TABLE twitter_users ALTER COLUMN uid
        SET DATA TYPE INTEGER USING to_number(uid, '9999999999')
    """,
    """
    ALTER TABLE twitter_users ADD UNIQUE (uid)
    """
]


def apply(store):
    print __doc__
    for statement in STATEMENTS:
        print statement
        store.execute(statement)
