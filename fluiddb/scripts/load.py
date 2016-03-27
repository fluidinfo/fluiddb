from datetime import datetime, timedelta
import errno
import logging
from multiprocessing import Pool, Queue
from Queue import Empty
from random import choice, randint, random
from string import ascii_letters
import time
from uuid import uuid4

from fom.session import Fluid
from fom.mapping import Namespace, Object


logQueue = Queue()
countQueue = Queue()


def generateLoad(username, password, endpoint, maxConnections):
    """Generate load on a Fluidinfo deployment.

    Single-threaded processes are started to create an endless stream of
    requests against a Fluidinfo deployment.

    @param username: The username to connect as.
    @param password: The password to use.
    @param endpoint: The Fluidinfo API endpoint to make requests against.
    @param maxConnections: The maximum number of concurrent connections to
        open at once.
    """
    logging.info('Starting %d processes', maxConnections)
    pool = Pool(maxConnections, generateData,
                (username, password, endpoint))
    pool.close()
    totalCount = 0
    lastCount = 0
    start = datetime.utcnow()
    while True:
        while True:
            try:
                message, args = logQueue.get(block=False)
            except IOError as error:
                # If we get a system interruption when calling Queue.get an
                # IOError will be raised. We just ignore the error and retry.
                # More information:
                #
                # http://code.activestate.com/lists/python-list/595310/
                if error.errno != errno.EINTR:
                    raise
            except Empty:
                break

            logging.info(message, *args)

        while True:
            try:
                totalCount += countQueue.get(block=False)
            except IOError as error:
                # If we get a system interruption when calling Queue.get an
                # IOError will be raised. We just ignore the error and retry.
                # More information:
                #
                # http://code.activestate.com/lists/python-list/595310/
                if error.errno != errno.EINTR:
                    raise
            except Empty:
                break

        requestCount = totalCount - lastCount
        duration = datetime.utcnow() - start
        if duration > timedelta(seconds=10):
            duration = (duration.seconds * 1000000) + duration.microseconds
            duration = float(duration)
            logging.info(
                'PROGRESS total=%d last=%s time=%0.02fs throughput=%0.02f/s',
                totalCount, requestCount, duration / 1000000.0,
                (requestCount / (duration / 1000000.0)))
            start = datetime.utcnow()
            lastCount = totalCount
        time.sleep(0.1)

    pool.join()


def generateData(username, password, endpoint):
    """Worker function creates random data.

    Requests to create namespaces, tags and values are continuously generated.
    This function never returns.

    @param username: The username to connect as.
    @param password: The password to use.
    @param endpoint: The Fluidinfo API endpoint to make requests against.
    """
    fluidinfo = Fluid(endpoint)
    fluidinfo.login(username, password)
    fluidinfo.bind()

    while True:
        try:
            generateNamespaceData(username)
        except StandardError, e:
            logQueue.put(('ERROR %s' % str(e), ()))


WORDS = ['dazzlement', 'jabberwock', 'witchcraft', 'pawnbroker',
         'thumbprint', 'motorcycle', 'cryptogram', 'torchlight',
         'bankruptcy', 'flugelhorn', 'newfangled', 'jackhammer']


def generateNamespaceData(username):
    """Generate random namespace, tag and tag value data.

    @param username: The username to connect as.
    """
    rootNamespace = Namespace(username)
    name = 'namespace-%s' % ''.join(choice(ascii_letters)
                                    for i in xrange(randint(8, 12)))
    namespace = rootNamespace.create_namespace(name, 'A child namespace')
    logQueue.put(('CREATE_NAMESPACE path=%s/%s', (username, name)))
    countQueue.put(1)

    for tagName in WORDS:
        tag = namespace.create_tag(tagName, 'A tag', False)
        logQueue.put(('CREATE_TAG path=%s/%s/%s', (username, name, tagName)))
        countQueue.put(1)
        for i in range(randint(2, 20)):
            value = getRandomValue()
            about = 'namespace %s tag %s count %d' % (name, tagName, i)
            obj = Object(uuid4(), about=about)
            obj.set(tag.path, value)
            logQueue.put(('CREATE_TAG_VALUE value=%s tag=%s/%s/%s',
                          (value, username, name, tagName)))
            countQueue.put(1)


def getRandomValue():
    """Generate a random tag value.

    @return: A random C{int}, C{float}, C{bool}, C{None}, C{unicode} or
        C{list} value.
    """
    return choice([randint(0, 1024 * 1024), random(), True, choice(WORDS),
                   None, [choice(WORDS) for i in range(randint(1, 12))]])
