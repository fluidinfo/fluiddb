import json
import re
import types

from hashlib import md5
import base64

from twisted.python import log

from fluiddb.common import error, defaults

CONTENT_TYPE_RE = re.compile(
    '\s*([\w\d-]+/[\w\d-]+)\s*(?:;?\s*charset=([\w\d-]+);?)?', re.UNICODE)


def checkPayloadFieldType(value, field, strCountsAsUnicode=False):
    if field.mayBeNone and value is None:
        return True
    ft = field.type
    vt = type(value)
    if ft in (bool, int, float, types.NoneType):
        return vt is ft
    elif ft is unicode:
        return (vt is unicode or
                (strCountsAsUnicode and vt is str) or
                (value is None and field.mayBeNone))
    elif ft is list:
        if vt is not list:
            return False
        if field.listType is unicode and strCountsAsUnicode:
            return all([isinstance(x, basestring) for x in value])
        else:
            return all([type(x) is field.listType for x in value])
    return False


def identityPayloadDecoder(data):
    return data


def base64PayloadDecoder(data):
    return base64.standard_b64decode(data)


class PayloadDecoder(object):
    decoders = {
        None: identityPayloadDecoder,
        'identity': identityPayloadDecoder,
        'base64': base64PayloadDecoder,
    }

    @classmethod
    def extract(cls, contentEncoding, data):
        decoder = cls.decoders[contentEncoding]
        return decoder(data)


def extractPayload(request):
    """
    Extract and return the payload from an HTTP request, checking for
    content-length header errors along the way. If the payload is encoded
    in some way (indicated by a 'content-encoding' header in the request)
    it is decoded before being returned.

    @param request: The request instance containing the payload.
    """
    try:
        # If we can't seek in the content, the only explanation (that we
        # know of so far) is that client has gone away.
        request.content.seek(0, 0)
    except ValueError:
        log.msg('Request %s: Could not seek in content. Client disconnected?' %
                request._fluidDB_reqid)
        raise error.ContentSeekError()

    data = request.content.read()
    contentLength = request.getHeader('content-length')

    if contentLength is None:
        if data:
            raise error.ContentLengthMismatch()
        else:
            return None
    else:
        contentLength = int(contentLength)

        if data:
            if len(data) != contentLength:
                raise error.ContentLengthMismatch()
            else:
                # Check if we have a Content-MD5 header and if it doesn't
                # validate the content throw a error.ContentChecksumMismatch,
                # which results in a PRECONDITION_FAIL error (412)
                contentMD5 = request.getHeader('content-md5')
                if contentMD5:
                    dataDigest = md5(data).digest()
                    encodedDigest = base64.standard_b64encode(dataDigest)
                    if encodedDigest != contentMD5:
                        raise error.ContentChecksumMismatch()
                contentEncoding = request.getHeader('content-encoding')
                if contentEncoding is None:
                    return data
                else:
                    return PayloadDecoder.extract(contentEncoding, data)
        else:
            if contentLength == 0:
                return ''
            else:
                raise error.ContentLengthMismatch()


def parseJSONPayload(data, charset=defaults.charset):
    # TODO: add support for different charsets
    try:
        return json.loads(data.decode(charset))
    except ValueError:
        raise error.MalformedPayload("Error trying to decode JSON payload")

_payloadParsers = {
    'application/json': parseJSONPayload,
}


def parsePayload(usage, request, payload):
    contentType = request.getHeader('content-type')
    if contentType is None:
        raise error.NoContentTypeHeader()
    contentType, charset = CONTENT_TYPE_RE.match(contentType).groups()

    usagePayload = usage.requestPayloads.get(contentType)
    if usagePayload is None:
        raise error.UnknownContentType()

    # Use default charset (utf-8)
    if charset is None:
        charset = defaults.charset

    formatParser = _payloadParsers.get(contentType)
    if formatParser is None:
        raise NotImplementedError(
            'Parser not implemented for payload type %r!' % contentType)

    dictionary = formatParser(payload, charset=charset)
    if type(dictionary) is not dict:
        raise error.MalformedPayload("Parsed payload is not a dictionary")
    return ParsedDictPayload(dictionary, usagePayload)


class ParsedDictPayload(object):

    def __init__(self, dictionary, usagePayload):
        self.dictionary = dictionary
        self.usagePayload = usagePayload

_payloadBuilders = {
    'application/json': json.dumps,
}


def buildPayload(responseType, responseDictionary):
    try:
        builder = _payloadBuilders[responseType]
    except KeyError:
        raise error.NotAcceptable()
    else:
        return builder(responseDictionary)
