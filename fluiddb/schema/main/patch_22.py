"""
Changes creator_id of fluiddb/about values to fluiddb and adds two more
indexes to tag_values.
"""

STATEMENTS = [
    """
    CREATE INDEX tag_values_creator_id_idx ON tag_values (creator_id)
    """,

    """
    CREATE INDEX tag_values_creation_time_idx
        ON tag_values (creation_time DESC);
    """,
]


def apply(store):
    print __doc__
    for statement in STATEMENTS:
        print statement
        store.execute(statement)
