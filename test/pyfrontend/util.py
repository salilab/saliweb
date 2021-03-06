import contextlib
import tempfile
import shutil


@contextlib.contextmanager
def temporary_directory():
    """Simple context manager to make a temporary directory"""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)
