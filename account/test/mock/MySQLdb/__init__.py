# Mock for database access; use sqlite3 in memory rather than MySQL

import sqlite3
import hashlib


MOCK_DB_SETUP = [
    "ATTACH DATABASE ':memory:' as servers",
    "CREATE TABLE servers.servers (server TEXT, access TEXT, url TEXT, "
    "    title TEXT, short_title TEXT)",
    "CREATE TABLE servers.access (user_name TEXT, server TEXT)",
    "CREATE TABLE servers.users (user_id INT, user_name TEXT, password TEXT, "
    "    ip_addr TEXT, login_time INT, first_name TEXT, last_name TEXT, "
    "    email TEXT, admin TEXT, date_added TEXT, last_modified INT, "
    "    institution TEXT)",
    "INSERT INTO servers (server,access,url,title,short_title) VALUES "
    "    ('public', 'academic', 'https://serv1', 'long title1', 'short1')",
    "INSERT INTO servers (server,access,url,title,short_title) VALUES "
    "    ('private', 'academic', 'https://serv2', 'long title2', 'short2')",
    "INSERT INTO access (user_name,server) VALUES ('Anonymous', 'public')",
    "INSERT INTO access (user_name,server) VALUES ('authuser', 'private')",
    "INSERT INTO users (user_id,user_name,password,first_name,last_name,email,"
    "    institution) VALUES (1, 'authuser', PASSWORD('authpw00'), 'Auth', "
    "    'User', 'authuser@test.com', 'Test In1')",
    "INSERT INTO users (user_id,user_name,password,first_name,last_name,email,"
    "    institution) VALUES (2, 'unauthuser', PASSWORD('unauthpw'), "
    "    'Unauth', 'User', 'unauthuser@test.com', 'Test In2')",
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
    return hashlib.md5(p).hexdigest()


class MockConnection(object):
    def __init__(self, *args, **keys):
        self.args = args
        self.keys = keys
        self.db = sqlite3.connect(":memory:")
        self.db.create_function("PASSWORD", 1, _sqlite_password)
        self.sql = []
        self._populate_mock_db()

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
