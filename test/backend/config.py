import saliweb.backend
import tempfile
import os
import shutil
import sys


class Config(saliweb.backend.Config):
    """Custom subclass of Config that captures email rather than sending it"""
    def __init__(self, fh):
        saliweb.backend.Config.__init__(self, fh)
        self.__tmpdir = tempfile.mkdtemp()
        self._mailer = os.path.join(self.__tmpdir, 'mailer')
        self.__mailoutput = os.path.join(self.__tmpdir, 'output')
        with open(self._mailer, 'w') as f:
            print("""#!%s
import sys
with open('%s', 'w') as fh:
    fh.write(sys.stdin.read())
""" % (sys.executable, self.__mailoutput), file=f)
        os.chmod(self._mailer, 0o755)

    def __del__(self):
        try:
            shutil.rmtree(self.__tmpdir)
        except AttributeError:
            pass

    def get_mail_output(self):
        try:
            with open(self.__mailoutput) as fh:
                return fh.read()
        except IOError:
            return None

    def _read_db_auth(self, end):
        self.database['user'] = self.database['passwd'] = 'test'
