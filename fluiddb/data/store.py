"""C{main} store access functions."""

from zope.component import getUtility

from storm.zope.interfaces import IZStorm


def getMainStore():
    """Get a C{Store} instance for the C{main} database.

    @return: A C{Store} instance for the C{main} database or C{None} if a
        C{main} database is not configured.
    """
    zstorm = getUtility(IZStorm)
    return zstorm.get('main')
