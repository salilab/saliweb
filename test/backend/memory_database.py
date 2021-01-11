try:
    import sqlite3
except ImportError:
    from pysqlite2 import dbapi2 as sqlite3
import datetime
import calendar
import saliweb.backend


# sqlite doesn't have a datetime type, so we use float
# instead (UTC seconds-since-epoch) for testing
def adapt_datetime(ts):
    return calendar.timegm(ts.timetuple())


sqlite3.register_adapter(datetime.datetime, adapt_datetime)


def utc_timestamp():
    return adapt_datetime(datetime.datetime.utcnow())


class MemoryDatabase(saliweb.backend.Database):
    """Subclass that uses an in-memory SQLite3 database rather than MySQL"""
    def _connect(self, config):
        self._placeholder = '?'
        self.config = config
        self.conn = sqlite3.connect(':memory:')
        # sqlite has no date/time functions, unlike MySQL, so add basic ones
        self.conn.create_function('UTC_TIMESTAMP', 0, utc_timestamp)
        # sqlite has no enum field, so hack it to look like a text field
        assert self._fields[6].name == 'state'
        self._fields[6].type = 'TEXT'
