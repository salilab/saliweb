import warnings
import tempfile
import os
import shutil

def run_catch_warnings(method, *args, **keys):
    """Run a method and return both its own return value and a list of any
       warnings raised."""
    warnings.simplefilter("always")
    oldwarn = warnings.showwarning
    w  = []
    def myshowwarning(*args):
        w.append(args)
    warnings.showwarning = myshowwarning

    try:
        ret = method(*args, **keys)
        return ret, w
    finally:
        warnings.showwarning = oldwarn
        warnings.resetwarnings()

class RunInTempDir(object):
    """Simple RAII-style class to run a test in a temporary directory"""
    def __init__(self):
        self.origdir = os.getcwd()
        self.tmpdir = tempfile.mkdtemp()
        os.chdir(self.tmpdir)
    def __del__(self):
        os.chdir(self.origdir)
        shutil.rmtree(self.tmpdir, ignore_errors=True)
