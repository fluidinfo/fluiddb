from instrument import test
from util import randomString


@test
def createRandomObject(fluiddb):
    """
    Creates an object with a random about tag using /objects.
    """
    about = 'benchmark test object ' + randomString(25)
    response = fluiddb.objects.post(about)
    return response.value['id']


@test
def setRandomTagValueString(fluiddb, objectId, path):
    """
    Updates a tag on the given object using a random string as value.
    """
    value = randomString(100)
    return fluiddb.objects[objectId][path].put(value)


@test
def simpleEqualsQuery(fluiddb, about):
    """
    Simple equals query on the about tag.
    """
    fluiddb.objects.get('fluiddb/about = "%s"' % about)


@test
def simpleMatchesQuery(fluiddb, term):
    """
    Simple matches query.
    """
    return fluiddb.objects.get('fluiddb/about matches "%s"' % term)


@test
def getObjectInfo(fluiddb, objectId):
    """
    Get information about an object.
    """
    return fluiddb.objects[objectId].get(showAbout=True)


@test
def getTagValue(fluiddb, objectId, path):
    """
    Get the value of a tag from an object.
    """
    return fluiddb.objects[objectId][path].get()


@test
def hasTagValue(fluiddb, objectId, path):
    """
    Tests if an object has a given tag.
    """
    return fluiddb.objects[objectId][path].head()


@test
def deleteTagValue(fluiddb, objectId, path):
    """
    Deletes a tag from an object.
    """
    return fluiddb.objects[objectId][path].delete()
