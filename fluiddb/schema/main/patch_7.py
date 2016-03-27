"""
Drop the NOT NULL constraint on the users.email column (issue #1282).
"""


def apply(store):
    print __doc__
    store.execute('ALTER TABLE users ALTER COLUMN email DROP NOT NULL')
