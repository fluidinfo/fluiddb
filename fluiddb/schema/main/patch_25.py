"""
Creates two indexes for the comment_object_relation table.
"""

STATEMENTS = [
    """
    CREATE INDEX comment_object_link_object_id_idx
        ON comment_object_link (object_id)
    """,
    """
    CREATE INDEX comment_object_link_comment_id_idx
        ON comment_object_link (comment_id)
    """,
]


def apply(store):
    print __doc__
    for statement in STATEMENTS:
        store.execute(statement)
