import logging

from fluiddb.data.store import getMainStore
from fluiddb.exceptions import FeatureError
from fluiddb.model.namespace import NamespaceAPI
from fluiddb.model.tag import TagAPI
from fluiddb.model.user import UserAPI, getUser


TESTING_DATA = {
    u'users': [
        u'testuser1',
        u'testuser2'],
    u'namespaces': [
        u'fluiddb/testing',
        u'fluiddb/testing/testing',
        u'testuser1/testing',
        u'testuser1/testing/testing',
        u'testuser2/testing',
        u'testuser2/testing/testing'],
    u'tags': [
        u'fluiddb/testing/test1',
        u'fluiddb/testing/test2',
        u'testuser1/testing/test1',
        u'testuser1/testing/test2',
        u'testuser2/testing/test1',
        u'testuser2/testing/test2']
}


def prepareForTesting():
    """
    Create a set of L{User}s, L{Namespace}s and L{Tag}s for testing purposes.
    """
    admin = getUser(u'fluiddb')
    logging.info('Creating testing users.')
    UserAPI().create([(username, 'secret', u'Test user', u'test@example.com')
                      for username in TESTING_DATA[u'users']])
    logging.info('Creating testing namespaces.')
    NamespaceAPI(admin).create([(namespace, u'Used for testing purposes.')
                                for namespace in TESTING_DATA[u'namespaces']])
    logging.info('Creating testing tags.')
    TagAPI(admin).create([(tag, u'Used for testing purposes.')
                          for tag in TESTING_DATA[u'tags']])
    getMainStore().commit()


def removeTestingData():
    """
    Delete L{User}s, L{Namespace}s and L{Tag}s used for testing purposes.
    """
    admin = getUser(u'fluiddb')
    logging.info('Deleting testing tags.')
    result = TagAPI(admin).get(TESTING_DATA[u'tags'])
    if result:
        TagAPI(admin).delete(result.keys())

    logging.info('Deleting testing namespaces.')
    result = NamespaceAPI(admin).get(TESTING_DATA[u'namespaces'])
    # we must delete namespaces one by one, otherwise we'll get NotEmptyError.
    for path in sorted(result.keys(), reverse=True):
        NamespaceAPI(admin).delete([path])

    logging.info('Deleting testing users.')
    result = UserAPI().get(TESTING_DATA[u'users'])
    if result:
        for username in result:
            path = '%s/private' % username
            try:
                NamespaceAPI(admin).delete([path])
            except FeatureError:
                # FIXME This is a bit crap, but it's faster than checking to
                # see if the namespace exists before attempting to delete it.
                continue
    if result:
        UserAPI().delete(result.keys())
    getMainStore().commit()
