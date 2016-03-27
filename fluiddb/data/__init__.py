"""
Layer contains data access logic for storing and retrieving data in Fluidinfo.
"""

# Import all the data classes so that they get registered with Storm's
# property resolver.
from fluiddb.data.tag import Tag
from fluiddb.data.user import User
from fluiddb.data.value import TagValue, AboutTagValue
from fluiddb.data.namespace import Namespace
from fluiddb.data.permission import NamespacePermission, TagPermission


# Suppress Pyflakes warnings.
_ = (AboutTagValue, Namespace, NamespacePermission, Tag, TagPermission,
     TagValue, User)

# Remove them so that they can't be imported directly from this package.
del (AboutTagValue, Namespace, NamespacePermission, Tag, TagPermission,
     TagValue, User, _)
