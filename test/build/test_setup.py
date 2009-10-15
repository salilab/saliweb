import unittest
import saliweb.build

class DummyConfig: pass

class SetupTest(unittest.TestCase):
    """Check setup functions"""

    def test_setup_service_name(self):
        """Check _setup_service_name function"""
        def check(service_name, service_module):
            env = {}
            config = DummyConfig()
            config.service_name = service_name
            saliweb.build._setup_service_name(env, config)
            self.assertEqual(env['service_name'], service_name)
            self.assertEqual(env['service_module'], service_module)
        check('ModFoo', 'modfoo')
        check('MOD FOO', 'mod_foo')

    def test_setup_install_directories(self):
        """Check _setup_install_directories function"""
        config = DummyConfig()
        config.directories = {'install': '/foo/bar/'}
        env = {'config': config}
        saliweb.build._setup_install_directories(env)
        for key, value in (('instdir', '/foo/bar/'),
                           ('bindir', '/foo/bar/bin'),
                           ('confdir', '/foo/bar/conf'),
                           ('pythondir', '/foo/bar/python'),
                           ('htmldir', '/foo/bar/html'),
                           ('txtdir', '/foo/bar/txt'),
                           ('cgidir', '/foo/bar/cgi'),
                           ('perldir', '/foo/bar/lib')):
            self.assertEqual(env[key], value)
            del env[key]
        del env['config']
        # Make sure it didn't create any additional directory keys
        self.assertEqual(env, {})

if __name__ == '__main__':
    unittest.main()
