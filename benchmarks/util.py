import random
import string


def randomString(size):
    """
    Returns a random string of a given size.
    """
    return ''.join(random.choice(string.letters) for _ in range(size))
