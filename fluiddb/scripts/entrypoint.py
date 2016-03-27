"""Bootstrap code starts and runs the Fluidinfo tools and services."""

import sys

from bzrlib.errors import BzrCommandError
from commandant import builtins
from commandant.controller import CommandController

from fluiddb.application import APIServiceOptions
from fluiddb.scripts import commands
from fluiddb.scripts.twistd import runTAC


def runAPI():
    """Start the Fluidinfo API service."""
    runTAC('api.tac', APIServiceOptions())


def runCommand(argv=sys.argv):
    """Run the command named in C{argv}.

    If a command name isn't provided the C{help} command is shown.

    @param argv: A list of command-line arguments.  The first argument should
        be the name of the command to run.  Any further arguments are passed
        to the command.
    @return: The exit code for the command that was invoked.
    """
    if len(argv) < 2:
        argv.append('help')

    controller = CommandController('fluidinfo', '0.1',
                                   'Management tools for Fluidinfo operators.',
                                   'https://launchpad.net/fluidinfo')
    controller.load_module(builtins)
    controller.load_module(commands)
    controller.install_bzrlib_hooks()
    try:
        return controller.run(argv[1:])
    except BzrCommandError as error:
        print error
    except:
        raise
