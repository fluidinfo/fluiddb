import json
import random

from fluiddb.common import error, util
from fluiddb.common.defaults import contentTypeForPrimitiveJSON


def _sendBody(request, body, contentType):
    request.setHeader('content-type', contentType)
    request.setHeader('content-length', str(len(body)))
    request.write(body)
    request.finish()


def getBooleanArg(request, argName, default):
    'Get a Boolean argument out of HTTP request arguments.'
    values = request.args.get(argName)
    if values is None:
        return default
    else:
        n = len(values)
        if n == 0:
            # This should never happen. If a request looks like
            # GET /blah?argument
            # where argument is not give a value (e.g. argument=True),
            # then 'argument' will not be in request.args so the
            # request.args.get above will have returned None.
            raise error.InternalError(
                '%s request on %s arg get for %r returned zero length.' %
                (request.method, request.uri, argName))
        elif n == 1:
            return util.strToBool(values[0], default)
        else:
            raise error.MultipleArgumentValues(argName)


def buildHeader(name):
    return "X-FluidDB-%s" % name


def requestId():
    return ''.join([chr(ord('a') + random.randrange(0, 26))
                    for _ in range(16)])


def _serializePrimitiveToJSON(value):
    if type(value) is set:
        value = list(value)
    return json.dumps(value)

primitiveTypeSerializer = {
    contentTypeForPrimitiveJSON: _serializePrimitiveToJSON,
}
