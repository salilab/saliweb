import warnings
import tempfile
import os
import glob
import shutil
import contextlib

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

class _TempDir(object):
    def __init__(self, origdir, tmpdir):
        self.origdir, self.tmpdir = origdir, tmpdir

@contextlib.contextmanager
def temp_working_dir():
    """Simple context manager to run some code in a temporary directory"""
    origdir = os.getcwd()
    tmpdir = tempfile.mkdtemp()
    os.chdir(tmpdir)
    yield _TempDir(origdir, tmpdir)
    os.chdir(origdir)
    shutil.rmtree(tmpdir, ignore_errors=True)


@contextlib.contextmanager
def temp_dir():
    """Simple context manager to make a temporary directory"""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)

def run_in_tempdir(func):
    """Decorate a test method to run it entirely in a temporary directory"""
    def wrapper(*args, **kwargs):
        with temp_working_dir():
            func(*args, **kwargs)
    return wrapper

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
