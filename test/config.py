import saliweb.backend
import tempfile
import os
import shutil

class Config(saliweb.backend.Config):
    """Custom subclass of Config that captures email rather than sending it"""
    def __init__(self, fh):
        saliweb.backend.Config.__init__(self, fh)
        self.__tmpdir = tempfile.mkdtemp()
        self._mailer = os.path.join(self.__tmpdir, 'mailer')
        self.__mailoutput = os.path.join(self.__tmpdir, 'output')
        f = open(self._mailer, 'w')
        print >> f, """#!/usr/bin/python
import sys
open('%s', 'w').write(sys.stdin.read())
""" % self.__mailoutput
        f.close()
        os.chmod(self._mailer, 0755)

    def __del__(self):
        shutil.rmtree(self.__tmpdir)

    def get_mail_output(self):
        return open(self.__mailoutput).read()

    def _read_db_auth(self, end):
        self.database['user'] = self.database['passwd'] = 'test'
