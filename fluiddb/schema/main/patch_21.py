"""
Use 3000 rows as a sample for the table analyzer to provide more information
to the query planner, this makes queries for the object_id column in the
# tag_values table (such as the one in the DIH) use the index instead of a
# sequential scan, and thus much faster.
"""

STATEMENTS = [
    """
    ALTER TABLE tag_values ALTER COLUMN object_id SET STATISTICS 3000
    """,
    """
    ANALYZE tag_values (object_id)
    """
]


def apply(store):
    print __doc__
    for statement in STATEMENTS:
        print statement
        store.execute(statement)
