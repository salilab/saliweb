import unittest
import os
import io
import sys
try:
    import urllib.request as urllib2 # python 3
except ImportError:
    import urllib2  # python 2
from saliweb.backend import SaliWebServiceResult

testurl = 'http://modbase.compbio.ucsf.edu/modloop/job/job_279120/' + \
          'output.pdb?passwd=oGHxb7R3xy'

def dummy_urlopen(url):
    cls = io.StringIO if sys.version_info[0] >= 3 else io.BytesIO
    return cls('dummy')


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
        old = urllib2.urlopen
        try:
            urllib2.urlopen = dummy_urlopen
            sio = io.StringIO() if sys.version_info[0] >= 3 else io.BytesIO()
            r.download(fh=sio)
            self.assertEqual(sio.getvalue(), 'dummy')
            r.download()
            with open('output.pdb') as fh:
                r = fh.read()
            self.assertEqual(r, 'dummy')
            os.unlink('output.pdb')
        finally:
            urllib2.urlopen = old

if __name__ == '__main__':
    unittest.main()
