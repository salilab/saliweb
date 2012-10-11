import unittest
import tempfile
import shutil
import os
from saliweb import web_service
from xml.dom.minidom import parseString
import xml.parsers.expat

class WebServiceTests(unittest.TestCase):
    """Test the web_service script."""

    def setUp(self):
        unittest.TestCase.setUp(self)
        self.tmpdir = tempfile.mkdtemp()
        curl = os.path.join(self.tmpdir, 'curl')
        open(curl, 'w').write("""#!/usr/bin/python
import sys
url = sys.argv[-1]
if 'badcurl' in url:
    print >> sys.stderr, "some curl error"
    sys.exit(1)
elif 'invalidxml' in url:
    print "this is not valid xml"
elif 'wrongxml' in url:
    print "<wrongtag />"
elif 'noparam' in url:
    print '<saliweb><service name="modfoo"/></saliweb>'
else:
    print '<saliweb><service name="modfoo"/>' \
          '<parameters><string name="foo">bar</string>' \
          '</parameters></saliweb>'
""")
        os.chmod(curl, 0700)
        os.environ['PATH'] = self.tmpdir + ':' + os.environ['PATH']

    def tearDown(self):
        unittest.TestCase.tearDown(self)
        shutil.rmtree(self.tmpdir)

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


if __name__ == '__main__':
    unittest.main()
