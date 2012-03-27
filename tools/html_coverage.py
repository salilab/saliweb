import glob

# Only use coverage if it's new enough
try:
    import coverage
    if not hasattr(coverage.coverage, 'combine'):
        coverage = None
except ImportError:
    coverage = None

def action(target, source, env):
    if coverage:
        topdir = 'python'
        mods = ["%s/saliweb/__init__.py" % topdir] \
               + glob.glob("%s/saliweb/build/*.py" % topdir) \
               + glob.glob("%s/saliweb/backend/*.py" % topdir)

        cov = coverage.coverage(branch=True)
        cov.combine()
        cov.file_locator.relative_dir = topdir + '/'
        cov.html_report(mods, directory='test/html_coverage')
    else:
        print "Could not find new enough coverage module"
        return 1
