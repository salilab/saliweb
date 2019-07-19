import sqlite3
from . import MockCursor


class DictCursor(MockCursor):
    def __init__(self, conn):
        self._oldrf = conn.db.row_factory
        conn.db.row_factory = sqlite3.Row
        super(DictCursor, self).__init__(conn)

    def __del__(self):
        if hasattr(self, 'db'):
            self.db.row_factory = self._oldrf
