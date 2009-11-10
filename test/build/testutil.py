import warnings
import tempfile
import os
import glob
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

def get_open_files():
    """Get a list of all files currently opened by this process"""
    pid = os.getpid()
    fd = os.path.join('/proc', '%s' % pid, 'fd')
    if not os.path.exists(fd):
        raise NotImplementedError("Needs a mounted /proc filesystem")
    for f in glob.glob('%s/*' % fd):
        try:
            yield os.readlink(f)
        except OSError:
            pass
