from fluiddb.common.types_thrift.ttypes import ThriftValueType, ThriftValue

keyTypes = {
    ThriftValueType.BOOLEAN_TYPE: 'booleanKey',
    ThriftValueType.INT_TYPE: 'intKey',
    ThriftValueType.STR_TYPE: 'strKey',
    ThriftValueType.FLOAT_TYPE: 'floatKey',
    ThriftValueType.SET_TYPE: 'setKey',
    ThriftValueType.BINARY_TYPE: 'binaryKey',
    ThriftValueType.NONE_TYPE: None,
}

valueTypes = {
    bool: ('booleanKey', ThriftValueType.BOOLEAN_TYPE),
    int: ('intKey', ThriftValueType.INT_TYPE),
    float: ('floatKey', ThriftValueType.FLOAT_TYPE),
    str: ('strKey', ThriftValueType.STR_TYPE),
    list: ('setKey', ThriftValueType.SET_TYPE),
}


def guessValue(tvalue):
    attr = keyTypes[tvalue.valueType]
    if attr is None:
        return None
    else:
        value = getattr(tvalue, attr)

        if tvalue.valueType == ThriftValueType.STR_TYPE:
            value = value.decode('utf-8')
        return value


def createThriftValue(key):
    # Don't use this to create binary Thrift values, instead use
    # createBinaryThriftValue below.
    if key is None:
        return ThriftValue(valueType=ThriftValueType.NONE_TYPE)

    baseType = type(key)

    if baseType is unicode:
        key = key.encode('utf-8')
        baseType = str

    attr, valueType = valueTypes[baseType]
    tvalue = ThriftValue(valueType=valueType)
    setattr(tvalue, attr, key)

    return tvalue


def createBinaryThriftValue(key, mimeType):
    return ThriftValue(valueType=ThriftValueType.BINARY_TYPE,
                       binaryKey=key, binaryKeyMimeType=mimeType)
