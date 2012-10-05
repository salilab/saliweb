#!/usr/bin/python

import sys
import os
from xml.dom.minidom import parseString
import xml.parsers.expat
import subprocess

def _curl_rest_page(url, curl_args):
    # Sadly Python currently has no method to POST multipart forms, so we
    # use curl instead
    p = subprocess.Popen(['/usr/bin/curl', '-s', '-L'] + curl_args \
                          + [url], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)
    (out, err) = p.communicate()
    exitval = p.wait()
    if exitval != 0:
        raise OSError("curl failed with exit %d; stderr:\n%s" % (exitval, err))
    try:
        dom = parseString(out)
    except xml.parsers.expat.ExpatError:
        print >> sys.stderr, "Web service did not return valid XML:\n" + out
        raise
    top = dom.getElementsByTagName('saliweb')
    if len(top) == 0:
        raise ValueError("Invalid XML: web service did not return "
                         "XML containing a 'saliweb' tag")
    return top[0], out

class _Parameter(object):
    def __init__(self, name, help, optional):
        self.name = name
        self.help = help
        self.optional = optional == '1'
    def get_full_arg(self):
        a = self._get_arg()
        if self.optional:
            return '[' + a + ']'
        else:
            return a
    def _get_arg(self):
        return '%s=ARG' % self.name
    def get_help(self):
        h = "%-20s" % self.name + self.help
        if self.optional:
            h += ' [optional]'
        return h

class _FileParameter(_Parameter):
    def _get_arg(self):
        return '%s=@FILENAME' % self.name

def _get_parameters_from_xml(xml):
    ps = []
    for param in xml.getElementsByTagName('parameters'):
        for c in param.childNodes:
            if c.nodeName == 'string':
                ps.append(_Parameter(c.getAttribute('name'),
                                     c.childNodes[0].wholeText,
                                     c.getAttribute('optional')))
            elif c.nodeName == 'file':
                ps.append(_FileParameter(c.getAttribute('name'),
                                         c.childNodes[0].wholeText,
                                         c.getAttribute('optional')))
    return ps

def get_progname():
    return os.path.basename(sys.argv[0])

def show_info(url):
    p, out = _curl_rest_page(url, [])
    parameters = _get_parameters_from_xml(p)
    if parameters:
        pstr = " ".join(x.get_full_arg() for x in parameters)
    else:
        pstr = "[name1=ARG] [name2=@FILENAME] ..."
    print "\nTo submit a job to this web service, run:\n"
    print "%s submit %s " % (get_progname(), url) + pstr
    print
    print "Where ARG is a string argument, and FILENAME is the name of a "
    print "file to upload (note the '@' prefix)."
    if parameters:
        for x in parameters:
            print "   " + x.get_help()
    else:
        print """
To determine name1, name2 etc., view the HTML source of the regular web
service page and look at the names of the HTML form elements. Alternatively,
ask the developer of the web service to implement the
get_submit_parameters_help() method!"""

def submit_job(url, args):
    curl_args = []
    for a in args:
        curl_args.append('-F')
        curl_args.append(a)
    p, out = _curl_rest_page(url, curl_args)
    for results in p.getElementsByTagName('job'):
        url = results.getAttribute('xlink:href')
        print "Job submitted: results will be found at " + url
        return url
    raise IOError("Could not submit job: " + out)

class _Command(object):
    pass

class _InfoCommand(_Command):
    shorthelp = "Get basic information about a web service."
    def main(self, args):
        if len(args) == 1:
            show_info(args[0])

class _SubmitCommand(_Command):
    shorthelp = "Submit a job to a web service."
    def main(self, args):
        if len(args) >= 1:
            submit_job(args[0], args[1:])


class WebService(object):
    def __init__(self):
        self.short_help = "Run jobs using Sali lab REST web services."
        self._progname = os.path.basename(sys.argv[0])
        self._all_commands = {'info':_InfoCommand,
                              'submit':_SubmitCommand}

    def main(self):
        if len(sys.argv) <= 1:
            print self.short_help + " Use '%s help' for help." % self._progname
        else:
            command = sys.argv[1]
            if command in self._all_commands:
                self.do_command(command)

    def do_command(self, command):
        c = self._all_commands[command]()
        c.main(sys.argv[2:])


def main():
    ws = WebService()
    ws.main()

if __name__ == '__main__':
    main()
