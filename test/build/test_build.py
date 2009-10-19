import unittest
import saliweb.build
import os

class BuildTest(unittest.TestCase):
    """Miscellaneous checks of the saliweb.build module"""

    def test_format_shell_command(self):
        """Check _format_shell_command function"""
        class DummyConfig: pass
        class DummyEnv(dict):
            def __init__(self, user):
                dict.__init__(self)
                self['config'] = c = DummyConfig()
                c.backend = {'user': user}
        env = DummyEnv('testuser')

        # If user = sudouser, or sudo is not being used,
        # display the command as-is
        os.environ['SUDO_USER'] = 'testuser'
        self.assertEquals(saliweb.build._format_shell_command(env, 'foo'),
                          'foo')
        del os.environ['SUDO_USER']
        self.assertEquals(saliweb.build._format_shell_command(env, 'foo'),
                          'foo')

        # If user != sudouser, add suitable sudo invocation
        os.environ['SUDO_USER'] = 'otheruser'
        self.assertEquals(saliweb.build._format_shell_command(env, 'foo'),
                          '/usr/bin/sudo -u testuser foo')
        del os.environ['SUDO_USER']

if __name__ == '__main__':
    unittest.main()
