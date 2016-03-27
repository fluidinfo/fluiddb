from fluiddb.common import error
from fluiddb.doc.api.http.registry import (
    Registry, HTTPTopLevel, Note, HTTPUsage, Payload, PayloadField,
    JSONPayload, HTTPExample)
from fluiddb.testing.basic import FluidinfoTestCase


class TestRegistry(FluidinfoTestCase):

    def setUp(self):
        super(TestRegistry, self).setUp()
        self.reg = Registry()

    def testRegisterAndGet(self):
        f = HTTPTopLevel('users', 'PUT')
        self.reg.register(f)
        apis = self.reg.get('users', 'PUT')
        self.assertEqual(apis, [['users', [('PUT', f)]]])

    def testGetFromEmpty(self):
        self.assertRaises(error.EmptyRegistry, self.reg.get)

    def testRegisterAndGetNonExistentToplevel(self):
        f = HTTPTopLevel('users', 'PUT')
        self.reg.register(f)
        self.assertRaises(error.NoSuchToplevel, self.reg.get, 'fred', '')

    def testRegisterAndGetNonExistentVerb(self):
        f = HTTPTopLevel('users', 'PUT')
        self.reg.register(f)
        self.assertRaises(error.NoSuchVerb, self.reg.get, 'users', '')

    def testNotes(self):
        f = HTTPTopLevel('users', 'PUT')
        usage = HTTPUsage('/dummy', 'an example of great profundity')
        f.addUsage(usage)
        note = Note('hey')
        usage.addNote(note)
        note = Note('hey')
        usage.addNote(note)
        self.assertEqual(len(usage.notes), 2)
        self.reg.register(f)
        apis = self.reg.get('users', 'PUT')
        self.assertEqual(apis, [['users', [('PUT', f)]]])
        f = apis[0][1][0][1]
        self.assertEqual(len(f.usages), 1)
        self.assertEqual(len(f.usages[0].notes), 2)

    def testGetWildcards(self):
        f1 = HTTPTopLevel('objects', 'GET')
        self.reg.register(f1)
        f2 = HTTPTopLevel('objects', 'PUT')
        self.reg.register(f2)
        f3 = HTTPTopLevel('users', 'GET')
        self.reg.register(f3)

        apis = self.reg.get('objects', 'GET')
        self.assertEqual(apis, [['objects', [('GET', f1)]]])

        apis = self.reg.get('objects', '*')
        self.assertEqual(apis, [['objects', [('GET', f1), ('PUT', f2)]]])

        apis = self.reg.get('*', 'GET')
        self.assertEqual(apis, [['objects', [('GET', f1)]],
                                ['users', [('GET', f3)]]])

        apis = self.reg.get('*', 'PUT')
        self.assertEqual(apis, [['objects', [('PUT', f2)]]])

        apis = self.reg.get('*', '*')
        self.assertEqual(apis, [['objects', [('GET', f1), ('PUT', f2)]],
                                ['users', [('GET', f3)]]])

    def testFindUsage(self):

        class Dummy1(object):
            pass

        class Dummy2(object):
            pass

        class Dummy3(object):
            pass

        f = HTTPTopLevel('users', 'PUT')
        self.reg.register(f)
        usage1 = HTTPUsage('', "Return a list of all users.")
        usage1.resourceClass = Dummy1
        f.addUsage(usage1)

        f = HTTPTopLevel('dummy', 'GET')
        self.reg.register(f)
        usage2 = HTTPUsage('', "Return a list of all dummies.")
        usage2.resourceClass = Dummy2
        f.addUsage(usage2)

        # Find the usage with class Dummy1.
        u = self.reg.findUsage('users', 'PUT',
                               usageResourceClass=Dummy1)
        self.assertTrue(u.resourceClass is usage1.resourceClass)

        # Find the usage with class Dummy2.
        u = self.reg.findUsage('dummy', 'GET',
                               usageResourceClass=Dummy2)
        self.assertTrue(u.resourceClass is usage2.resourceClass)

        # Ask for a non-existent usage class.
        self.assertRaises(error.NoSuchUsage,
                          self.reg.findUsage, 'dummy', 'GET',
                          usageResourceClass=Dummy3)

        # Ask for a non-existent toplevel.
        self.assertRaises(error.NoSuchToplevel,
                          self.reg.findUsage, 'sunny', 'PUT',
                          usageResourceClass=Dummy2)

        # Ask for a non-existent verb.
        self.assertRaises(error.NoSuchVerb,
                          self.reg.findUsage, 'dummy', 'PUT',
                          usageResourceClass=Dummy2)

    def TestUsageExamples(self):
        """
        Rather un-exciting test but at least the code is exercised and expected
        behaviour checked.
        """
        u = HTTPUsage('/dummy', 'an example of great profundity')
        request = 'foo'
        response = 'bar'
        description = 'baz'
        example = HTTPExample(request, response, description)
        u.addExample(example)
        self.assertEqual(1, len(u.examples))
        self.assertEqual('foo', u.examples[0].request)
        self.assertEqual('bar', u.examples[0].response)
        self.assertEqual('baz', u.examples[0].description)


class TestPayload(FluidinfoTestCase):

    def setUp(self):
        super(TestPayload, self).setUp()
        self.payload = Payload()

    def testEmpty(self):
        self.assertEqual([], self.payload.fields())

    def testContains(self):
        name = 'name'
        field = PayloadField(name, 'type', 'desc')
        self.payload.addField(field)
        self.assertTrue(name in self.payload)

    def testRepeatedAdd(self):
        name = 'name'
        field = PayloadField(name, 'type', 'desc')
        self.payload.addField(field)
        self.assertRaises(AssertionError, self.payload.addField, field)

    def testFromUsersPUT(self):
        self.payload.addField(PayloadField(
            'name', 'string', 'The real-world name of the new user.'))
        self.payload.addField(PayloadField(
            'password', 'string', 'The password for the new user.'))
        self.payload.addField(PayloadField(
            'email', 'string', 'The email address of the new user.'))
        for field in 'name', 'password', 'email':
            self.assertTrue(field in self.payload)
        names = [f.name for f in self.payload.fields()]
        self.assertEqual(names, ['email', 'name', 'password'])

    def testMandatory(self):
        self.assertFalse(self.payload.mandatory)

        field = PayloadField('f1', 'type', 'desc', mandatory=False)
        self.payload.addField(field)
        self.assertFalse(self.payload.mandatory)

        field = PayloadField('f2', 'type', 'desc', mandatory=True)
        self.payload.addField(field)
        self.assertTrue(self.payload.mandatory)

    def testUsageRequestPayloadMandatory1(self):
        # f = HTTPTopLevel('users', 'PUT')
        usage = HTTPUsage('/dummy', 'Bee-bop')
        payload = Payload()
        usage.addRequestPayload(payload)

        field = PayloadField('f1', 'type', 'desc', mandatory=False)
        payload.addField(field)
        self.assertFalse(usage.requestPayloadMandatory())

        field = PayloadField('f2', 'type', 'desc', mandatory=True)
        payload.addField(field)
        self.assertTrue(usage.requestPayloadMandatory())

    def testUsageRequestPayloadMandatory2(self):
        # f = HTTPTopLevel('users', 'PUT')
        usage = HTTPUsage('/dummy', 'Bee-bop')

        payload = Payload()
        usage.addRequestPayload(payload)
        field = PayloadField('f1', 'type', 'desc', mandatory=False)
        payload.addField(field)

        payload = Payload()
        payload.format = 'blah'
        usage.addRequestPayload(payload)
        field = PayloadField('f1', 'type', 'desc', mandatory=False)
        payload.addField(field)

        self.assertFalse(usage.requestPayloadMandatory())

        payload = JSONPayload()
        usage.addRequestPayload(payload)
        field = PayloadField('f1', 'type', 'desc', mandatory=True)
        payload.addField(field)

        self.assertTrue(usage.requestPayloadMandatory())
