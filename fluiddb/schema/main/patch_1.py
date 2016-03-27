"""
Rename tables to avoid collisions with PostgreSQL reserved words (bug
#792400).
"""


def apply(store):
    print __doc__
    store.execute('ALTER TABLE "user" RENAME TO users')
    store.execute('ALTER TABLE "namespace" RENAME TO namespaces')
    store.execute('ALTER TABLE tag RENAME TO tags')
    store.execute('ALTER TABLE tag_value RENAME TO tag_values')
    store.execute('ALTER TABLE permission RENAME TO permissions')
    store.execute('ALTER TABLE user_policy RENAME TO user_policies')
    store.execute('ALTER TABLE about_tag_value RENAME TO about_tag_values')
