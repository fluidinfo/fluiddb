"""
Add a password to the PostgreSQL fluidinfo user so applications that use
TCP (e.g. JDBC) to talk to PostgreSQL can authenticate.
"""

STATEMENTS = [
    """
    ALTER ROLE fluidinfo WITH ENCRYPTED PASSWORD 'fluidinfo'
    """,
]


def apply(store):
    print __doc__
    for statement in STATEMENTS:
        store.execute(statement)
