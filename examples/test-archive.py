import unittest
import modfoo
import saliweb.test
import os


class JobTests(saliweb.test.TestCase):
    """Check custom ModFoo Job class"""

    def test_archive(self):
        """Test the archive method"""
        # Make a ModFoo Job test job in ARCHIVED state
        j = self.make_test_job(modfoo.Job, 'ARCHIVED')
        # Run the rest of this testcase in the job's directory
        with saliweb.test.working_directory(j.directory):
            # Make a test PDB file and another incidental file
            with open('test.pdb', 'w') as f:
                print("test pdb", file=f)
            with open('test.txt', 'w') as f:
                print("text file", file=f)

            # Run the job's "archive" method
            j.archive()

            # Job's archive method should have gzipped every PDB file but not
            # anything else
            self.assertTrue(os.path.exists('test.pdb.gz'))
            self.assertFalse(os.path.exists('test.pdb'))
            self.assertTrue(os.path.exists('test.txt'))


if __name__ == '__main__':
    unittest.main()
