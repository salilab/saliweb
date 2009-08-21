import unittest
from StringIO import StringIO
from saliweb.backend import SGERunner

class RunnerTest(unittest.TestCase):
    """Check SGERunner"""

    def test_generate_script(self):
        """Check that SGERunner generates reasonable scripts"""
        r = SGERunner('echo foo', interpreter='/bin/csh')
        r.set_sge_options('-l diva1=1G')
        sio = StringIO()
        r._write_sge_script(sio)
        expected = """#!/bin/csh
#$ -S /bin/csh
#$ -cwd
#$ -l diva1=1G
setenv _SALI_JOB_DIR `pwd`
echo "STARTED" > ${_SALI_JOB_DIR}/job-state
echo foo
echo "DONE" > ${_SALI_JOB_DIR}/job-state
"""
        self.assertEqual(sio.getvalue(), expected)

if __name__ == '__main__':
    unittest.main()
