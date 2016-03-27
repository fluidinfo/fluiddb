"""Lowercase all the users in the database."""

from fluiddb.data.user import getUsers
from fluiddb.scripts.commands import setupStore


if __name__ == '__main__':

    store = setupStore('postgres:///fluidinfo', 'main')

    print __doc__

    for user in getUsers():
        if user.username != user.username.lower():
            print 'Fixing user', user.username
            user.username = user.username.lower()

        store.commit()
