import crypt
import random
import uuid

from fluiddb.common.types_thrift.ttypes import (
    TBadArgument, TBadRequest, TUnsatisfiedDependency, TInternalError,
    TPathPermissionDenied, TNonexistentNamespace, TNamespaceNotEmpty,
    TNamespaceAlreadyExists, TNonexistentTag, TParseError,
    TTagAlreadyExists, TNoSuchUser, TUserAlreadyExists,
    TPasswordIncorrect, TInvalidSession, TNoInstanceOnObject,
    TUnknownRangeType, TagRangeType, TInvalidName, TUniqueRangeError)


def dictSubset(d, names):
    '''Return a new dict consisting of the items in d that are in names.'''
    return dict([(key, d[key]) for key in names if key in d])


def generateObjectId():
    return str(uuid.uuid4())


def strToBool(s, default):
    value = unicode(s.lower())
    if value == u'true' or value == u'1':
        return True
    if value == u'false' or value == u'0':
        return False
    return default


# Password hashing code used by the facade in creating new users and by the
# bootstrap code in creating the admin user.
_ALPHABET = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
_ALPHABET_LENGTH = len(_ALPHABET)
_SALT_LENGTH = 8


def hashPassword(password, salt=None):
    if salt is None:
        salt = '$1$' + ''.join([
            _ALPHABET[random.randint(0, _ALPHABET_LENGTH - 1)]
            for _ in range(_SALT_LENGTH)])
    return crypt.crypt(password, salt)


thriftExceptions = {
    TTagAlreadyExists: ('path',),
    TBadArgument: ('message',),
    TBadRequest: ('message',),
    TInternalError: ('message',),
    TInvalidSession: (),
    TNamespaceAlreadyExists: ('path',),
    TNamespaceNotEmpty: ('path',),
    TNoInstanceOnObject: ('path', 'objectId',),
    TNoSuchUser: ('name',),
    TNonexistentTag: ('path',),
    TNonexistentNamespace: ('path',),
    TParseError: ('message', 'query',),
    TPasswordIncorrect: (),
    TPathPermissionDenied: ('category', 'action', 'path',),
    TUniqueRangeError: ('path', 'objectId'),
    TUnknownRangeType: ('rangeType',),
    TUnsatisfiedDependency: ('message',),
    TUserAlreadyExists: ('name',),
    TInvalidName: ('name',),
}

rangeTypeStr = {
    TagRangeType.NORMAL_TYPE: 'normal',
    TagRangeType.VALUELESS_TYPE: 'valueless',
    TagRangeType.UNIQUE_TYPE: 'unique',
    TagRangeType.LIMITED_TYPE: 'limited',
}
