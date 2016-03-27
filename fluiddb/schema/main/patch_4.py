"""Drop user_policies table."""


def apply(store):
    store.execute('DROP TABLE user_policies')
