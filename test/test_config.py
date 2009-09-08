import unittest
from saliweb.backend import Config, ConfigError
from StringIO import StringIO

basic_config = """
[general]
admin_email: test@salilab.org
service_name: test_service
state_file: state_file
socket: test.socket
check_minutes: 10

[database]
db: testdb
frontend_config: frontend.conf
backend_config: backend.conf

[directories]
install: /
incoming: /in
preprocessing: /preproc

[oldjobs]
archive: %s
expire: %s
"""

def get_config(archive='3h', expire='90d'):
    return Config(StringIO(basic_config % (archive, expire)))

class ConfigTest(unittest.TestCase):
    """Check Config class"""

    def test_init(self):
        """Check Config init"""
        conf = get_config()
        self.assertEqual(conf.database['frontend_config'], 'frontend.conf')
        self.assertEqual(conf.directories['INCOMING'], '/in')
        self.assertEqual(conf.directories['PREPROCESSING'], '/preproc')
        self.assertEqual(conf.directories['FAILED'], '/preproc')
        self.assertEqual(conf.oldjobs['expire'].days, 90)
        self.assertEqual(conf.admin_email, 'test@salilab.org')

    def test_time_deltas(self):
        """Check parsing of time deltas in config files"""
        # Check integer hours, days, months, years
        conf = get_config(expire='8h')
        self.assertEqual(conf.oldjobs['expire'].seconds, 8*60*60)
        conf = get_config(expire='5d')
        self.assertEqual(conf.oldjobs['expire'].days, 5)
        conf = get_config(expire='2m')
        self.assertEqual(conf.oldjobs['expire'].days, 60)
        conf = get_config(expire='1y')
        self.assertEqual(conf.oldjobs['expire'].days, 365)
        # Check valid floating point
        conf = get_config(expire='0.5d')
        self.assertEqual(conf.oldjobs['expire'].seconds, 12*60*60)
        conf = get_config(expire='1e3d')
        self.assertEqual(conf.oldjobs['expire'].days, 1000)
        # Check NEVER
        conf = get_config(expire='never')
        self.assertEqual(conf.oldjobs['expire'], None)
        # Other suffixes or non-floats should raise an error
        self.assertRaises(ValueError, get_config, expire='8s')
        self.assertRaises(ValueError, get_config, expire='foo')
        # archive time cannot be greater than expire
        self.assertRaises(ConfigError, get_config, expire='1y', archive='never')
        self.assertRaises(ConfigError, get_config, expire='1y', archive='2y')
        conf = get_config(expire='1y', archive='1y')
        conf = get_config(expire='never', archive='never')

if __name__ == '__main__':
    unittest.main()
