# Mock for database access; use sqlite3 in memory rather than MySQL

import sqlite3
import hashlib
import calendar
import datetime


# sqlite doesn't have a datetime type, so we use float
# instead (UTC seconds-since-epoch) for testing
def adapt_datetime(ts):
    return calendar.timegm(ts.timetuple())


sqlite3.register_adapter(datetime.datetime, adapt_datetime)


MOCK_DB_SETUP = [
    "ATTACH DATABASE ':memory:' as servers",
    "CREATE TABLE servers.servers (server TEXT, access TEXT, url TEXT, "
    "    title TEXT, short_title TEXT)",
    "CREATE TABLE servers.access (user_name TEXT, server TEXT)",
    "CREATE TABLE servers.users (user_id INT, user_name TEXT, password TEXT, "
    "    ip_addr TEXT, login_time INT, first_name TEXT, last_name TEXT, "
    "    email TEXT, admin TEXT, date_added TEXT, last_modified INT, "
    "    institution TEXT, modeller_key TEXT, reset_key TEXT, "
    "    reset_key_expires FLOAT)",
    "INSERT INTO servers (server,access,url,title,short_title) VALUES "
    "    ('public', 'academic', 'https://serv1', 'long title1', 'short1')",
    "INSERT INTO servers (server,access,url,title,short_title) VALUES "
    "    ('private', 'academic', 'https://serv2', 'long title2', 'short2')",
    "INSERT INTO access (user_name,server) VALUES ('Anonymous', 'public')",
    "INSERT INTO access (user_name,server) VALUES ('authuser', 'private')",
    "INSERT INTO users (user_id,user_name,password,first_name,last_name,email,"
    "    institution,modeller_key) VALUES (1, 'authuser', "
    "    PASSWORD('authpw00'), 'Auth', 'User', 'authuser@test.com', "
    "    'Test In1', 'authusermodkey')",
    "INSERT INTO users (user_id,user_name,password,first_name,last_name,email,"
    "    institution,modeller_key,reset_key,reset_key_expires) "
    "    VALUES (2, 'unauthuser', PASSWORD('unauthpw'), "
    "    'Unauth', 'User', 'unauthuser@test.com', 'Test In2', 'modkey', "
    "    'unauthkey', %s)" % adapt_datetime(datetime.datetime.now() +
                                            datetime.timedelta(days=2)),
    "INSERT INTO users (user_id,user_name,password,first_name,last_name,email,"
    "    institution,modeller_key) VALUES (3, 'badrecipuser', "
    "    PASSWORD('authpw02'), 'Auth', 'User', 'badrecip@test.com', "
    "    'Test In3', 'authusermodkey')",
]


class MockCursor(object):
    def __init__(self, conn):
        self.sql, self.db = conn.sql, conn.db
        self.dbcursor = self.db.cursor()

    def execute(self, statement, args=()):
        self.sql.append(statement)
        # sqlite uses ? as a placeholder; MySQL uses %s
        self.dbcursor.execute(statement.replace('%s', '?'), args)

    def fetchone(self):
        return self.dbcursor.fetchone()

    def __iter__(self):
        fa = self.dbcursor.fetchall()
        return fa.__iter__()


def _sqlite_password(p):
    """Provide a simple (insecure!) implementation of PASSWORD for sqlite"""
    p = p.encode('utf-8')
    return hashlib.md5(p).hexdigest()


class MockConnection(object):
    def __init__(self, *args, **keys):
        self.args = args
        self.keys = keys
        self.db = sqlite3.connect(":memory:")
        self.db.create_function("PASSWORD", 1, _sqlite_password)
        self.sql = []
        self._populate_mock_db()

    def set_character_set(self, cs):
        pass

    def _populate_mock_db(self):
        c = self.db.cursor()
        for sql in MOCK_DB_SETUP:
            c.execute(sql)

    def cursor(self):
        return MockCursor(self)

    def close(self):
        self.db.close()


def connect(*args, **keys):
    return MockConnection(*args, **keys)
