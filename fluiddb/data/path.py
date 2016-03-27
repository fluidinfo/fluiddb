import re


def getPathName(path):
    """Get the name of the final entity in C{path}.

    @param path: A fully-qualified C{unicode} path.
    @return: The C{unicode} name of the final element in the path.
    """
    unpackedPath = path.rsplit(u'/', 1)
    return path if len(unpackedPath) == 1 else unpackedPath[1]


def getParentPath(path):
    """Get the parent path from C{path}.

    @param path: A fully-qualified C{unicode} path.
    @return: The C{unicode} parent path or C{None} if C{path} represents a
        root-level entity.
    """
    unpackedPath = path.rsplit(u'/', 1)
    return None if len(unpackedPath) == 1 else unpackedPath[0]


def getParentPaths(paths):
    """Get the parent paths for the specified paths.

    @param paths: The paths to get parent paths for.
    @return: A C{set} of parent paths.
    """
    parentPaths = set()
    for path in paths:
        parentPath = getParentPath(path)
        if parentPath:
            parentPaths.add(parentPath)
    return parentPaths


def getPathHierarchy(paths):
        """
        Get the given paths plus all the parents for each path up to the root
        namespace.
        """
        hierarchy = set()
        for path in paths:
            hierarchy.add(path)
            parent = getParentPath(path)
            while parent is not None:
                hierarchy.add(parent)
                parent = getParentPath(parent)
        return hierarchy


NAME_REGEXP = re.compile(r'^[\:\.\-\w]+$', re.UNICODE)


def isValidPath(path):
    """Determine if C{path} is valid.

    A path may only contain uppercase or lowercase letters, numbers, and
    colon, dash, dot and underscore characters.

    @param path: A C{unicode} path to validate.
    @return: C{True} if C{path} is valid, otherwise C{False}.
    """
    # FIXME: I (ceronman) think this is not necessary anymore. However, it's a
    # documented limit [1] and there are integration tests for it. We should
    # remove this later and document the changes, for now it's better to keep
    # compatibility with the old code.
    # [1] http://doc.fluidinfo.com/fluidDB/api/namespaces-and-tags.html#paths
    if len(path) > 233:
        return False
    return all(NAME_REGEXP.match(part) for part in path.split(u'/'))
