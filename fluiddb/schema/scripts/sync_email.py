"""
Sync all the fluiddb/users/email tags with the users email stored in the users
table.
"""
from fluiddb.application import setConfig, setupConfig
from fluiddb.data.user import getUsers
from fluiddb.model.value import TagValueAPI
from fluiddb.scripts.commands import setupStore


if __name__ == '__main__':
    print __doc__

    store = setupStore('postgres:///fluidinfo', 'main')
    setConfig(setupConfig(None))

    superUser = getUsers(usernames=[u'fluiddb']).one()

    values = {}
    for user in getUsers():
        print 'synchronizing', user.username.encode('utf-8')
        if user.email == u'':
            print 'ERROR: user', user.username, 'has an invalid email.'
            user.email = None
        values[user.objectID] = {u'fluiddb/users/email': user.email}
        if len(values) >= 100:
            TagValueAPI(superUser).set(values)
            store.commit()
            values = {}

    TagValueAPI(superUser).set(values)
    store.commit()
    print 'Done.'
