from testresources import ResourcedTestCase
from twisted.trial.unittest import TestCase


class FluidinfoTestCase(ResourcedTestCase, TestCase):
    """A test case for Twisted code that is compatible with test resources."""

    def setUp(self):
        ResourcedTestCase.setUp(self)
        TestCase.setUp(self)

    def tearDown(self):
        ResourcedTestCase.tearDown(self)
        TestCase.tearDown(self)
