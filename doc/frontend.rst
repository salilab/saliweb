.. currentmodule:: saliweb::frontend

.. _frontend:

Frontend
********

The frontend is a set of Perl classes that displays the web interface, allowing
a user to upload their input files, start a job, display a list of all jobs
in the system, and get back job results. The main :class:`saliweb::frontend`
class must be subclassed for each web service. This class is then used to
display the web pages using a set of CGI scripts that are set up for you
automatically by the build system.

.. note:: A method in Perl is simply a function that gets a reference to an
          object, $self, as its first argument. To override a method, simply
          define a function with the same name as one in the
          :class:`saliweb::frontend` class, for example :meth:`footer`.

Initialization
==============

The first step is to create a Perl module that initializes the subclass by
implementing a custom 'new' method. For a web service 'ModFoo' this should be
done in the Perl module ``modfoo.pm``. This is fairly standard boilerplate:

.. literalinclude:: ../examples/frontend-new.pm
   :language: perl

The 'new' method sets the name of the service ('ModFoo' in this case)
and the name of the configuration file (@CONFIGFILE@ is filled in automatically
by the build system).

Web page layout
===============

Each web page has a similar layout. Firstly, it contains a standard header
that is shared between all lab services. Secondly, it contains a list of links
to other pages in the web service, such as help pages and a display of jobs in
the queue. This list can be customized by overriding the
:meth:`get_navigation_links` method, which returns a reference to a list of
HTML links.
Thirdly, it contains a 'project menu',
which can be used to display miscellaneous information such as the authors,
or in more complex projects to allow results from one job to be used as input
to a new job. This can be customized by overriding the :meth:`get_project_menu`
method, which returns the HTML for this menu.

Finally, after the actual page content itself a footer is displayed, in which
information such as paper references can be placed. This can be customized by
overriding the :meth:`footer` method, which returns an HTML fragment.

.. literalinclude:: ../examples/frontend-layout.pm
   :language: perl

The :class:`saliweb::frontend` class provides several useful attributes and
methods to simplify the process of displaying web pages. For example, above
the :attr:`cgi` attribute is used to get a standard Perl CGI object which can
format HTML links, paragraphs, etc., access cookies, and process form data.
The class also provides the URLs of other pages in the system, such as
:attr:`queue_url`, which is the page that displays all jobs in the web service.

Displaying standard pages
=========================

The bulk of the functionality of the frontend is implemented by overriding
a single method for each page. For a typical web service, the index,
submission and results pages need to be implemented by overriding the
:meth:`get_index_page`, :meth:`get_submit_page` and :meth:`get_results_page`
methods respectively. These will be considered in turn.

Index page
----------

The index page is the first page seen when using the web service, and typically
displays a form allowing the user to set parameters and upload input files.
(In more complex web services this first form can lead to further forms for
advanced options, etc., but they are all handled by the same 'index page' in
the web service.) The form is set up to submit to the submission page
(found at :attr:`submit_url`), which will then actually run the job.
The example below overrides the :meth:`get_index_page` method to create a
simple form allowing the user to upload a single PDB file, as well as pick an
optional name for their job and an optional email address to be notified when
the job completes:

.. literalinclude:: ../examples/frontend-index.pm
   :language: perl

Submission page
---------------

The submission page is called when the user has input all the information
needed for the job. It is implemented by overriding the :meth:`get_submit_page`
method, which should validate the provided information, then
actually submit the job to the backend. If validation fails, it should throw
an :exc:`InputValidationError` exception; this will be handled by the web
framework as a message to the user asking them to fix the problem and resubmit.
(If some kind of internal error occurs, such as a file write failure, in this
or any other method, an :exc:`InternalError` exception should be raised instead
which notifies the server admin rather than the end user, since it is probably
not the end user's fault.)

To submit the job, call the :meth:`make_job`
method to make a directory, then put all necessary input files in that
directory, then finally run the job by calling :meth:`~IncomingJob.submit`.

Finally, the submission page should inform the user of the results URL, so
that they can obtain the results when the job finishes.

The example below reads in the PDB file provided by the user on the index page,
checks to make sure it contains at least one ATOM record, then writes it into
the job directory and finally submits the job:

.. literalinclude:: ../examples/frontend-submit.pm
   :language: perl

Results page
------------

The results page is used to display the results of a job, and is implemented
by overriding the :meth:`get_results_page` method. Unlike the other
methods, it is passed an additional parameter which is a :class:`CompletedJob`
object, which contains information about the job. It is also run in the job's
directory, so that output files can be read in directly. The method can either
display the job results directly, or it can display links to allow output files
to be downloaded. In the latter case, these links are simply the results page
URL itself (provided by CGI's `self_url` attribute) with an additional `file`
parameter specifying the name of the file. The framework will then automatically
handle downloads of this file. Note that if the backend generates additional
files in the job directory which should not be downloaded, the
:meth:`allow_file_download` method can be overridden to control which files
the end user is allowed to download. Note also that if some files are not text
files, the :meth:`get_file_mime_type` method should also be overridden to
specify the MIME type.

The example below assumes the backend generates a log file ``log`` and a
single output file, ``output.pdb``, and allows the user to download these files
(and only these files). The :meth:`CompletedJob.get_results_available_time`
method is used to tell the user how long the results page will be available
for. If the output file is not produced, the user is informed
that a problem occurred.

.. literalinclude:: ../examples/frontend-results.pm
   :language: perl
