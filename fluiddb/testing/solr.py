import json
import time
from urllib2 import urlopen

from fluiddb.data.store import getMainStore


DIH_POLL_INTERVAL = 0.2
DIH_MAX_RETRIES = 50


def runDataImportHandler(solrURL, clean=True):
    """Run Solr's Data Import Handler

    The DIH indexes all the L{TagValue}s stored in the postgres database.

    @param solrURL: The URL of the Solr Indexing Server.
    @param clean: If true, the DIH will remove all previous documents in the
        Solr index.
    """
    store = getMainStore()
    store.commit()
    clean = str(clean).lower()
    statusURL = solrURL + '/dataimport?wt=json'
    commandURL = statusURL + '&command=full-import&clean=%s' % clean
    urlopen(commandURL)
    importRunning = True
    retries = 0
    while importRunning:
        time.sleep(DIH_POLL_INTERVAL)
        result = json.load(urlopen(statusURL))
        retries += 1
        if retries > DIH_MAX_RETRIES:
            raise RuntimeError('DataImportHandler timeout.')
        if result[u'status'] != u'busy':
            if (u'Time taken' in result[u'statusMessages']
                    or u'Time taken ' in result[u'statusMessages']):
                break
            else:
                raise RuntimeError('DataImportHandler failed: \n%s'
                                   % json.dumps(result, indent=4))
