import random

from fluiddb.common import users


class RandomUser(object):

    def __init__(self, username=None, password=None, name=None, email=None):
        n = random.randint(0, 1e9)
        if username is None:
            username = 'fred-%d' % n
            assert len(username) <= users.maxUsernameLength, \
                'Username %r is too long.' % username
        self.username = username
        self.password = password if password else 'pwd-%d' % n
        self.name = name if name else 'name-%d' % n
        self.email = email if email else 'email@host%d.com' % n
