import re

from twisted.python import log
# from twisted.internet import defer

from txfluiddb.client import _HasPath, Object, Tag

from fluiddb.common.defaults import sep, pathComponentRegex
from fluiddb.common import paths
from fluiddb.common.types_thrift.ttypes import (
    TUsernameTooLong, TInvalidUsername)

#: The maximum allowed username length
maxUsernameLength = 128

_usernameRegex = re.compile('^%s$' % pathComponentRegex, re.U)


def checkUsername(name):
    if len(name) > maxUsernameLength:
        log.msg('Username too long. Len=%d, Type=%s, Value=%r' %
                (len(name), str(type(name)), name))
        raise TUsernameTooLong()
    if _usernameRegex.match(name):
        return
    else:
        log.msg('Username is invalid. Len=%d, Type=%s, Value=%r' %
                (len(name), str(type(name)), name))
        raise TInvalidUsername()


class User(_HasPath):
    """This class would be in txFluidDB, but it's not generally applicable
    to normal FluidDB users (who can't create users).
    """
    collectionName = 'users'

    def __init__(self, username):
        super(User, self).__init__(username)
        self.username = username
        self.uuid = self.name = self.email = None

    def __str__(self):
        return '\n'.join([
            'Username: %r' % self.username,
            'Name: %r' % self.name,
            'Email: %r' % self.email,
            'Id: %r' % self.uuid,
        ])

    @classmethod
    def create(cls, endpoint, username, name, password, email):

        def _parseResponse(response):
            user = cls(username)
            user.uuid = response[u'id']
            user.name = name
            user.email = email
            return user

        data = {'username': username, 'name': name,
                'password': password, 'email': email}
        d = endpoint.submit(endpoint.getRootURL() + User.collectionName,
                            method='POST', data=data)
        return d.addCallback(_parseResponse)

    def delete(self, endpoint):
        url = self.getURL(endpoint, suffix=[self.username])
        return endpoint.submit(url, method='DELETE')

    @classmethod
    def fromObject(cls, endpoint, obj):

        def _parseResponse(username):
            user = cls(username)
            user.uuid = obj.uuid
            return user.update(endpoint)

        d = obj.get(endpoint, Tag(*map(unicode, paths.usernamePath())))
        return d.addCallback(_parseResponse)

    def update(self, endpoint):

        def _addEmail(email):
            self.email = email
            return self

        def _parseResult(result):
            uuid = self.uuid = result[u'id']
            self.name = result[u'name']
            o = Object(uuid)
            d = o.get(endpoint, Tag(*map(unicode, paths.emailPath())))
            return d.addCallback(_addEmail)

        url = self.getURL(endpoint)
        d = endpoint.submit(url=url, method='GET')
        return d.addCallback(_parseResult)


def findUsersByEmail(endpoint, email):
    query = '%s = "%s"' % (sep.join(paths.emailPath()), email)

    def _parseResult(objs):
        return [User.fromObject(endpoint, obj) for obj in objs]

    d = Object.query(endpoint, query)
    return d.addCallback(_parseResult)
