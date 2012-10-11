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

    def run_web_service(self, args):
        # Find path to web_service.py (can't use python -m with older Python)
        mp = __import__('saliweb.web_service', {}, {}, ['']).__file__
        if mp.endswith('.pyc'):
            mp = mp[:-1]
        p = subprocess.Popen([sys.executable, mp] + args,
                             stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        out, err = p.communicate()
        return out, err, p.wait()

    def test_run(self):
        """Check running web_service.py from the command line"""
        out, err, exit = self.run_web_service([])
        self.assertEqual(exit, 0)
        self.assertTrue("Use 'web_service.py help' for help" in out, msg=out)

    def test_help(self):
        """Check running web_service.py help"""
        out, err, exit = self.run_web_service(['help'])
        self.assertEqual(exit, 0)
        self.assertTrue("for detailed help on any command" in out, msg=out)

if __name__ == '__main__':
    unittest.main()
