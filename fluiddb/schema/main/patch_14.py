"""Creates an index for the objects.update_time row"""


def apply(store):
    print __doc__
    store.execute('CREATE INDEX objects_update_time_idx '
                  'ON objects (update_time DESC)')
