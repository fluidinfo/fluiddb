from fluiddb.api.util import getCategoryAndAction, getOperation
from fluiddb.data.permission import Operation
from fluiddb.testing.basic import FluidinfoTestCase


class GetCategoryAndActionTest(FluidinfoTestCase):

    def testGetCategoryAndAction(self):
        """
        L{getCategoryAndAction} returns the category and action for a
        given L{Operation} value.
        """
        self.assertEqual((u'namespaces', u'create'),
                         getCategoryAndAction(Operation.CREATE_NAMESPACE))
        self.assertEqual((u'namespaces', u'update'),
                         getCategoryAndAction(Operation.UPDATE_NAMESPACE))
        self.assertEqual((u'namespaces', u'delete'),
                         getCategoryAndAction(Operation.DELETE_NAMESPACE))
        self.assertEqual((u'namespaces', u'list'),
                         getCategoryAndAction(Operation.LIST_NAMESPACE))
        self.assertEqual((u'namespaces', u'control'),
                         getCategoryAndAction(Operation.CONTROL_NAMESPACE))
        self.assertEqual((u'tags', u'update'),
                         getCategoryAndAction(Operation.UPDATE_TAG))
        self.assertEqual((u'tags', u'delete'),
                         getCategoryAndAction(Operation.DELETE_TAG))
        self.assertEqual((u'tags', u'control'),
                         getCategoryAndAction(Operation.CONTROL_TAG))
        self.assertEqual((u'tag-values', u'write'),
                         getCategoryAndAction(Operation.WRITE_TAG_VALUE))
        self.assertEqual((u'tag-values', u'read'),
                         getCategoryAndAction(Operation.READ_TAG_VALUE))
        self.assertEqual((u'tag-values', u'delete'),
                         getCategoryAndAction(Operation.DELETE_TAG_VALUE))
        self.assertEqual((u'tag-values', u'control'),
                         getCategoryAndAction(Operation.CONTROL_TAG_VALUE))
        self.assertEqual((u'users', 'create'),
                         getCategoryAndAction(Operation.CREATE_USER))
        self.assertEqual((u'users', 'delete'),
                         getCategoryAndAction(Operation.DELETE_USER))
        self.assertEqual((u'users', 'update'),
                         getCategoryAndAction(Operation.UPDATE_USER))
        self.assertEqual((u'objects', 'create'),
                         getCategoryAndAction(Operation.CREATE_OBJECT))


class GetOperation(FluidinfoTestCase):

    def testGetOperation(self):
        """
        L{getOperation} converts a C{category} and C{action} to an
        L{Operation} value.
        """
        self.assertEqual(Operation.CREATE_NAMESPACE,
                         getOperation(u'namespaces', u'create'))
        self.assertEqual(Operation.UPDATE_NAMESPACE,
                         getOperation(u'namespaces', u'update'))
        self.assertEqual(Operation.DELETE_NAMESPACE,
                         getOperation(u'namespaces', u'delete'))
        self.assertEqual(Operation.LIST_NAMESPACE,
                         getOperation(u'namespaces', u'list'))
        self.assertEqual(Operation.CONTROL_NAMESPACE,
                         getOperation(u'namespaces', u'control'))
        self.assertEqual(Operation.UPDATE_TAG,
                         getOperation(u'tags', u'update'))
        self.assertEqual(Operation.DELETE_TAG,
                         getOperation(u'tags', u'delete'))
        self.assertEqual(Operation.CONTROL_TAG,
                         getOperation(u'tags', u'control'))
        self.assertEqual(Operation.WRITE_TAG_VALUE,
                         getOperation(u'tag-values', u'write'))
        self.assertEqual(Operation.READ_TAG_VALUE,
                         getOperation(u'tag-values', u'read'))
        self.assertEqual(Operation.DELETE_TAG_VALUE,
                         getOperation(u'tag-values', u'delete'))
        self.assertEqual(Operation.CONTROL_TAG_VALUE,
                         getOperation(u'tag-values', u'control'))

    def testGetOperationWithTagValueCategoryAndCreateActionPair(self):
        """
        L{getOperation} correctly returns L{Operation.WRITE_TAG_VALUE} for the
        C{('tag-values', 'create')} pair.  This is provided for backwards
        compatibility, the preferred action is C{write}.
        """
        self.assertEqual(Operation.WRITE_TAG_VALUE,
                         getOperation(u'tag-values', u'create'))
