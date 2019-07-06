from __future__ import print_function
import sys
# Mock of MySQLdb


class _MockCursor(object):
    def execute(self, sql, args):
        self.sql, self.args = sql, args

    def fetchone(self):
        if self.sql == 'SELECT COUNT(name) FROM jobs WHERE name=%s':
            if self.args[0].startswith('running-job'):
                return [1]
            else:
                return [0]


class _MockConnection(object):
    def cursor(self):
        return _MockCursor()

    def commit(self):
        pass


def connect(*args, **kwargs):
    return _MockConnection()
