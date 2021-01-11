# Dummy implementation to test the Database._connect() method

OperationalError = 'Dummy MySQL OperationalError'


class DummyCursor(object):
    def __init__(self, sql):
        self.sql = sql

    def execute(self, statement):
        self.sql.append(statement)


class DummyConnection(object):
    def __init__(self, *args, **keys):
        self.args = args
        self.keys = keys
        self.sql = []

    def cursor(self):
        return DummyCursor(self.sql)


def connect(*args, **keys):
    return DummyConnection(*args, **keys)
