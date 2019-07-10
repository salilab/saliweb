import unittest
import saliweb.test

# Import the modfoo frontend with mocks
modfoo = saliweb.test.import_mocked_frontend("modfoo", __file__,
                                             '../../frontend')


class Tests(saliweb.test.TestCase):

    def test_index(self):
        """Test index page"""
        c = modfoo.app.test_client()
        rv = c.get('/')
        self.assertIn('ModFoo: Modeling using Foo', rv.data)


if __name__ == '__main__':
    unittest.main()
