import unittest
import saliweb.build

class SetupTest(unittest.TestCase):
    """Check setup functions"""

    def test_setup_service_name(self):
        """Check _setup_service_name function"""
        def check(service_name, service_module):
            class DummyConfig: pass
            env = {}
            config = DummyConfig()
            config.service_name = service_name
            saliweb.build._setup_service_name(env, config)
            self.assertEqual(env['service_name'], service_name)
            self.assertEqual(env['service_module'], service_module)
        check('ModFoo', 'modfoo')
        check('MOD FOO', 'mod_foo')

if __name__ == '__main__':
    unittest.main()
