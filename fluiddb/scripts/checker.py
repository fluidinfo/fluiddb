import logging
import sys

from fluiddb.data.namespace import getNamespaces, Namespace
from fluiddb.data.path import getParentPath, isValidPath
from fluiddb.data.permission import (
    getNamespacePermissions, getTagPermissions, Operation)
from fluiddb.data.store import getMainStore
from fluiddb.data.tag import getTags, Tag
from fluiddb.data.user import getUsers, isValidUsername, User
from fluiddb.data.value import (
    getTagValues, TagValue, getAboutTagValues, AboutTagValue)


def checkIntegrity(maxRowsPerQuery=10000):
    """
    Check the integrity of the database for cases which the database
    engine can't detect.

    @param maxRowsPerQuery: Limit the number of rows fetched by SQL queries to
        avoid excessive use of memory.
    """
    results = _splitResult(getNamespaces(), Namespace.id, maxRowsPerQuery)
    for result in results:
        namespaces = list(result)
        NamespaceIntegrityChecker().check(namespaces)

    results = _splitResult(getTags(), Tag.id, maxRowsPerQuery)
    for result in results:
        tags = list(result)
        TagIntegrityChecker().check(tags)

    results = _splitResult(getUsers(), User.id, maxRowsPerQuery)
    for result in results:
        users = list(result)
        UserIntegrityChecker().check(users)

    results = _splitResult(getAboutTagValues(), AboutTagValue.objectID,
                           maxRowsPerQuery)
    for result in results:
        aboutTagValues = list(result)
        AboutTagValueIntegrityChecker().check(aboutTagValues)

    # In the case of TagValues we limit the query to only tag paths starting
    # with "fluiddb" because these are the only ones we're checking and we
    # don't want a huge result.
    store = getMainStore()
    result = store.find(TagValue,
                        TagValue.tagID == Tag.id,
                        Tag.path.startswith(u'fluiddb/'))
    results = _splitResult(getTagValues(), TagValue.id, maxRowsPerQuery)
    for result in results:
        tagValues = list(result)
        TagValueIntegrityChecker().check(tagValues)


def _splitResult(resultSet, orderBy, chunkSize):
    """
    Split a L{ResultSet} in parts to avoid storing a huge number of rows in
    memory. Each resulting ResultSet will represent a query to the database
    with a limited number of rows.

    @param resultSet: The L{ResultSet} to split.
    @param orderBy: The column to order the original L{ResultSet} by. This
        is necessary because SQL won't guarantee the order of a query without
        an C{ORDER BY} clause.
    @param chunkSize: The max number of rows that should be returned by each
        sub L{ResultSet}.
    """
    totalRows = resultSet.copy().count()
    chunks = totalRows / chunkSize
    if chunks == 0:
        chunks = 1

    for i in xrange(chunks):
        limit = chunkSize if (i != chunks - 1) else None
        offset = i * chunkSize
        result = resultSet.copy()
        result = result.order_by(orderBy)
        result = result.config(limit=limit, offset=offset)
        yield result


class BaseIntegrityChecker(object):
    """
    Base class for all integrity checkers.

    @param stream: A file-like object to write error notifications to.
    """

    def _getSystemTag(self, path):
        """Get a system L{Tag} showing an error if it doesn't exist.

        @param path: The path of the requested L{Tag}.
        @return The requested L{Tag}.
        """
        tag = getTags(paths=[path]).one()
        if not tag:
            logging.critical(
                'Fatal Error: system tag %r does not exist.' % path)
            sys.exit(1)
        return tag

    def _getValues(self, objects, path):
        """Get all L{TagValue}s for the given objects and the given path.

        @param objects: A sequence of L{Tag}s, L{Namespace}s or L{User}s.
        @param path: The path of the L{Tag} to get the vaues from.
        @return: A C{dict} mapping object IDs to values.
        """
        tag = self._getSystemTag(path)
        result = getTagValues([(object.objectID, tag.id)
                               for object in objects])
        return dict(result.values(TagValue.objectID, TagValue.value))

    def checkAboutValue(self, object, aboutValues, expectedValue):
        """Check that a given object has the expected about tag value.

        @param object: A L{Tag}, L{Namespace} or L{User} to check.
        @param aboutValues: A C{dict} mapping object IDs to about values.
        @param expectedValue: The expected value for the object.
        """
        aboutValue = aboutValues.get(object.objectID)
        if not aboutValue:
            self._log(object, u'About tag is missing.')
        elif aboutValue != expectedValue:
            self._log(object, u'About tag is incorrect.')

    def checkPathValue(self, object, pathValues):
        """Check that a given object has a correct path tag value.

        @param object: A L{Tag}, L{Namespace} to check.
        @param pathValues: A C{dict} mapping object IDs to path values.
        """
        pathValue = pathValues.get(object.objectID)
        if not pathValue:
            self._log(object, u'Path tag is missing.')
        elif pathValue != object.path:
            self._log(object, u'Path tag is incorrect.')

    def checkDescriptionValue(self, object, descriptionValues):
        """Check that a given object has a correct path description value.

        @param object: A L{Tag}, L{Namespace} to check.
        @param descriptionValues: A C{dict} mapping object IDs to description
            values.
        """
        descriptionValue = descriptionValues.get(object.objectID)
        if not descriptionValue:
            self._log(object, u'Description tag is missing.')

    def checkPermissions(self, object, permissions, users, operations):
        """Check that a given L{Tag} or L{Namespace} has correct permissions.

        @param object: A L{Namespace} or L{Tag} to check.
        @param permissions: A C{dict} mapping objects to permissions.
        @param users: A C{dict} mapping user IDs to users.
        @param operations a list of operations to be checked.
        """
        permission = permissions.get(object)
        if permission is None:
            self._log(object, u'Permissions row is missing.')
            return
        for operation in operations:
            policy, exceptions = permission.get(operation)
            for userID in exceptions:
                user = users.get(userID)
                if user is None:
                    self._log(object,
                              'Nonexistent user ID %d in exceptions list '
                              'for %s permission.' % (userID, operation))
                elif user.isSuperuser():
                    self._log(object,
                              'A superuser is in the exceptions list for '
                              '%s permission.' % operation)
                elif (user.isAnonymous() and
                      operation not in Operation.ALLOWED_ANONYMOUS_OPERATIONS):
                    self._log(object,
                              'An anonymous user is in the exceptions list '
                              'for %s permission.' % operation)

    def checkValidPath(self, object):
        """Check that a given object has a correct path.

        @param object: A L{Tag}, L{Namespace} to check.
        """
        if not isValidPath(object.path):
            self._log(object, u'Invalid path.')


class NamespaceIntegrityChecker(BaseIntegrityChecker):
    """Integrity checker for L{Namespace}s."""

    def _log(self, namespace, message):
        error = 'Integrity Error in namespace %r: %s' % (namespace.path,
                                                         message)
        logging.error(error)

    def check(self, namespaces):
        """ Check given L{Namespace}s for integrity errors.

        @param namespaces: A sequence of L{Namespace}s to be checked.
        """

        aboutValues = self._getValues(namespaces, u'fluiddb/about')
        pathValues = self._getValues(namespaces, u'fluiddb/namespaces/path')
        descriptionValues = self._getValues(namespaces,
                                            u'fluiddb/namespaces/description')

        paths = [namespace.path for namespace in namespaces]
        namespacePermissions = dict(getNamespacePermissions(paths))

        parentPaths = [getParentPath(namespace.path)
                       for namespace in namespaces
                       if namespace.parentID is not None]
        parentNamespaces = getNamespaces(paths=parentPaths)
        parentNamespaces = dict((namespace.path, namespace)
                                for namespace in parentNamespaces)

        users = getUsers()
        users = dict((user.id, user) for user in users)

        for namespace in namespaces:
            expectedAbout = u'Object for the namespace %s' % namespace.path
            self.checkAboutValue(namespace, aboutValues, expectedAbout)
            self.checkPathValue(namespace, pathValues)
            self.checkDescriptionValue(namespace, descriptionValues)
            self.checkPermissions(namespace, namespacePermissions, users,
                                  Operation.NAMESPACE_OPERATIONS)
            self.checkParent(namespace, parentNamespaces)
            self.checkValidPath(namespace)

    def checkParent(self, namespace, parentNamespaces):
        """Check that a given L{Namespace} has a correct parent.

        @param object: A L{Namespace} to check.
        @param parentNamespaces: A C{dict} mapping paths to namespaces
            representing parents.
        """
        parentPath = getParentPath(namespace.path)
        if not parentPath:
            return
        parent = parentNamespaces.get(parentPath)
        if namespace.parentID is None:
            self._log(namespace, 'Parent ID is not specified.')
        elif not parent or parent.id != namespace.parentID:
            self._log(namespace, 'Assigned parent is incorrect.')


class TagIntegrityChecker(BaseIntegrityChecker):
    """Integrity checker for L{Tag}s"""

    def _log(self, tag, message):
        error = 'Integrity Error in tag %r: %s' % (tag.path, message)
        logging.error(error)

    def check(self, tags):
        """Check given L{Tag}s for integrity errors.

        @param tags: A sequence of L{Tag}s to be checked.
        """
        aboutValues = self._getValues(tags, u'fluiddb/about')
        pathValues = self._getValues(tags, u'fluiddb/tags/path')
        descriptionValues = self._getValues(tags, u'fluiddb/tags/description')

        tagPermissions = dict(getTagPermissions([tag.path for tag in tags]))

        parentPaths = [getParentPath(tag.path) for tag in tags]
        parentNamespaces = getNamespaces(parentPaths)
        parentNamespaces = dict((namespace.path, namespace)
                                for namespace in parentNamespaces)

        users = getUsers()
        users = dict((user.id, user) for user in users)

        for tag in tags:
            expectedAbout = u'Object for the attribute %s' % tag.path
            self.checkAboutValue(tag, aboutValues, expectedAbout)
            self.checkPathValue(tag, pathValues)
            self.checkDescriptionValue(tag, descriptionValues)
            self.checkPermissions(tag, tagPermissions, users,
                                  Operation.TAG_OPERATIONS)
            self.checkParent(tag, parentNamespaces)
            self.checkValidPath(tag)

    def checkParent(self, tag, parentNamespaces):
        """Check that a given L{Tag} has a correct parent.

        @param object: A L{Tag} to check.
        @param parentNamespaces: A C{dict} mapping paths to namespaces
            representing parents.
        """
        parentPath = getParentPath(tag.path)
        parent = parentNamespaces.get(parentPath)
        if tag.namespaceID is None:
            self._log(tag, 'Parent ID is not specified.')
        elif not parent or parent.id != tag.namespaceID:
            self._log(tag, 'Assigned parent is incorrect.')


class UserIntegrityChecker(BaseIntegrityChecker):
    """Integrity checker for L{User}s"""

    def _log(self, user, message):
        error = 'Integrity Error in user %r: %s' % (user.username, message)
        logging.error(error)

    def check(self, users):
        """Check a given L{User}s for integrity errors.

        @param users: A sequence of L{User}s to be checked.
        """
        aboutValues = self._getValues(users, u'fluiddb/about')
        usernameValues = self._getValues(users, u'fluiddb/users/username')
        nameValues = self._getValues(users, u'fluiddb/users/name')
        emailValues = self._getValues(users, u'fluiddb/users/email')

        namespaces = getNamespaces(paths=[user.username for user in users])
        namespaces = dict((namespace.path, namespace)
                          for namespace in namespaces)

        for user in users:
            expectedAbout = u'@%s' % user.username
            self.checkAboutValue(user, aboutValues, expectedAbout)
            self.checkUsernameValue(user, usernameValues)
            self.checkNameValue(user, nameValues)
            self.checkEmailValue(user, emailValues)
            self.checkNamespace(user, namespaces)
            self.checkUsername(user)

    def checkUsernameValue(self, user, usernameValues):
        """Check that a given L{User} has a correct username tag value.

        @param user: A L{User} to check.
        @param usernameValues: A C{dict} mapping object IDs to username
            values.
        """
        usernameValue = usernameValues.get(user.objectID)
        if not usernameValue:
            self._log(user, u'Username tag is missing.')
        elif usernameValue != user.username:
            self._log(user, u'Username tag is incorrect.')

    def checkNameValue(self, user, nameValues):
        """Check that a given L{User} has a name tag value.

        @param user: A L{User} to check.
        @param nameValues: A C{dict} mapping object IDs to name values.
        """
        nameValue = nameValues.get(user.objectID)
        if not nameValue:
            self._log(user, u'Name tag is missing.')
        elif nameValue != user.fullname:
            self._log(user, u'Name tag is incorrect.')

    def checkEmailValue(self, user, emailValues):
        """Check that a given L{User} has a email tag value.

        @param user: A L{User} to check.
        @param emailValues: A C{dict} mapping object IDs to email values.
        """
        emailValue = emailValues.get(user.objectID)
        if not emailValue:
            self._log(user, u'Email tag is missing.')
        elif emailValue != user.email:
            self._log(user, u'Email tag is incorrect.')

    def checkNamespace(self, user, namespaces):
        """
        Check that a given L{User} has a root namespace matching its username.

        @param user: A L{User} to check.
        @param namespaces: A C{dict} mapping namespace paths to namespaces.
        """
        namespace = namespaces.get(user.username)
        if namespace is None:
            self._log(user, u'Root namespace is missing.')
        elif user.namespaceID != namespace.id:
            self._log(user, u'Assigned namespace is incorrect.')

    def checkUsername(self, user):
        """Check that a given L{User} has a correct namespace.

        @param user: A L{User} to check.
        """
        if not isValidUsername(user.username):
            self._log(user, u'Invalid username.')


class AboutTagValueIntegrityChecker(BaseIntegrityChecker):
    """Integrity checker for L{AboutTagValue}s"""

    def _log(self, tagValue, message):
        error = 'Integrity Error in object %s: %s' % (tagValue.objectID,
                                                      message)
        logging.error(error)

    def check(self, aboutTagValues):
        """Check a given L{AboutTagValue}s for integrity errors.

        @param aboutTagValues: A sequence of L{AboutTagValue}s to be checked.
        """
        aboutValues = self._getValues(aboutTagValues, u'fluiddb/about')
        for aboutTagValue in aboutTagValues:
            self.checkTagValue(aboutTagValue, aboutValues)

    def checkTagValue(self, aboutTagValue, aboutValues):
        """
        Check that a given L{AboutTagValue} has an corresponding fluiddb/about
        L{TagValue}.

        @param aboutTagValue: A L{AboutTagValue} to check.
        @param aboutValues: A C{dict} mapping object IDs to about values.
        """
        aboutValue = aboutValues.get(aboutTagValue.objectID)
        if aboutValue is None:
            self._log(aboutTagValue,
                      "AboutTagValue doesn't have an associated TagValue.")
        elif aboutValue != aboutTagValue.value:
            self._log(aboutTagValue,
                      "AboutTagValue doesn't match its TagValue.")


class TagValueIntegrityChecker(BaseIntegrityChecker):
    """Integrity checker for L{TagValue}s"""

    def _log(self, tagValue, message):
        error = 'Integrity Error in object %s: %s' % (tagValue.objectID,
                                                      message)
        logging.error(error)

    def check(self, tagValues):
        """Check a given L{TagValue}s for integrity errors.

        @param tagValues: A sequence of L{TagValue}s to be checked.
        """
        objectIDs = [tagValue.objectID for tagValue in tagValues]
        aboutTagValues = getAboutTagValues(objectIDs=objectIDs)
        aboutTagValues = dict((aboutTagValue.objectID, aboutTagValue)
                              for aboutTagValue in aboutTagValues)
        namespaces = dict((namespace.objectID, namespace)
                          for namespace in getNamespaces(objectIDs=objectIDs))
        users = dict((user.objectID, user)
                     for user in getUsers(objectIDs=objectIDs))
        tags = dict((tag.objectID, tag)
                    for tag in getTags(objectIDs=objectIDs))

        for tagValue in tagValues:
            self.checkAboutTagValue(tagValue, aboutTagValues)
            self.checkNamespaceValues(tagValue, namespaces)
            self.checkTagValues(tagValue, tags)
            self.checkUserValues(tagValue, users)

    def checkAboutTagValue(self, tagValue, aboutTagValues):
        """
        Check that a given L{TagValue} for the fluiddb/about tag has a
        corresponding L{AboutTagValue} row in the database.

        @param tagValue: A L{TagValue} to be checked.
        @param aboutTagValues: a C{dict} mapping object IDs to
            L{AboutTagValue}s.
        """
        if (tagValue.tag.path == u'fluiddb/about'
                and tagValue.objectID not in aboutTagValues):
            self._log(tagValue,
                      "fluiddb/about TagValue doesn't have an associated "
                      'AboutTagValue.')

    def checkNamespaceValues(self, tagValue, namespaces):
        """
        Check that a given L{TagValue} for a fluiddb/namespaces tag has a
        corresponding L{Namespace} row in the database.

        @param tagValue: A L{TagValue} to be checked.
        @param aboutTagValues: a C{dict} mapping object IDs to
            L{Namespace}s.
        """
        if (tagValue.tag.path.startswith('fluiddb/namespaces')
                and tagValue.objectID not in namespaces):
            self._log(tagValue,
                      "%s TagValue doesn't have an associated Namespace."
                      % tagValue.tag.path)

    def checkTagValues(self, tagValue, tags):
        """
        Check that a given L{TagValue} for a fluiddb/tags tag has a
        corresponding L{Tag} row in the database.

        @param tagValue: A L{TagValue} to be checked.
        @param aboutTagValues: a C{dict} mapping object IDs to
            L{Tags}s.
        """
        if (tagValue.tag.path.startswith('fluiddb/tags')
                and tagValue.objectID not in tags):
            self._log(tagValue,
                      "%s TagValue doesn't have an associated Tag."
                      % tagValue.tag.path)

    def checkUserValues(self, tagValue, users):
        """
        Check that a given L{TagValue} for a fluiddb/users tag has a
        corresponding L{User} row in the database.

        @param tagValue: A L{TagValue} to be checked.
        @param aboutTagValues: a C{dict} mapping object IDs to
            L{User}s.
        """
        if (tagValue.tag.path.startswith('fluiddb/users')
                and tagValue.objectID not in users):
            self._log(tagValue,
                      "%s TagValue doesn't have an associated User."
                      % tagValue.tag.path)
