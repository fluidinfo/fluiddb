from instrument import test
from util import randomString


@test
def createRandomObject(fluiddb):
    """
    Creates an object with a random about tag using /about.
    """
    about = 'benchmark test object ' + randomString(25)
    fluiddb.about.post(about)
    return about


@test
def getObjectInfo(fluiddb, about):
    """
    Gets object info for an object with the given about tag.
    """
    return fluiddb.about[about].get()


@test
def getTagValue(fluiddb, about, path):
    """
    Get the value of a tag from an object with the given about tag.
    """
    return fluiddb.about[about][path].get()


@test
def hasTagValue(fluiddb, about, path):
    """
    Tests if the object with the given about tag has a given tag.
    """
    return fluiddb.about[about][path].head()


@test
def setRandomTagValueString(fluiddb, about, path):
    """
    Updates a tag on the object with the given about tag.
    """
    value = randomString(100)
    return fluiddb.about[about][path].put(value)


@test
def deleteTagValue(fluiddb, about, path):
    """
    Deletes a tag from an object with the given about path.
    """
    return fluiddb.about[about][path].delete()
