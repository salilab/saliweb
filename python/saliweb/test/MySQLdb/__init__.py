# Mock of MySQLdb

from . import cursors

class _MockCursor(object):
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, args=()):
        self.sql, self.args = sql, args

    def fetchone(self):
        if self.sql == 'SELECT COUNT(name) FROM jobs WHERE name=%s':
            if self.args[0].startswith('running-job'):
                return [1]
            else:
                return [0]
        if (self.sql == 'SELECT email FROM servers.users WHERE user_name=%s '
                        'AND password=%s'):
            if self.args[1] == 'goodpwcrypt':
                return ['testemail']


class _MockConnection(object):
    def __init__(self):
        self._jobs = []

    def cursor(self):
        return _MockCursor(self)

    def commit(self):
        pass

    def close(self):
        pass


def connect(*args, **kwargs):
    return _MockConnection()
