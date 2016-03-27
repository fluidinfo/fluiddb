from twisted.internet import defer

servicesExchange = 'fi.serv'

# The 255 constant here is dependant on the AMQP spec. See
# http://dev.lshift.net/tonyg/amqp-june-2007-f2f/
# transport-sig-f2f-spec.with-outline.html
#
# Ideally we'd get the max queue name length on a per-broker basis (which
# could also then be independent of AMQP). But we'd need a broker API
# instance to do that, which would make it much harder to get the dependant
# path name length limit into the documentation.
maxQueueNameLength = 255

coordinatorQueue = '/%s/coordinator' % servicesExchange
coordinatorRequestsQueue = coordinatorQueue + '/requests'

tagsQueue = '/%s/tags' % servicesExchange
tagQueue = tagsQueue + '/tag'


def makeTagQueue(path):
    # ensure that unicode path args are treated correctly
    if isinstance(path, unicode):
        path = path.encode('utf-8')
    return '%s/req/%s' % (tagQueue, path)

namespacesQueue = '/%s/nss' % servicesExchange
namespaceQueue = namespacesQueue + '/ns'


def makeNamespaceQueue(path):
    # Note: path can be the empty string.
    # ensure that unicode path args are treated correctly
    if isinstance(path, unicode):
        path = path.encode('utf-8')
    return '%s/req/%s' % (namespaceQueue, path)


class ThriftQueue(object):

    def __init__(self, queue=None):
        if queue is None:
            queue = defer.DeferredQueue()
        self.queue = queue

    def put(self, value):
        d = defer.Deferred()
        self.queue.put((d, value))
        return d

    def get(self):
        return self.queue.get()
