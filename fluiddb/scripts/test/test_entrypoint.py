import sys
from textwrap import dedent

from commandant.testing.resources import BzrlibHooksResource, StdoutResource

from fluiddb.scripts.entrypoint import runCommand
from fluiddb.testing.basic import FluidinfoTestCase


class RunCommandTest(FluidinfoTestCase):

    resources = [('bzrlib_hooks', BzrlibHooksResource()),
                 ('stdout', StdoutResource())]

    def testRunCommand(self):
        """
        Running C{fluidinfo} without arguments causes the basic help to be
        displayed.
        """
        runCommand(['fluiddb'])
        self.assertEquals(
            dedent("""\
            fluidinfo -- Management tools for Fluidinfo operators.
            https://launchpad.net/fluidinfo

            Basic commands:
              fluidinfo help commands  List all commands
              fluidinfo help topics    List all help topics
            """),
            sys.stdout.getvalue())
