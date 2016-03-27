from instrument import test
from util import randomString


@test
def createRandomNamespace(fluiddb, path):
    """
    Creates a namespace with a random name.
    """
    name = randomString(25)
    description = 'Namepsace ' + name
    fluiddb.namespaces[path].post(name, description)
    return path.rstrip('/') + '/' + name


@test
def getNamespaces(fluiddb, path):
    """
    Gets information about the namespaces contained in a namespace.
    """
    return fluiddb.namespaces[path].get()


@test
def updateNamespaceWithRandomDescription(fluiddb, path):
    """
    Updates a namespace with a random description.
    """
    description = randomString(50)
    return fluiddb.namespaces[path].put(description)


@test
def deleteNamespace(fluiddb, path):
    """
    Deletes a namespace.
    """
    return fluiddb.namespaces[path].delete()
