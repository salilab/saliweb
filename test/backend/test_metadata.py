import unittest
from saliweb.backend import _JobMetadata

class MetadataTest(unittest.TestCase):
    """Check JobMetadata class"""

    def test_init(self):
        """Check creation of _JobMetadata class"""
        m = _JobMetadata(['key1', 'key2', 'state'], ['value1', 'value2', 'foo'])
        # state key should be removed
        self.assertEqual(len(m.keys()), 2)

    def test_get(self):
        """Check _JobMetadata get methods"""
        m = _JobMetadata(['key1', 'key2', 'state'], ['value1', 'value2', 'foo'])
        self.assertEqual(m['key1'], 'value1')
        self.assertEqual(m.get('key1'), 'value1')
        self.assertEqual(m.get('nokey', 'bar'), 'bar')
        self.assertEqual(m.get('nokey'), None)
        self.assertRaises(KeyError, m.__getitem__, 'nokey')
        k = sorted(m.keys())
        self.assertEqual(k, ['key1', 'key2'])
        v = sorted(m.values())
        self.assertEqual(v, ['value1', 'value2'])

    def test_set(self):
        """Check _JobMetadata set methods and syncing"""
        m = _JobMetadata(['key1', 'key2', 'state'], ['value1', 'value2', 'foo'])
        self.assertEqual(m.needs_sync(), False)
        self.assertRaises(KeyError, m.__setitem__, 'nokey', 'bar')
        m['key1'] = 'value1'
        self.assertEqual(m.needs_sync(), False)
        m['key1'] = 'value2'
        self.assertEqual(m.needs_sync(), True)
        m.mark_synced()
        self.assertEqual(m.needs_sync(), False)

if __name__ == '__main__':
    unittest.main()
