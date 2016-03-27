import sys

from twisted.python.usage import Options
from twisted.scripts.twistd import runApp, ServerOptions

from fluiddb.scripts import getScriptPath


class ServerOptions(ServerOptions):
    """
    Override L{ServerOptions} so that it works when not specifying a TAC file.
    """

    def parseOptions(self, options=None):
        """
        Don't upcall L{ServerOptions.parseOptions}, but L{Options.parseOptions}
        directly.
        """
        if options is None:
            options = sys.argv[1:]
        Options.parseOptions(self, options=options)


def runTAC(filename, options):
    """
    Run the specified TAC C{filename}, which is expected to be in the
    C{fluiddb/scripts} directory.
    """
    path = getScriptPath(filename)
    options['python'] = path
    options.parseOptions()
    runApp(options)
