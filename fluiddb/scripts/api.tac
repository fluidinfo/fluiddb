import logging
import os
import sys

from twisted.application.internet import TCPServer

from fluiddb.application import (
    APIServiceOptions, getConfig, setupApplication, verifyStore)


options = APIServiceOptions()
options.parseOptions(sys.argv[1:])
port, site, application = setupApplication(options)

# Check database health.
logging.info('Checking database health.')
try:
    verifyStore()
except Exception as error:
    logging.error(error)
    logging.critical('Shutting down.')
    sys.exit(1)
else:
    logging.info('Database is up-to-date.')

# Log configuration parameters.
config = getConfig()
logging.info('PID is %s', os.getpid())
logging.info('service/temp-path is %s', config.get('service', 'temp-path'))
logging.info('service/max-threads is %s', config.get('service', 'max-threads'))
logging.info('service/port is %s', config.get('service', 'port'))
logging.info('store/main-uri is %s', config.get('store', 'main-uri'))
logging.info('index/url is %s', config.get('index', 'url'))

# Register the application.
TCPServer(port, site).setServiceParent(application)
