from textwrap import dedent
from net.grinder.script import Test


# We use a module variable to keep count of the test recorded by the grinder.
_testCounter = 1


def test(function):
    """
    Decorator that creates a Grinder Test object for each function
    and instruments it.
    """
    global _testCounter
    description = dedent(function.__doc__).strip()
    testObject = Test(_testCounter, description)
    _testCounter = _testCounter + 1
    testObject.record(function)
    return function
