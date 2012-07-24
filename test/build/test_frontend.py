import unittest
import saliweb.build

class DummyEnv(dict):
    def Install(self, target, files):
        self.install_target = target
        self.install_files = files
    def Command(self, *args):
        if not hasattr(self, 'command_target'):
            self.command_target = []
        self.command_target.append(args)
    def Value(self, contents):
        pass
    def Clone(self):
        return DummyEnv(self)


class FrontendTest(unittest.TestCase):
    """Check alternate frontend functions"""

    def make_frontend(self, name):
        class DummyConfig:
            frontends = {'foo': {'service_name': 'Foo'} }

        env = DummyEnv()
        env['instdir'] = '/inst/'
        env['perldir'] = '/inst/lib'
        env['config'] = DummyConfig()
        return saliweb.build._make_frontend(env, name)

    def test_frontend_init(self):
        """Check init of Frontend class"""
        self.assertRaises(ValueError, self.make_frontend, 'bar')
        f = self.make_frontend('foo')
        self.assertEqual(f._name, 'foo')
        self.assertEqual(f._env['cgidir'], '/inst/foo/cgi')
        self.assertEqual(f._env['htmldir'], '/inst/foo/html')
        self.assertEqual(f._env['txtdir'], '/inst/foo/txt')

    def test_frontend_install_cgi(self):
        """Check Frontend.InstallCGIScripts() method"""
        f = self.make_frontend('foo')
        f.InstallCGIScripts(['mycgi'])
        self.assertEqual(len(f._env.command_target), 1)
        self.assertEqual(f._env.command_target[0][0], '/inst/foo/cgi/mycgi')

    def test_frontend_install_html(self):
        """Check Frontend.InstallHTML() method"""
        f = self.make_frontend('foo')
        f.InstallHTML(['myhtml'])
        self.assertEqual(f._env.install_target, '/inst/foo/html')
        self.assertEqual(f._env.install_files, ['myhtml'])

    def test_frontend_install_txt(self):
        """Check Frontend.InstallTXT() method"""
        f = self.make_frontend('foo')
        f.InstallTXT(['mytxt'])
        self.assertEqual(f._env.install_target, '/inst/foo/txt')
        self.assertEqual(f._env.install_files, ['mytxt'])

if __name__ == '__main__':
    unittest.main()
