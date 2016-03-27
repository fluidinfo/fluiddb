class ThriftValueType(object):
    INT_TYPE = 0
    FLOAT_TYPE = 1
    STR_TYPE = 2
    SET_TYPE = 3
    BINARY_TYPE = 4
    NONE_TYPE = 5
    BOOLEAN_TYPE = 6


class TagRangeType(object):
    NORMAL_TYPE = 0
    UNIQUE_TYPE = 1
    VALUELESS_TYPE = 2
    LIMITED_TYPE = 3


class ThriftValue(object):
    """
    Attributes:
     - valueType
     - booleanKey
     - intKey
     - floatKey
     - strKey
     - setKey
     - binaryKey
     - binaryKeyMimeType
    """

    def __init__(self, valueType=None, booleanKey=None, intKey=None,
                 floatKey=None, strKey=None, setKey=None, binaryKey=None,
                 binaryKeyMimeType=None):
        self.valueType = valueType
        self.booleanKey = booleanKey
        self.intKey = intKey
        self.floatKey = floatKey
        self.strKey = strKey
        self.setKey = setKey
        self.binaryKey = binaryKey
        self.binaryKeyMimeType = binaryKeyMimeType

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TProcess(object):
    """
    Attributes:
     - state
     - pid
     - executable
     - arguments
     - startedAt
     - stoppedAt
     - exitStatus
     - stdin
     - stdout
     - stderr
     - closeStdin
     - env
    """

    def __init__(self, state=None, pid=None, executable=None, arguments=None,
                 startedAt=None, stoppedAt=None, exitStatus=None, stdin=None,
                 stdout=None, stderr=None, closeStdin=None, env=None):
        self.state = state
        self.pid = pid
        self.executable = executable
        self.arguments = arguments
        self.startedAt = startedAt
        self.stoppedAt = stoppedAt
        self.exitStatus = exitStatus
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.closeStdin = closeStdin
        self.env = env

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TUser(object):
    """
    Attributes:
     - username
     - name
     - objectId
    """

    def __init__(self, username=None, name=None, role=None, objectId=None):
        self.username = username
        self.name = name
        self.objectId = objectId
        self.role = role

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TUserUpdate(object):
    """
    Attributes:
     - username
     - password
     - name
     - email
    """

    def __init__(self, username=None, password=None, name=None, email=None,
                 role=None):
        self.username = username
        self.password = password
        self.name = name
        self.email = email
        self.role = role

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TNamespace(object):
    """
    Attributes:
     - objectId
     - path
     - description
     - namespaces
     - tags
    """

    def __init__(self, objectId=None, path=None, description=None,
                 namespaces=None, tags=None):
        self.objectId = objectId
        self.path = path
        self.description = description
        self.namespaces = namespaces
        self.tags = tags

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TTag(object):
    """
    Attributes:
     - objectId
     - path
     - indexed
     - rangeType
     - description
    """

    def __init__(self, objectId=None, path=None, indexed=None, rangeType=None,
                 description=None):
        self.objectId = objectId
        self.path = path
        self.indexed = indexed
        self.rangeType = rangeType
        self.description = description

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TPolicyAndExceptions(object):
    """
    Attributes:
     - policy
     - exceptions
    """

    def __init__(self, policy=None, exceptions=None,):
        self.policy = policy
        self.exceptions = exceptions

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TObjectInfo(object):
    """
    Attributes:
     - about
     - tagPaths
    """

    def __init__(self, about=None, tagPaths=None,):
        self.about = about
        self.tagPaths = tagPaths

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class Tfluiddb_service_tags_status(object):
    """
    Attributes:
     - status
     - tagPaths
    """

    def __init__(self, status=None, tagPaths=None,):
        self.status = status
        self.tagPaths = tagPaths

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class Tfluiddb_service_broker_rabbitmq_status(object):
    """
    Attributes:
     - status
     - processes
    """

    def __init__(self, status=None, processes=None,):
        self.status = status
        self.processes = processes

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class Tfluiddb_service_coordinator_status(object):
    """
    Attributes:
     - startedAt
    """

    def __init__(self, startedAt=None,):
        self.startedAt = startedAt

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class Tfluiddb_service_database_postgres_status(object):
    """
    Attributes:
     - status
     - processes
    """

    def __init__(self, status=None, processes=None,):
        self.status = status
        self.processes = processes

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class Tfluiddb_service_facade_status(object):
    """
    Attributes:
     - status
    """

    def __init__(self, status=None,):
        self.status = status

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class Tfluiddb_service_kvstore_local_status(object):
    """
    Attributes:
     - status
    """

    def __init__(self, status=None,):
        self.status = status

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class Tfluiddb_service_kvstore_s3_status(object):
    """
    Attributes:
     - status
    """

    def __init__(self, status=None,):
        self.status = status

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class Tfluiddb_service_namespaces_status(object):
    """
    Attributes:
     - status
     - namespacePaths
    """

    def __init__(self, status=None, namespacePaths=None,):
        self.status = status
        self.namespacePaths = namespacePaths

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class Tfluiddb_service_objects_status(object):
    """
    Attributes:
     - status
     - nTagValues
    """

    def __init__(self, status=None, nTagValues=None,):
        self.status = status
        self.nTagValues = nTagValues

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class Tfluiddb_service_ping_status(object):
    """
    Attributes:
     - status
    """

    def __init__(self, status=None,):
        self.status = status

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class Tfluiddb_service_setops_status(object):
    """
    Attributes:
     - status
    """

    def __init__(self, status=None,):
        self.status = status

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class Tfluiddb_service_wsfe_status(object):
    """
    Attributes:
     - status
    """

    def __init__(self, status=None,):
        self.status = status

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TStdoutStderr(object):
    """
    Attributes:
     - stdout
     - stderr
    """

    def __init__(self, stdout=None, stderr=None,):
        self.stdout = stdout
        self.stderr = stderr

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TBadArgument(Exception):
    """
    Attributes:
     - message
    """

    def __init__(self, message=None,):
        self.message = message

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TBadRequest(Exception):
    """
    Attributes:
     - message
    """

    def __init__(self, message=None,):
        self.message = message

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TUnsatisfiedDependency(Exception):
    """
    Attributes:
     - message
    """

    def __init__(self, message=None,):
        self.message = message

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TInternalError(Exception):
    """
    Attributes:
     - message
    """

    def __init__(self, message=None,):
        self.message = message

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TPathPermissionDenied(Exception):
    """
    Attributes:
     - category
     - action
     - path
    """

    def __init__(self, category=None, action=None, path=None,):
        self.category = category
        self.action = action
        self.path = path

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TNonexistentNamespace(Exception):
    """
    Attributes:
     - path
    """

    def __init__(self, path=None,):
        self.path = path

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TNamespaceNotEmpty(Exception):
    """
    Attributes:
     - path
    """

    def __init__(self, path=None,):
        self.path = path

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TNamespaceAlreadyExists(Exception):
    """
    Attributes:
     - path
    """

    def __init__(self, path=None,):
        self.path = path

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TNonexistentTag(Exception):
    """
    Attributes:
     - path
    """

    def __init__(self, path=None,):
        self.path = path

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TTagAlreadyExists(Exception):
    """
    Attributes:
     - path
    """

    def __init__(self, path=None,):
        self.path = path

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TNoSuchUser(Exception):
    """
    Attributes:
     - name
    """

    def __init__(self, name=None,):
        self.name = name

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TUserAlreadyExists(Exception):
    """
    Attributes:
     - name
    """

    def __init__(self, name=None,):
        self.name = name

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TPasswordIncorrect(Exception):

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TInvalidSession(Exception):

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TParseError(Exception):
    """
    Attributes:
     - query
     - message
    """

    def __init__(self, query=None, message=None,):
        self.query = query
        self.message = message

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TUniqueRangeError(Exception):
    """
    Attributes:
     - path
     - objectId
     - value
    """

    def __init__(self, path=None, objectId=None, value=None,):
        self.path = path
        self.objectId = objectId
        self.value = value

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TSetTagInstanceGivingUp(Exception):
    """
    Attributes:
     - path
     - objectId
     - value
    """

    def __init__(self, path=None, objectId=None, value=None,):
        self.path = path
        self.objectId = objectId
        self.value = value

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TNoInstanceOnObject(Exception):
    """
    Attributes:
     - path
     - objectId
    """

    def __init__(self, path=None, objectId=None,):
        self.path = path
        self.objectId = objectId

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TUnknownRangeType(Exception):
    """
    Attributes:
     - rangeType
    """

    def __init__(self, rangeType=None,):
        self.rangeType = rangeType

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TInvalidPolicy(Exception):

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TUnauthorized(Exception):

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TUsernameTooLong(Exception):

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TInvalidUsername(Exception):

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TInvalidPath(Exception):

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TInvalidName(Exception):
    """
    Attributes:
     - name
    """

    def __init__(self, name=None,):
        self.name = name

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TExitFailed(Exception):

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)


class TNoSuchKey(Exception):
    """
    Attributes:
     - name
    """

    def __init__(self, name=None,):
        self.name = name

    def __str__(self):
        return repr(self)

    def __repr__(self):
        L = ['%s=%r' % (key, value)
             for key, value in self.__dict__.iteritems()]
        return '%s(%s)' % (self.__class__.__name__, ', '.join(L))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and (
            self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not (self == other)
