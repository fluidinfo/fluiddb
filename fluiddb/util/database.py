from json import loads, dumps

from storm.properties import SimpleProperty
from storm.variables import EncodedValueVariable


class BinaryJSONVariable(EncodedValueVariable):
    """Variable serializes data to and from JSON."""

    __slots__ = ()

    def _loads(self, value):
        return loads(value)

    def _dumps(self, value):
        return dumps(value)


class BinaryJSON(SimpleProperty):
    """Storm property stores data in JSON-format in a BYTEA binary column."""

    variable_class = BinaryJSONVariable
