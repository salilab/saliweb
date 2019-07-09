import datetime

class DictCursor(object):
    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, args=()):
        self.sql, self.args = sql, args

    def fetchone(self):
        if self.sql == 'SELECT * FROM jobs WHERE name=%s AND passwd=%s':
            for j in self.conn._jobs:
                if self.args == (j.name, j.passwd):
                    return {'state': 'COMPLETED', 'name': j.name,
                            'passwd': j.passwd,
                            'archive_time': datetime.datetime(year=2099,
                                                              month=1, day=1),
                            'directory': j.directory}

    def __iter__(self):
        return iter([])
