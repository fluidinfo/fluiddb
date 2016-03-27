from string import letters, digits

from fluiddb.data.path import (
    getPathName, getParentPath, getParentPaths, isValidPath)
from fluiddb.testing.basic import FluidinfoTestCase


class GetParentPathTest(FluidinfoTestCase):

    def testGetParentPathWithRootPath(self):
        """
        L{getParentPath} returns C{None} if the path is a root-level path.
        """
        self.assertIdentical(None, getParentPath(u'foo'))

    def testGetParentPath(self):
        """
        L{getParentPath} returns the parent path for non-root-level paths.
        """
        self.assertEqual(u'foo', getParentPath(u'foo/bar'))
        self.assertEqual(u'foo/bar', getParentPath(u'foo/bar/baz'))


class GetParentPathsTest(FluidinfoTestCase):

    def testGetParentPathsWithRootPath(self):
        """L{getParentPaths} ignores root-level paths."""
        self.assertEqual(set(), getParentPaths([u'foo']))

    def testGetParentPaths(self):
        """
        L{getParentPaths} returns a set of parent paths for the non-root-level
        paths.
        """
        self.assertEqual(set([u'bar', u'baz']),
                         getParentPaths([u'bar/foo', u'baz/foo']))


class GetPathNameTest(FluidinfoTestCase):

    def testGetPathNameWithRootPath(self):
        """L{getPathName} returns the path, unchanged, for root-level paths."""
        self.assertEqual(u'foo', getPathName(u'foo'))

    def testGetPathName(self):
        """
        L{getPathName} returns the final segment in the path, for
        non-root-level paths.
        """
        self.assertEqual(u'bar', getPathName(u'foo/bar'))
        self.assertEqual(u'baz', getPathName(u'foo/bar/baz'))


class IsValidPathTest(FluidinfoTestCase):

    def testIsValidPath(self):
        """
        L{isValidPath} returns C{True} if the specified path is not empty and
        is made up of upper and lower case alphanumeric characters, colon,
        dash, dot or underscore.
        """
        validCharacters = letters + digits + ':-._'
        for character in validCharacters:
            self.assertTrue(isValidPath(unicode(character)))

    def testIsValidWithEmptyPath(self):
        """L{isValidPath} returns C{False} if the specified path is empty."""
        self.assertFalse(isValidPath(u''))

    def testIsValidWithEmptyPathComponent(self):
        """L{isValidPath} returns C{False} if any path component is empty."""
        self.assertFalse(isValidPath(u'one//two'))

    def testIsValidPathWithUnnacceptableCharacter(self):
        """
        L{isValidPath} returns C{False} if the specified path contains
        unnacceptable characters.
        """
        invalidCharacters = u'!@#$%^&*()+={}[]\;"\'?<>\\, '
        for character in invalidCharacters:
            self.assertFalse(isValidPath(character))

    def testIsValidPathWithLongPath(self):
        """
        L{isValidPath} returns C{False} if the specified path is longer than
        233 characters.
        """
        path = 'root/' + ('x' * 229)
        self.assertFalse(isValidPath(path))
