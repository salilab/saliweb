import glob
import os

# Only use coverage if it's new enough
try:
    import coverage
    if not hasattr(coverage.coverage, 'combine'):
        coverage = None
except ImportError:
    coverage = None

def fixup_perl_html_coverage(subdir):
    prefix = os.path.abspath('perl') + '/'
    urlprefix=prefix.replace('/', '-')
    os.rename(os.path.join(subdir, 'coverage.html'),
              os.path.join(subdir, 'index.html'))
    # Remove prefixes from file coverage pages
    for f in glob.glob(os.path.join(subdir, '%s*.html' % urlprefix)):
        b = os.path.basename(f)
        os.rename(f, os.path.join(subdir, b[len(urlprefix):]))
    # Remove file and URL prefixes from text in all HTML files
    for f in glob.glob(os.path.join(subdir, '*.html')):
        fin = open(f)
        fout = open(f + '.new', 'w')
        for line in fin:
            fout.write(line.replace(prefix, '').replace(urlprefix, ''))
        fin.close()
        fout.close()
        os.rename(f + '.new', f)

def action(target, source, env):
    if coverage:
        topdir = 'python'
        mods = glob.glob("%s/saliweb/*.py" % topdir) \
               + glob.glob("%s/saliweb/build/*.py" % topdir) \
               + glob.glob("%s/saliweb/backend/*.py" % topdir)

        cov = coverage.coverage(branch=True)
        cov.combine()
        if hasattr(coverage.files, 'RELATIVE_DIR'):
            coverage.files.RELATIVE_DIR = topdir + '/'
        else:
            cov.file_locator.relative_dir = topdir + '/'
        cov.html_report(mods, directory='html_coverage/python')
    else:
        print "Could not find new enough coverage module"
        return 1
    env.Execute("cover -outputdir html_coverage/perl "
                "test/frontend/cover_db")
    fixup_perl_html_coverage('html_coverage/perl')
