"""
Migrate old opaque values in the file store to the new in-db file-store.
"""
import json
import os
import sys

from fluiddb.data.value import TagValue, createOpaqueValue
from fluiddb.scripts.commands import setupStore

FILESTORE_PATH = '/var/lib/fluidinfo/file-store/file-store/'


def getFilename(fileID):
    """Get the directory of a file in the store.

    @param fileID: Hexdigest of the SHA-256 hash for the desired file.
    @return: The fully-qualified path to the directory on disk.
    """
    pathParts = [fileID[i:i + 2] for i in range(0, 8, 2)]
    filePath = os.path.join(*pathParts)
    return os.path.join(FILESTORE_PATH, filePath, fileID)


if __name__ == '__main__':
    store = setupStore('postgres:///fluidinfo', 'main')
    print __doc__

    result = store.execute("""SELECT id, value FROM tag_values
                              WHERE value LIKE '{%'""")
    for id, value in list(result):
        value = json.loads(str(value))
        if u'file-id' not in value:
            print >>sys.stderr, 'Opaque value already migrated:', id
            continue
        print 'migrating', id, value[u'file-id']
        filename = getFilename(value[u'file-id'])
        try:
            with open(filename, 'rb') as opaqueFile:
                content = opaqueFile.read()
        except IOError:
            print >>sys.stderr, 'File not found:', value[u'file-id']
            continue

        tagValue = store.find(TagValue, TagValue.id == id).one()
        if tagValue is None:
            print >>sys.stderr, 'Tag value', id, 'is none.'
            continue
        tagValue.value = {'mime-type': value['mime-type'],
                          'size': len(content)}
        createOpaqueValue(id, content)
        store.commit()
