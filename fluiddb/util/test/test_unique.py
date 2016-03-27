from fluiddb.util.unique import uniqueList
from fluiddb.testing.basic import FluidinfoTestCase


class UniqueListTest(FluidinfoTestCase):
    """Test the function that makes a list unique."""

    def testEmpty(self):
        """The empty list is the empty list when uniqued."""
        self.assertEquals([], uniqueList([]))

    def testSimpleDuplicate(self):
        """A list of two identical things gets reduced to length one."""
        self.assertEquals(['hey'], uniqueList(['hey', 'hey']))

    def testNoDuplicates(self):
        """A list with no duplicates should be untouched."""
        self.assertEquals(['hey', 'you', 'guys'],
                          uniqueList(['hey', 'you', 'guys']))

    def testDuplicatesWithInterveningElement(self):
        """A list with elements A B A should become just A B."""
        self.assertEquals(['A', 'B'], uniqueList(['A', 'B', 'A']))

    def testManyDuplicationsInOrder1234(self):
        """
        A list with duplicates of all of 1 2 3 4 (introduced in that order)
        should become the list 1 2 3 4 with only one of each.
        """
        self.assertEquals([1, 2, 3, 4],
                          uniqueList([1, 2, 1, 2, 3, 1, 2, 4, 1, 3, 2]))

    def testManyDuplicationsInOrder4321(self):
        """
        A list with duplicates of all of 4 3 2 1 (introduced in that order)
        should become the list 4 3 2 1 with only one of each.
        """
        self.assertEquals([4, 3, 2, 1],
                          uniqueList([4, 4, 3, 4, 3, 2, 3, 4, 4, 3, 1, 2, 4]))
