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
expire: %s
"""

class ConfigTest(unittest.TestCase):
    """Check Config class"""

    def test_init(self):
        """Check Config init"""
        conf = Config(StringIO(basic_config % '90d'))
        self.assertEqual(conf.database['user'], 'dbuser')
        self.assertEqual(conf.directories['INCOMING'], '/in')
        self.assertEqual(conf.directories['PREPROCESSING'], '/preproc')
        self.assertEqual(conf.directories['FAILED'], '/preproc')
        self.assertEqual(conf.oldjobs['expire'].days, 90)

    def test_time_deltas(self):
        """Check parsing of time deltas in config files"""
        # Check integer hours, days, months, years
        conf = Config(StringIO(basic_config % '8h'))
        self.assertEqual(conf.oldjobs['expire'].seconds, 8*60*60)
        conf = Config(StringIO(basic_config % '5d'))
        self.assertEqual(conf.oldjobs['expire'].days, 5)
        conf = Config(StringIO(basic_config % '2m'))
        self.assertEqual(conf.oldjobs['expire'].days, 60)
        conf = Config(StringIO(basic_config % '1y'))
        self.assertEqual(conf.oldjobs['expire'].days, 365)
        # Check valid floating point
        conf = Config(StringIO(basic_config % '0.5d'))
        self.assertEqual(conf.oldjobs['expire'].seconds, 12*60*60)
        conf = Config(StringIO(basic_config % '1e3d'))
        self.assertEqual(conf.oldjobs['expire'].days, 1000)
        # Other suffixes or non-floats should raise an error
        self.assertRaises(ValueError, Config, StringIO(basic_config % '8s'))
        self.assertRaises(ValueError, Config, StringIO(basic_config % 'foo'))

if __name__ == '__main__':
    unittest.main()
