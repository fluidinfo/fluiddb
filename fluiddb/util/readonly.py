from storm.info import get_cls_info
from storm.variables import Variable


class ReadonlyObjectFactory(object):
    """Factory monkey patches a Storm C{ResultSet} to make it readonly."""

    def patch(self, result):
        """Monkey patch the C{ResultSet} to put it in readonly mode.

        @param result: A Storm C{ResultSet}.
        @return: The patched C{ResultSet} instance.
        """
        self._result = result
        result._find_spec.load_objects = self._load_objects
        result.set = self.set
        return result

    def set(self, *args, **kwargs):
        """Updates are disabled.

        @raise: A C{RuntimeError} is raised if this method is invoked.
        """
        raise RuntimeError('This ResultSet is in readonly mode.')

    def _load_objects(self, store, result, values):
        """Load objects from the database result set.

        @param store: The C{Store} to load objects from.
        @param result: The database result set.
        @param values: The database values.
        @return: The objects loaded from the specified values and result set.
        """
        objects = []
        values_start = values_end = 0
        for is_expr, info in self._result._find_spec._cls_spec_info:
            if is_expr:
                values_end += 1
                factory_class = getattr(info, "variable_factory", Variable)
                variable = factory_class(value=values[values_start],
                                         from_db=True)
                objects.append(variable.get())
            else:
                values_end += len(info.columns)
                obj = self._load_object(info, result,
                                        values[values_start:values_end])
                objects.append(obj)
            values_start = values_end
        if self._result._find_spec.is_tuple:
            return tuple(objects)
        else:
            return objects[0]

    def _load_object(self, cls_info, result, values):
        """Create an object from values loaded from the database.

        @param cls_info: The C{ClassInfo} for the row being loaded.
        @param result: The database result set.
        @param values: The database values.
        @return: A new instances of the class mapped to the table being
            loaded.
        """
        if not any(values):
            # We've got a row full of NULLs, so consider that the object
            # wasn't found.  This is useful for joins, where non-existent rows
            # are represented like that.
            return None

        # Build a new instance.  We need the cls_info columns for the class of
        # the actual object, not from a possible wrapper (e.g. an alias).
        cls = cls_info.cls
        cls_info = get_cls_info(cls)
        index = {}
        for attributeName, propertyColumn in cls_info.attributes.iteritems():
            index[propertyColumn.name] = attributeName

        # Build a new instance and populate it with values from the database.
        obj = cls.__new__(cls)
        for column, value in zip(cls_info.columns, values):
            variable = column.variable_factory(value=value, from_db=True)
            attributeName = index[column.name]
            setattr(obj, attributeName, variable.get())
        return obj


def readonly(result):
    """Make a C{ResultSet} return readonly objects.

    The C{ResultSet} is monkey patched to create objects without connecting to
    Storm's event system or putting them in Storm's cache.  This is a one way
    transformation.  The C{ResultSet} cannot be used for write operations
    after this function has been invoked.

    @return: The C{ResultSet} in readonly mode.
    """
    factory = ReadonlyObjectFactory()
    return factory.patch(result)
