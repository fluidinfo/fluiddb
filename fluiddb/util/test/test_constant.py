from fluiddb.testing.basic import FluidinfoTestCase
from fluiddb.util.constant import Constant, ConstantEnum


class ConstantTest(FluidinfoTestCase):

    def testInstantiate(self):
        """A L{Constant} includes an ID and a name."""
        constant = Constant(42, 'VALUE')
        self.assertEqual(42, constant.id)
        self.assertEqual('VALUE', constant.name)

    def testStr(self):
        """
        L{Constant.name} is returned when a constant is converted to a string.
        """
        constant = Constant(42, 'VALUE')
        self.assertEqual('VALUE', str(constant))

    def testRepr(self):
        """
        A helpful string is generated when C{repr} is used with a L{Constant}.
        """
        constant = Constant(42, 'VALUE')
        self.assertEqual('<Constant id=42 name=VALUE>', repr(constant))


class ConstantEnumTest(FluidinfoTestCase):

    def testProperty(self):
        """
        A L{ConstantEnum} extracts L{Constant} values from the enumeration
        class specified when a property is defined and only accepts those
        values as valid possibilities.
        """

        class SampleEnum(object):

            VALUE = Constant(1, 'VALUE')
            unacceptable = 10

        class SampleStormClass(object):

            __storm_table__ = 'sample_storm_class'

            enum = ConstantEnum(enum_class=SampleEnum, primary=True)

        sample = SampleStormClass()
        sample.enum = SampleEnum.VALUE
        self.assertIdentical(SampleEnum.VALUE, sample.enum)
        self.assertRaises(ValueError, setattr, sample, 'enum',
                          SampleEnum.unacceptable)
