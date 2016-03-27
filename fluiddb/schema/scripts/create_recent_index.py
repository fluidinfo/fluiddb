"""Creates two indexes to make queries for recent activity faster."""

from fluiddb.scripts.commands import setupStore


if __name__ == '__main__':

    store = setupStore('postgres:///fluidinfo', 'main')
    print 'Creating creator-creation index.'
    store.execute('CREATE INDEX tag_values_creator_creation_idx '
                  'ON tag_values (creator_id, creation_time DESC)')
    store.commit()
    print 'Done'
