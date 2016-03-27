"""
This module monkeypatches the httplib2 Http.request method to use Grinder's
HTTPRequest class.
"""

import httplib2
from net.grinder.plugin.http import HTTPRequest
from HTTPClient import NVPair
from jarray import array, zeros


class ResponseSurrogate(dict):
    """
    Surrogate for the httplib2 response object.
    """

    status = 0


class HttpSurrogate(HTTPRequest):
    """
    Simple surrogate for the httplib2 request object. It only replaces the
    request method using net.grinder.plugin.http.HTTPRequest.
    """

    def request(self, url, method, payload, headers):

        if payload is None:
            payload = zeros(0, 'b')
        else:
            payload = array(payload, 'b')

        headers = [NVPair(key, value) for key, value in headers.iteritems()]
        headers = array(headers, NVPair)

        query = zeros(0, NVPair)

        if method == 'DELETE':
            response = self.DELETE(url, headers)

        elif method == 'GET':
            response = self.GET(url, query, headers)

        elif method == 'HEAD':
            response = self.HEAD(url, query, headers)

        elif method == 'OPTIONS':
            response = self.OPTIONS(url, payload, headers)

        elif method == 'POST':
            response = self.POST(url, payload, headers)

        elif method == 'PUT':
            response = self.PUT(url, payload, headers)

        elif method == 'TRACE':
            response = self.TRACE(url, headers)
        else:
            raise ValueError('Unsported Method')

        content = response.getText()

        responseObj = ResponseSurrogate()
        responseObj.status = response.getStatusCode()

        headersEnumeration = response.listHeaders()

        while headersEnumeration.hasMoreElements():
            key = headersEnumeration.nextElement().lower()
            responseObj[key] = response.getHeader(key)

        return responseObj, content


def registerHook():
    httplib2.OldHttp = httplib2.Http
    httplib2.Http = HttpSurrogate


def unregisterHook():
    httplib2.Http = httplib2.OldHttp
