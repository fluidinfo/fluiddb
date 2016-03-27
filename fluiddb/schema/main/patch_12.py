"""Convert the fluidinfo.com user to a user manager."""


def apply(store):
    print __doc__
    store.execute("UPDATE users SET role = 4 WHERE username = 'fluidinfo.com'")
