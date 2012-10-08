.. currentmodule:: saliweb.backend

Using the web service
*********************

This section covers the use of the web service by an end user. Here the
'ModFoo' example web service is used, which is defined by the
:ref:`configuration file <configfile>` to be deployed at
`http://modbase.compbio.ucsf.edu/modfoo`.

Web interface
=============

End users can simply use the web service by pointing their web browsers to
`http://modbase.compbio.ucsf.edu/modfoo/`. This will display the index page,
from where they can submit jobs or navigate to other pages.

User authentication
===================

The web framework ties in automatically to Ursula's login page for web service
accounts. If a user logs in, his or her email address is automatically
supplied to forms that ask for it; job results pages are linked from the
queue page; and, potentially, data files can be passed between multiple lab
web services. Unauthenticated (anonymous) users can still use lab web services,
however, unless the service is experimental or very expensive in terms of
computer time.

.. _automated:

Automated use
=============

The web framework automatically sets up each web service to allow automation.
This allows a program to submit jobs, check for completion, and finally to
obtain the generated results. This is achieved with a
`REST <http://en.wikipedia.org/wiki/REST>`_-style interface that talks a simple
form of XML. This interface is provided by a 'job' script; for the fictional
ModFoo web service this would be found at
`http://modbase.compbio.ucsf.edu/modfoo/job`. Jobs can be submitted by
sending an HTTP POST request to this URL containing the same form data that
would be sent to the regular submit page. On successful submission, the
returned XML file will contain a URL pointing to the job results.
This URL can be queried by an HTTP GET to see if the job has finished.
If it has, a list of URLs for job results files is returned; if it has not,
an HTTP error is returned and the request can be retried later.
Finally, the job results files can be downloaded using the provided URLs.

There is a simple Python interface to all Sali Lab services that use the
framework, installed on `modbase`, that takes care of XML parsing and error
handling for you. It can be used to submit jobs and collect results either
from the command line or from other Python scripts. For example, to run a job
on the fictional ModFoo service and wait for results, you can run from the
command line on `modbase` something like::

    web_service.py run http://modbase.compbio.ucsf.edu/modfoo/job \
                       input_pdb=@input.pdb job_name=testjob

Use ``web_service.py help`` for full details on using this utility.

Alternatively, you can do the same thing from Python with a script like:

.. literalinclude:: ../examples/modfoo_rest.py
   :language: python

Although `/usr/bin/web_service.py` is only installed on `modbase`, you can
copy it and run it on any machine that has network access and has Python and
curl installed.
