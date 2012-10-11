import unittest
import tempfile
import shutil
import urllib2
import os
import sys
import time
from saliweb import web_service
from xml.dom.minidom import parseString
import xml.parsers.expat
import subprocess
from cStringIO import StringIO

class MockURLOpen(object):
    ns = 'xmlns:xlink="http://www.w3.org/1999/xlink"'
    def __init__(self, url):
        self.url = url
    def read(self):
        return """
<saliweb %s>
<results_file xlink:href="http://results1/" />
<results_file xlink:href="http://results2/" />
</saliweb>
""" % self.ns

def mock_sleep(interval):
    pass

def mock_urlopen(url):
    if 'notdone' in url:
        raise urllib2.HTTPError('url', 503, 'msg', [], None)
    elif 'badurl' in url:
        raise urllib2.HTTPError('url', 404, 'msg', [], None)
    else:
        return MockURLOpen(url)

class WebServiceTests(unittest.TestCase):
    """Test the web_service script."""

    def setUp(self):
        unittest.TestCase.setUp(self)
        self.tmpdir = tempfile.mkdtemp()
        curl = os.path.join(self.tmpdir, 'curl')
        open(curl, 'w').write("""#!/usr/bin/python
import sys
url = sys.argv[-1]
ns = 'xmlns:xlink="http://www.w3.org/1999/xlink"'
if 'badcurl' in url:
    print >> sys.stderr, "some curl error"
    sys.exit(1)
elif 'invalidxml' in url:
    print "this is not valid xml"
elif 'wrongxml' in url:
    print "<wrongtag />"
elif 'noparam' in url:
    print '<saliweb><service name="modfoo"/></saliweb>'
elif 'badsubmit' in url:
    print '<saliweb><error>invalid job submission</error></saliweb>'
elif 'oksubmit' in url:
    print '<saliweb %s><job xlink:href="http://jobresults/" /></saliweb>' % ns
else:
    print '<saliweb><service name="modfoo"/>' \
          '<parameters><string name="foo">bar</string>' \
          '</parameters></saliweb>'
""")
        os.chmod(curl, 0700)
        os.environ['PATH'] = self.tmpdir + ':' + os.environ['PATH']
        self.orig_urlopen = urllib2.urlopen
        urllib2.urlopen = mock_urlopen
        self.orig_sleep = time.sleep
        time.sleep = mock_sleep

    def tearDown(self):
        unittest.TestCase.tearDown(self)
        shutil.rmtree(self.tmpdir)
        urllib2.urlopen = self.orig_urlopen
        time.sleep = self.orig_sleep

    def test_curl_rest_page(self):
        """Check _curl_rest_page function"""
        self.assertRaises(OSError, web_service._curl_rest_page,
                          'http://badcurl/job', [])
        self.assertRaises(xml.parsers.expat.ExpatError,
                          web_service._curl_rest_page,
                          'http://invalidxml/job', [])
        self.assertRaises(ValueError, web_service._curl_rest_page,
                          'http://wrongxml/job', [])
        top, out = web_service._curl_rest_page('http://ok/job', [])

    def test_parameters(self):
        """Test _Parameter and _FileParameter classes"""
        p = web_service._Parameter('foo', 'bar', '0')
        optp = web_service._Parameter('foo', 'bar', '1')
        f = web_service._FileParameter('foo', 'bar', '1')
        self.assertEqual(p.get_full_arg(), 'foo=ARG')
        self.assertEqual(optp.get_full_arg(), '[foo=ARG]')
        self.assertEqual(f.get_full_arg(), '[foo=@FILENAME]')
        self.assertEqual(p.get_help(), 'foo' + ' '*17 + 'bar')
        self.assertEqual(optp.get_help(), 'foo' + ' '*17 + 'bar [optional]')
        self.assertEqual(f.get_help(), 'foo' + ' '*17 + 'bar [optional]')

    def test_get_parameters_from_xml(self):
        """Test _get_parameters_from_xml()"""
        xml = "<saliweb />"
        pxml = """
<saliweb>
  <parameters>
    <string name="string1">help1</string>
    <string name="string2" optional="1">help2</string>
    <file name="file1">help3</file>
  </parameters>
</saliweb>"""
        xml = parseString(xml).getElementsByTagName('saliweb')[0]
        pxml = parseString(pxml).getElementsByTagName('saliweb')[0]
        ps = web_service._get_parameters_from_xml(xml)
        self.assertEqual(ps, [])
        ps = web_service._get_parameters_from_xml(pxml)
        self.assertEqual(len(ps), 3)
        self.assertEqual([x.name for x in ps], ['string1', 'string2', 'file1'])
        self.assertEqual([x.help for x in ps], ['help1', 'help2', 'help3'])
        self.assertEqual([x.optional for x in ps], [False, True, False])

    def test_show_info(self):
        """Test show_info()"""
        o = web_service.show_info('http://noparam/')
        o = web_service.show_info('http://ok/')

    def test_submit_job(self):
        """Test submit_job()"""
        self.assertRaises(IOError, web_service.submit_job,
                          'http://badsubmit/', [])
        url = web_service.submit_job('http://oksubmit/', ['foo=bar'])
        self.assertEqual(url, "http://jobresults/")

    def test_get_results(self):
        """Test get_results()"""
        self.assertEqual(web_service.get_results('http://notdone/'), None)
        self.assertRaises(urllib2.HTTPError, web_service.get_results,
                          'http://badurl/')
        urls = web_service.get_results('http://jobresults/')
        self.assertEqual(urls, [u'http://results1/', u'http://results2/'])

    def test_run_job(self):
        """Test run_job()"""
        urls = web_service.run_job('http://oksubmit/', ['foo=bar'])
        self.assertEqual(urls, [u'http://results1/', u'http://results2/'])

    def run_web_service_subprocess(self, args):
        """Run web_service.py in a subprocess"""
        # Find path to web_service.py (can't use python -m with older Python)
        mp = __import__('saliweb.web_service', {}, {}, ['']).__file__
        if mp.endswith('.pyc'):
            mp = mp[:-1]
        p = subprocess.Popen([sys.executable, mp] + args,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        out, err = p.communicate()
        return out, err, p.wait()

    def run_web_service(self, args):
        """Run web-service.py in the current process, but as if it were
           run from the command line"""
        orig_stdout = sys.stdout
        orig_stderr = sys.stderr
        orig_argv = sys.argv
        out = StringIO()
        err = StringIO()
        exitval = 0
        try:
            sys.stdout = out
            sys.stderr = err
            sys.argv = ['web_service.py'] + args
            try:
                web_service.main()
            except SystemExit, detail:
                exitval = detail.code
        finally:
            sys.stdout = orig_stdout
            sys.stderr = orig_stderr
            sys.argv = orig_argv
        return out.getvalue(), err.getvalue(), exitval

    def test_run(self):
        """Check running web_service.py from the command line"""
        out, err, exit = self.run_web_service_subprocess([])
        self.assertEqual(exit, 0)
        self.assertTrue("Use 'web_service.py help' for help" in out, msg=out)

    def test_help(self):
        """Check running web_service.py help"""
        for args in [['help'], ['help', 'help']]:
            out, err, exit = self.run_web_service(args)
            self.assertEqual(exit, 0)
            self.assertTrue("for detailed help on any command" in out, msg=out)

        out, err, exit = self.run_web_service(['help', 'info'])
        self.assertEqual(exit, 0)
        self.assertTrue("Get basic information about a web service" in out,
                        msg=out)

        out, err, exit = self.run_web_service(['help', 'badcmd'])
        self.assertEqual(exit, 1)
        self.assertTrue("Unknown command: 'badcmd'" in out, msg=out)

    def test_unknown_command(self):
        """Check running unknown web_service.py command"""
        out, err, exit = self.run_web_service(['badcmd'])
        self.assertEqual(exit, 1)
        self.assertTrue("Unknown command: 'badcmd'" in out, msg=out)

    def test_info_command(self):
        """Check running web_service.py info command"""
        out, err, exit = self.run_web_service(['info'])
        self.assertEqual(exit, 1)
        self.assertTrue("sample usage for submitting jobs" in out, msg=out)
        out, err, exit = self.run_web_service(['info', 'http://noparam/'])
        self.assertEqual(exit, 0)
        self.assertTrue("web_service.py submit http://noparam/ "
                        "[name1=ARG] [name2=@FILENAME] ..." in out, msg=out)
        out, err, exit = self.run_web_service(['info', 'http://ok/'])
        self.assertEqual(exit, 0)
        self.assertTrue("web_service.py submit http://ok/ foo=ARG" in out,
                        msg=out)

    def test_submit_command(self):
        """Check running web_service.py submit command"""
        out, err, exit = self.run_web_service(['submit'])
        self.assertEqual(exit, 1)
        self.assertTrue("This only submits the job" in out, msg=out)
        out, err, exit = self.run_web_service(['submit', 'http://oksubmit/'])
        self.assertEqual(exit, 0)
        self.assertTrue("Job submitted: results will be found at" in out,
                        msg=out)

    def test_results_command(self):
        """Check running web_service.py results command"""
        out, err, exit = self.run_web_service(['results'])
        self.assertEqual(exit, 1)
        self.assertTrue("If the job has finished," in out, msg=out)

        out, err, exit = self.run_web_service(['results', 'http://jobresults/'])
        self.assertEqual(exit, 0)
        self.assertTrue("http://results1/" in out, msg=out)

    def test_run_command(self):
        """Check running web_service.py run command"""
        out, err, exit = self.run_web_service(['run'])
        self.assertEqual(exit, 1)
        self.assertTrue("basically the equivalent" in out, msg=out)

        out, err, exit = self.run_web_service(['run', 'http://oksubmit/'])
        self.assertEqual(exit, 0)
        self.assertTrue("http://results1/" in out, msg=out)

if __name__ == '__main__':
    unittest.main()
