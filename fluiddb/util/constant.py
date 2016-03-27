from storm.locals import Enum


class EnumBase(object):

    @classmethod
    def fromID(cls, id):
        """Return a constant from the enum based on its ID.
        """
        for value in cls.__dict__.itervalues():
            if isinstance(value, Constant) and value.id == id:
                return value
        raise LookupError()

    @classmethod
    def fromName(cls, name):
        for value in cls.__dict__.itervalues():
            if isinstance(value, Constant) and value.name == name:
                return value
        raise LookupError()


class Constant(object):
    """A constant value for use when defining enumerations.

    @param id: The ID of the constant.
    @param name: The name of the constant.
    """

    def __init__(self, id, name):
        self.id = id
        self.name = name

    def __str__(self):
        """Get the name of this constant."""
        return self.name

    def __repr__(self):
        """Get a representation of this constant, suitable for debugging."""
        return '<Constant id=%s name=%s>' % (self.id, self.name)


class ConstantEnum(Enum):
    """A Storm property for use with L{Constant}-based enumerations.

    @param name: Optionally, the name of the column.
    @param enum_class: The enumeration class that contains L{Constant}
        attributes.
    @param primary: True if this property represents a primary key.
    """

    def __init__(self, name=None, enum_class=None, primary=False, **kwargs):
        get_map = {}
        for member in enum_class.__dict__.itervalues():
            if isinstance(member, Constant):
                get_map[member] = member.id
        kwargs['map'] = get_map
        super(ConstantEnum, self).__init__(name=name, primary=primary,
                                           **kwargs)
