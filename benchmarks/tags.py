from instrument import test
from util import randomString


@test
def createRandomTag(fluiddb, path):
    """
    Creates a new tag with a random name.
    """
    name = randomString(25)
    description = 'Tag ' + name
    fluiddb.tags[path].post(name, description, True)
    return path.rstrip('/') + '/' + name


@test
def getTagInfo(fluiddb, path):
    """
    Gets information about a given tag.
    """
    return fluiddb.tags[path].get()


@test
def UpdateTagWithRandomDescription(fluiddb, path):
    """
    Updates a tag with a random value.
    """
    description = randomString(50)
    return fluiddb.tags[path].put(description)


@test
def deleteTag(fluiddb, path):
    """
    Deletes a tag.
    """
    return fluiddb.tags[path].delete()
