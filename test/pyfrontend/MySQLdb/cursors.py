class DictCursor(object):
    def __init__(self, conn):
        pass

    def execute(self, sql, args):
        self.sql, self.args = sql, args

    def fetchone(self):
        if self.sql == 'SELECT * FROM jobs WHERE name=%s AND passwd=%s':
            if self.args[0] == 'expired-job':
                return {'state': 'EXPIRED'}
            elif self.args[0] == 'running-job':
                return {'state': 'RUNNING'}
            elif self.args[0] == 'completed-job':
                return {'state': 'COMPLETED', 'name': self.args[0],
                        'passwd': self.args[1], 'archive_time': None,
                        'directory': '/test/job'}
