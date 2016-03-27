from os import execl, fork, wait

from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.testing.resources import LoggingResource
from fluiddb.util.minitoken import dataToToken, tokenToData, createKey


class TokenTest(FluidinfoTestCase):
    """Test minitoken.py functions."""

    resources = [('log', LoggingResource())]

    def testBadDataToToken(self):
        """Attempt to turn bad data into a token.

        Use C{self} as the bad data, since it can't be encoded by JSON.

        Make sure we get a C{ValueError}.
        """
        key = createKey()
        self.assertRaises(ValueError, dataToToken, key, data=self)

    def testBadKeyToToken(self):
        """Attempt to turn data into a token with a bad key.

        Make sure we get a C{ValueError}.
        """
        key = 5
        self.assertRaises(ValueError, dataToToken, key, data='hey')

    def testKeyInfoTooShort(self):
        """Attempt to turn data into a token with key info that's too short.

        Make sure we get a C{ValueError}.
        """
        key = 5
        self.assertRaises(ValueError, dataToToken, key, data='x', keyInfo='xx')

    def testKeyInfoTooLong(self):
        """Attempt to turn data into a token with key info that's too long.

        Make sure we get a C{ValueError}.
        """
        key = 5
        self.assertRaises(ValueError, dataToToken, key, data='hey',
                          keyInfo='xxxxx')

    def testTokenToDataWithBadKey(self):
        """Attempt to turn a token into valid data using an invalid key.

        Make sure we get a C{ValueError}.
        """
        key = createKey()
        data = {u'user': u'aliafshar'}
        token = dataToToken(key, data)
        self.assertRaises(ValueError, tokenToData, createKey(), token=token)

    def testRoundtrip(self):
        """Test that we can roundtrip encrypt / decrypt without error."""
        key = createKey()
        data = {u'user': u'aliafshar', u'id': u'91821212'}
        token = dataToToken(key, data)
        self.assertEqual(data, tokenToData(key, token))

    def testRoundtripAfterFork(self):
        """
        Test that we can roundtrip encrypt / decrypt after forking
        without error.
        """
        if fork() == 0:
            key = createKey()
            data = {u'user': u'aliafshar', u'id': u'91821212'}
            token = dataToToken(key, data)
            self.assertEqual(data, tokenToData(key, token))
            # This is horrible, but necessary: Turn the child into a sleep
            # process, so trial doesn't get its knickers in a knot when the
            # child tries to remove the trial lock file. I.e., politically
            # 'vanish' the child process and trial (the parent) removes the
            # lock as normal.
            #
            # This is necessary because trial checks the PID of the process
            # when removing the lock file. So apart from having two
            # processes trying to remove the same lock file (which causes
            # one kind of error), if the child gets there first, there is a
            # PID-mismatch error.
            execl('/bin/sleep', 'sleep', '0.01')
        else:
            # The parent waits for the child and exits normally.
            wait()
