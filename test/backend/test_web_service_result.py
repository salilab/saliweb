import unittest
import os
import StringIO
import urllib
from saliweb.backend import SaliWebServiceResult

testurl = 'http://modbase.compbio.ucsf.edu/modloop/job/job_279120/' + \
          'output.pdb?passwd=oGHxb7R3xy'

def dummy_urlopen(url):
    return StringIO.StringIO('dummy')


class Test(unittest.TestCase):
    """Test the SaliWebServiceResult class."""

    def test_get_filename(self):
        """Test get_filename() method"""
        r = SaliWebServiceResult(testurl)
        self.assertEqual(r.get_filename(), 'output.pdb')

    def test_download(self):
        """Test download() method"""
        r = SaliWebServiceResult('http://modbase.compbio.ucsf.edu/modloop/' \
                                 'job/job_279120/output.pdb?passwd=oGHxb7R3xy')
        old = urllib.urlopen
        try:
            urllib.urlopen = dummy_urlopen
            sio = StringIO.StringIO()
            r.download(fh=sio)
            self.assertEqual(sio.getvalue(), 'dummy')
            r.download()
            r = open('output.pdb').read()
            self.assertEqual(r, 'dummy')
            os.unlink('output.pdb')
        finally:
            urllib.urlopen = old

if __name__ == '__main__':
    unittest.main()
