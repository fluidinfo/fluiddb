class Error(Exception):
    pass


class AlreadyExists(Error):
    pass


class BadArgument(Error):
    pass


class BadExitStatus(Error):
    pass


class ConfigError(Error):
    pass


class ContentLengthMismatch(Error):
    pass


class ContentChecksumMismatch(Error):
    pass


class ContentSeekError(Error):
    pass


class CoordinatorNotRunning(Error):
    pass


class CoordinatorStillRunning(Error):
    pass


class DatabaseProblem(Error):
    pass


class EmptyRegistry(Error):
    pass


class EmptyToplevel(Error):
    pass


class GenericError(Error):
    pass


class InUse(Error):
    pass


class InfiniteSetError(Error):
    pass


class InstanceIsRunning(Error):
    pass


class InstanceNotRunning(Error):
    pass


class InternalError(Error):
    pass


class InternalInconsistency(Error):
    pass


class InvalidRangeType(Error):
    pass


class MalformedPayload(Error):

    def __init__(self, message):
        self.message = message


class KVStoreClearError(Error):
    pass


class MissingPayload(Error):
    pass


class NoContentLengthHeader(Error):
    pass


class NoContentTypeHeader(Error):
    pass


class NoOriginHeader(Error):
    pass


class NoInstance(Error):
    pass


class NoMoreServers(Error):
    pass


class NoObjects(Error):
    pass


class NoSuchFile(Error):
    pass


class NoSuchInstance(Error):
    pass


class NoSuchKey(Error):
    pass


class NoSuchObject(Error):
    pass


class NoSuchPlugin(Error):
    pass


class NoSuchProcess(Error):
    pass


class NoSuchProfile(Error):
    pass


class NoSuchResource(Error):
    pass


class NoSuchRole(Error):
    pass


class NoSuchServer(Error):
    pass


class NoSuchServerType(Error):
    pass


class NoSuchToplevel(Error):
    pass


class NoSuchUsage(Error):
    pass


class NoSuchUser(Error):
    pass


class NoSuchVerb(Error):
    pass


class NoSuchVersion(Error):
    pass


class NotAcceptable(Error):
    pass


class NonEmptyNamespace(Error):
    pass


class NonexistentTag(Error):
    pass


class NonexistentNamespace(Error):
    pass


class NotIndexed(Error):
    pass


class PasswordMismatch(Error):
    pass


class PermissionDenied(Error):
    pass


class PluginError(Error):
    pass


class ProcessStillRunning(Error):
    pass


class QueryParseError(Error):
    pass


class TimeoutError(Error):
    pass


class TooManyObjects(Error):
    pass


class UnexpectedContentLengthHeader(Error):
    pass


class UnknownAcceptType(Error):
    pass


class UnknownContentType(Error):
    pass


class UnknownError(Error):
    pass


class UnsupportedJSONType(Error):
    pass


class WatchLimitReached(Error):
    pass


class UnwrappableBlob(Error):
    pass


class IndexingError(Error):
    pass


class FieldError(Error):

    def __init__(self, fieldName):
        self.fieldName = fieldName

    def __repr__(self):
        return '<%s instance: fieldName=%r>' % (
            self.__class__.__name__, self.fieldName)

    __str__ = __repr__


class InvalidPayloadField(FieldError):
    pass


class InvalidResponsePayloadField(FieldError):
    pass


class PayloadFieldMissing(FieldError):
    pass


class ResponsePayloadFieldMissing(FieldError):
    pass


class UnknownPayloadField(FieldError):
    pass


class UnknownResponsePayloadField(FieldError):
    pass


class ArgumentError(Error):

    def __init__(self, argument):
        self.argument = argument

    def __repr__(self):
        return '<%s instance: argument=%r>' % (
            self.__class__.__name__, self.argument)

    __str__ = __repr__


class UnknownArgument(ArgumentError):
    pass


class MissingArgument(ArgumentError):
    pass


class MultipleArgumentValues(ArgumentError):
    pass


class InvalidUTF8Argument(ArgumentError):
    pass
