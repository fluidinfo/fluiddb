"""Logic for commands needed by operators of Fluidinfo."""

from twisted.python.util import sibpath


def getScriptPath(filename):
    """Return the full path of the given script filename."""
    return sibpath(__file__, filename)
