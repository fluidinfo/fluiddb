from twisted.internet import reactor
from twisted.python import log
from twisted.web import client, error


class HTTPError(error.Error):

    def __init__(self, code, message=None, response=None,
                 response_headers=None):
        error.Error.__init__(self, code, message, response)
        self.response_headers = response_headers


class HTTPPageGetter(client.HTTPPageGetter):
    handleStatus_204 = lambda self: self.handleStatus_200()


class HTTPClientFactory(client.HTTPClientFactory):
    protocol = HTTPPageGetter

    def page(self, page):
        if self.waiting:
            self.waiting = 0
            self.deferred.callback((self.status, self.response_headers, page))

    def noPage(self, reason):
        if self.waiting:
            self.waiting = 0
            if isinstance(reason.value, error.Error):
                reason = HTTPError(reason.value.status, reason.value.message,
                                   reason.value.response,
                                   self.response_headers)
            self.deferred.errback(reason)


def _checkCacheControl(result):
    # Make sure there's a cache-control header in every non-failure reply.
    headers = result[1]
    assert 'cache-control' in headers
    assert headers['cache-control'] == ['no-cache'], \
        "Got unexpected cache-control %r." % headers['cache-control']
    return result


def getPage(url, contextFactory=None, *args, **kwargs):
    log.msg('Method: %s' % kwargs.get('method', 'GET'))
    log.msg('URI: %s' % url)
    try:
        log.msg('Headers: %r' % kwargs['headers'])
    except KeyError:
        pass
    try:
        log.msg('Payload: %r' % kwargs['postdata'])
    except KeyError:
        pass
    scheme, host, port, path = client._parse(url)
    factory = HTTPClientFactory(url, *args, **kwargs)
    if scheme == 'https':
        from twisted.internet import ssl
        if contextFactory is None:
            contextFactory = ssl.ClientContextFactory()
        reactor.connectSSL(host, port, factory, contextFactory)
    else:
        reactor.connectTCP(host, port, factory)

    def _eb(failure):
        log.msg('Failed.')
        log.msg(failure)
        return failure

    return factory.deferred.addCallback(_checkCacheControl).addErrback(_eb)
