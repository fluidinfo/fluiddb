"""Creates fluiddb/users/role for all the users."""
from fluiddb.application import setConfig, setupConfig
from fluiddb.scripts.commands import setupStore
from fluiddb.data.user import getUsers
from fluiddb.model.user import getUser
from fluiddb.model.value import TagValueAPI

if __name__ == '__main__':
    store = setupStore('postgres:///fluidinfo', 'main')
    setConfig(setupConfig(None))
    print __doc__

    tagValues = TagValueAPI(getUser(u'fluiddb'))

    for user in list(getUsers()):
        print 'Adding role for', user.username
        values = {user.objectID: {u'fluiddb/users/role': unicode(user.role)}}
        tagValues.set(values)
        store.commit()
