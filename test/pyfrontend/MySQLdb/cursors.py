import datetime


def _utcnow():
    """Get the current UTC time and date"""
    # MySQLdb uses naive datetime objects. We store all dates in the DB
    # in UTC. This function replaces datetime.datetime.utcnow() as that has
    # been deprecated in modern Python.
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None)


class DictCursor(object):
    def __init__(self, conn):
        pass

    def execute(self, sql, args=()):
        self.sql, self.args = sql, args

    def fetchone(self):
        if self.sql == 'SELECT * FROM jobs WHERE name=%s AND passwd=%s':
            if self.args[0] == 'expired-job':
                return {'state': 'EXPIRED'}
            elif self.args[0] == 'running-job':
                return {'state': 'RUNNING', 'contact_email': 'test@test.com',
                        'submit_time': _utcnow()
                        - datetime.timedelta(seconds=10)}
            elif self.args[0] == 'completed-job':
                return {'state': 'COMPLETED', 'name': self.args[0],
                        'passwd': self.args[1], 'archive_time': None,
                        'directory': '/test/job',
                        'contact_email': 'test@test.com'}
        elif (self.sql == 'SELECT first_name,last_name,email,institution,'
                          'modeller_key FROM servers.users WHERE user_name=%s '
                          'AND password=%s'):
            if self.args[1] == 'goodpwcrypt':
                return {'email': 'testemail', 'first_name': 'foo',
                        'last_name': 'bar', 'institution': 'testin',
                        'modeller_key': 'modkey'}

    def __iter__(self):
        return iter([])
