import unittest
from saliweb.backend import Config, ConfigError
import sys
if sys.version_info[0] >= 3:
    from io import StringIO
else:
    from io import BytesIO as StringIO
import config
try:
    from email.mime.text import MIMEText  # python3
except ImportError:
    from email.MIMEText import MIMEText  # python2
import re
import testutil

basic_config = """
[general]
admin_email: test@salilab.org
service_name: test_service
socket: test.socket
%s

[backend]
user: test
state_file: state_file
check_minutes: 10

[frontend:foo]
service_name: Foo

[frontend:bar]
service_name: Bar

[database]
db: testdb
frontend_config: frontend.conf
backend_config: backend.conf

[directories]
install: /
incoming: /in
preprocessing: /preproc
%s

[oldjobs]
archive: %s
expire: %s
"""

def get_config(archive='3h', expire='90d', extra='', extradir='',
               config_class=Config, general_extra=''):
    return config_class(StringIO(basic_config % (general_extra, extradir,
                                                 archive, expire) + extra))

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
        self.assertEqual(conf.limits['running'], 5)
        self.assertFalse('concurrent_tasks' in conf.limits)
        self.assertFalse(conf.track_hostname)
        self.assertEqual(len(conf.frontends.keys()), 2)
        self.assertEqual(conf.frontends['foo']['service_name'], 'Foo')
        self.assertEqual(conf.frontends['bar']['service_name'], 'Bar')

        conf = get_config(general_extra='track_hostname: True')
        self.assertTrue(conf.track_hostname)
        conf = get_config(general_extra='track_hostname: False')
        self.assertFalse(conf.track_hostname)

        conf = get_config(extra='[limits]\nconcurrent_tasks: 10')
        self.assertEqual(conf.limits['concurrent_tasks'], 10)

        conf = get_config(extra='[limits]\nconcurrent_tasks: 10')
        self.assertEqual(conf.limits['concurrent_tasks'], 10)

    def test_send_email(self):
        """Check Config.send_email()"""
        for to in ['testto', ['testto'], ('testto',)]:
            for body in ('testbody', MIMEText('testbody')):
                conf = get_config(config_class=config.Config)
                conf.send_email(to, 'testsubj', body)
                mail = conf.get_mail_output()
                self.assertTrue(re.search('Subject: testsubj.*From: '
                                   'test@salilab\.org.*To: testto.*testbody',
                                   mail, flags=re.DOTALL),
                             'Unexpected mail output: ' + mail)

    def test_directory_defaults(self):
        """Check Config directory defaults"""
        # FAILED and ARCHIVED default to COMPLETED
        conf = get_config(extradir='completed: /foo')
        self.assertEqual(conf.directories['FAILED'], '/foo')
        self.assertEqual(conf.directories['ARCHIVED'], '/foo')
        # COMPLETED and later default to FINALIZING
        conf = get_config(extradir='finalizing: /fin\narchived:/arch')
        self.assertEqual(conf.directories['COMPLETED'], '/fin')
        self.assertEqual(conf.directories['FAILED'], '/fin')
        self.assertEqual(conf.directories['ARCHIVED'], '/arch')
        conf = get_config(extradir='finalizing: /fin')
        self.assertEqual(conf.directories['ARCHIVED'], '/fin')
        # FINALIZING defaults to POSTPROCESSING
        conf = get_config(extradir='postprocessing: /postproc')
        self.assertEqual(conf.directories['FINALIZING'], '/postproc')
        # POSTPROCESSING defaults to RUNNING
        conf = get_config(extradir='running: /running')
        self.assertEqual(conf.directories['POSTPROCESSING'], '/running')

    def test_time_deltas(self):
        """Check parsing of time deltas in config files"""
        # Check integer hours, days, months, years
        conf = get_config(expire='8h')
        self.assertEqual(conf.oldjobs['expire'].seconds, 8*60*60)
        conf = get_config(expire='5d')
        self.assertEqual(conf.oldjobs['expire'].days, 5)
        conf = get_config(expire='2w')
        self.assertEqual(conf.oldjobs['expire'].days, 14)
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
        self.assertIsNone(conf.oldjobs['expire'])
        # Other suffixes or non-floats should raise an error
        self.assertRaises(ValueError, get_config, expire='8s')
        self.assertRaises(ValueError, get_config, expire='4.garbageh')
        self.assertRaises(ValueError, get_config, expire='foo')
        # archive time cannot be greater than expire
        self.assertRaises(ConfigError, get_config, expire='1y', archive='never')
        self.assertRaises(ConfigError, get_config, expire='1y', archive='2y')
        conf = get_config(expire='1y', archive='1y')
        conf = get_config(expire='never', archive='never')

if __name__ == '__main__':
    unittest.main()
