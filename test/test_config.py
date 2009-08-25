import unittest
from saliweb.backend import Config
from StringIO import StringIO

basic_config = """
[database]
user: dbuser
db: testdb
passwd: dbtest

[directories]
incoming: /in
preprocessing: /preproc

[oldjobs]
archive: 30d
expire: 90d
"""

class ConfigTest(unittest.TestCase):
    """Check Config class"""

    def test_init(self):
        """Check Config init"""
        conf = Config(StringIO(basic_config))
        self.assertEqual(conf.database['user'], 'dbuser')
        self.assertEqual(conf.directories['INCOMING'], '/in')
        self.assertEqual(conf.directories['PREPROCESSING'], '/preproc')
        self.assertEqual(conf.directories['FAILED'], '/preproc')
        self.assertEqual(conf.oldjobs['expire'].days, 90)

if __name__ == '__main__':
    unittest.main()
