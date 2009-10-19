import warnings

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
