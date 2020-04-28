import unittest
from saliweb.backend import MySQLField

class MySQLFieldTest(unittest.TestCase):
    """Check MySQLField class"""

    def test_get_schema(self):
        """Check MySQLField.get_schema()"""
        field = MySQLField('name', 'VARCHAR(50)')
        self.assertEqual(field.index, False)
        self.assertEqual(field.get_schema(), 'name VARCHAR(50)')
        field = MySQLField('name', 'VARCHAR(50)', key='PRIMARY', null=False,
                           default='TEST')
        self.assertEqual(field.get_schema(),
                         "name VARCHAR(50) PRIMARY KEY NOT NULL DEFAULT 'TEST'")
        # Check mapping of MySQL DESCRIBE key types
        field = MySQLField('name', 'TEXT', key='PRI')
        self.assertEqual(field.get_schema(), "name TEXT PRIMARY KEY")
        field = MySQLField('name', 'TEXT', key='')
        self.assertEqual(field.get_schema(), "name TEXT")
        # Check mapping of MySQL DESCRIBE null types
        field = MySQLField('name', 'TEXT', null='YES')
        self.assertEqual(field.get_schema(), "name TEXT")
        field = MySQLField('name', 'TEXT', null='NO', default='DEF')
        self.assertEqual(field.get_schema(), "name TEXT NOT NULL DEFAULT 'DEF'")
        # default cannot be NULL if NULL is not allowed
        field = MySQLField('name', 'VARCHAR(50)', null=False, default=None)
        self.assertEqual(field.get_schema(),
                         "name VARCHAR(50) NOT NULL DEFAULT ''")
        # defaults cannot be given for TEXT fields
        field = MySQLField('name', 'text', null=False)
        self.assertEqual(field.get_schema(), "name text NOT NULL")
        # Check index
        field = MySQLField('name', 'TEXT', index=True)
        self.assertEqual(field.index, True)

    def test_equals(self):
        """Check MySQLField equality"""
        def make_pair():
            a = MySQLField('testname', 'testtype', null=False,
                           default='testdef', key='PRIMARY')
            b = MySQLField('testname', 'testtype', null=False,
                           default='testdef', key='PRIMARY')
            return a, b
        a,b = make_pair()
        self.assertEqual(a, b)
        self.assertTrue(not a != b)
        a,b = make_pair()
        a.name = 'othername'
        self.assertNotEqual(a, b)
        self.assertTrue(not a == b)
        a,b = make_pair()
        a.type = 'othertype'
        self.assertNotEqual(a, b)
        self.assertTrue(not a == b)
        a,b = make_pair()
        a.null = True
        self.assertNotEqual(a, b)
        self.assertTrue(not a == b)
        a,b = make_pair()
        a.default = 'otherdefault'
        self.assertNotEqual(a, b)
        self.assertTrue(not a == b)
        a,b = make_pair()
        a.key = None
        self.assertNotEqual(a, b)
        self.assertTrue(not a == b)
        a,b = make_pair()
        a.index = True
        self.assertNotEqual(a, b)
        self.assertTrue(not a == b)

if __name__ == '__main__':
    unittest.main()
