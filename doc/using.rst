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
A simple example Python script to
automatically submit a job, and then gather the results, is shown below.

.. literalinclude:: ../examples/modfoo_rest.py
   :language: python
