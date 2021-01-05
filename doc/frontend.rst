.. currentmodule:: saliweb.frontend

.. _frontend:

Frontend
********

The frontend is provided by Python code using the
`Flask microframework <http://flask.pocoo.org/>`_. This displays the web
interface, allowing a user to upload their input files, start a job, display
a list of all jobs in the system, and get back job results. This Python code
uses utility classes and functions in the :mod:`saliweb.frontend` module,
together with functionality provided by Flask.

Initialization
==============

The first step is to create a Python module that creates the web application
itself, using the :func:`saliweb.frontend.make_application` function (which
in turn creates a Flask application and configures it).
For a web service 'ModFoo' this should be done in the Python module
``frontend/modfoo/__init__.py``. This is fairly standard boilerplate:

.. literalinclude:: ../examples/frontend-new.py
   :language: python

The 'parameters' object here is a list of parameters the job requires at
submission time, and will be :ref:`described later <parameters>`.

Web page layout
===============

Each web page has a similar layout (header, footer, links, and so on).
This is provided by a system-wide `Jinja2 template <http://jinja.pocoo.org/>`_
called ``saliweb/layout.html``, which can be seen
`at GitHub <https://github.com/salilab/saliweb/blob/main/python/saliweb/frontend/templates/saliweb/layout.html>`_.
This system-wide template should be overriden for each web service, by
providing a file ``frontend/modfoo/templates/layout.html`` that 'extends'
the template:

.. literalinclude:: ../examples/layout.html
   :language: html+jinja

This example demonstrates a few Jinja2 and Flask features:

 - Parts of the base template can be overriden using the ``block`` directive.
   Here, a custom stylesheet is added (by overriding the ``css`` block),
   links are added to all pages to the navigation bar at the top of the
   page (``navigation`` block), and the sidebar and footer (at the left
   and bottom of the page, which are blank in the system-wide template)
   are filled in.
 - Links to other parts of the web service can be provided using Flask's
   `url_for <http://flask.pocoo.org/docs/1.0/api/#flask.url_for>`_ function.
   This takes either the name of the Python function that renders the page
   (such as "index"; :ref:`see below <std_pages>`) or "static" to point
   to static files (such as stylesheets or
   images) in the web service's ``html`` subdirectory.
 - A number of global variables are available which can be substituted in
   using Jinja2's ``{{ }}`` syntax, most notably ``config`` which stores
   web service configuration, such as the name and version in
   ``config.SERVICE_NAME`` and ``config.VERSION`` respectively.
 - Some helper functions are available. Here the ``get_navigation_links``
   function is used, which takes a list of (URL, description) pairs.

See the `Jinja2 manual <http://jinja.pocoo.org/docs/2.10/templates/>`_
for more information on Jinja2 templates.

.. _std_pages:

Displaying standard pages
=========================

The bulk of the functionality of the frontend is implemented by providing
Python functions for each page using
`Flask routes <http://flask.pocoo.org/docs/1.0/quickstart/#routing>`_.

For a typical web service, the index, submission, results and results file
pages need to be implemented by providing ``index``, ``job``, ``results``,
and ``results_file`` functions, respectively.
These pages will be considered in turn.

.. note:: Additional pages (such as page to download the software, or a
          help page) can be simply implemented by adding more Python
          functions with appropriate routes (and, if appropriate, adding
          links to these pages to ``layout.html``).
          :ref:`See below <add_pages>`.

Index page
----------

The index page is the first page seen when using the web service, and typically
displays a form allowing the user to set parameters and upload input files.
(In more complex web services this first form can lead to further forms for
advanced options, etc.) The Python code for this is straightforward - it
simply defines an ``index`` function which uses the Flask
`render_template <http://flask.pocoo.org/docs/1.0/api/#flask.render_template>`_
function to render a Jinja2 template, and is then
`decorated using app.route <https://flask.palletsprojects.com/en/1.0.x/api/#flask.Flask.route>`_
to tell Flask to use this function to service the '/' URL:

.. literalinclude:: ../examples/frontend-index.py
   :language: python

The Jinja2 template in turn looks like:

.. literalinclude:: ../examples/index.html
   :language: html+jinja

The template extends the previously-defined ``layout.html`` so will get
the sidebar, footer, etc. defined there.

The form is set up to submit to the submission page
(``url_for("job")``). It allows the user to upload a single PDB file, as
well as pick an optional name for their job and an optional email address
to be notified when the job completes.

Note that the email address is filled in using
``g.user.email``. (``g`` is used by Flask to store
`global data <http://flask.pocoo.org/docs/1.0/api/#flask.g>`_.)
If the user is logged in to the webserver, ``g.user`` will
be a :class:`LoggedInUser` object, and
their email address will be available for use in this fashion (otherwise, the
user will simply have to input a suitable address if they want to be
notified). Similarly, ``g.user.modeller_key`` provides the MODELLER license
key of the logged-in user.

.. _parameters:

The names of the form parameters above (``job_name``, ``input_pdb``)
should also be described in the Python code ``frontend/modloop/__init__.py``
for automated use of the service (see :ref:`automated`), by passing suitable
:class:`Parameter` and/or :class:`FileParameter` objects
when the application is created. Note that ``email`` is omitted because
automated usage typically does not use email notification:

.. literalinclude:: ../examples/frontend-new-params.py
   :language: python

Submission page
---------------

The submission page is called when the user has input all the information
needed for the job. It is implemented by defining the ``job`` function which
handles the ``/job`` URL. This serves double duty - an HTTP POST to this URL
will submit a new job, while a GET will show all jobs in the system (the
queue).

Showing the queue is handled by the :func:`saliweb.frontend.render_queue_page`
function. Job submission should validate the provided information, then
actually submit the job to the backend. If validation fails, it should throw
an :exc:`InputValidationError` exception; this will be handled by the web
framework as a message to the user asking them to fix the problem and resubmit.
(If some kind of internal error occurs, such as a file write failure, in this
or any other method, the user will see an error page and the server admin
will be notified by email to fix the problem.)

To submit the job, first create a :class:`saliweb.frontend.IncomingJob`
object, which also creates a new directory for the job files. Put all
necessary input files in that directory, for example using
:meth:`IncomingJob.get_path`, then actually run the job by calling
:meth:`IncomingJob.submit`.

.. note::

   'Input files' include PDB files, parameter files, etc. but *not*
   shell scripts, Python scripts, or executables. These should never
   be generated by the frontend, but instead should be generated by
   the backend. If these files are generated by the frontend, it is
   very easy for an unscrupulous end user to hack into the cluster by
   compromising the web service. The backend should always check inputs
   provided by the frontend (e.g. in the
   :meth:`~saliweb.backend.Job.preprocess` method) for sanity before
   running anything.

.. note::

   When taking files as input, you can simply write them into the job directory
   using their `save method <https://werkzeug.palletsprojects.com/en/0.15.x/datastructures/#werkzeug.datastructures.FileStorage.save>`_.
   But never trust the filename provided by the user! Ideally, save with a
   fixed generic name (e.g. ``input.pdb``). If this is not possible, use the
   `secure_filename <https://werkzeug.palletsprojects.com/en/0.15.x/utils/#werkzeug.utils.secure_filename>`_
   function to get a safe version of the filename.

Finally, the submission page should inform the user of the results URL
(:attr:`IncomingJob.results_url`), so that they can obtain the results
when the job finishes. This uses the function
:func:`saliweb.frontend.render_submit_template`, which will either
display an HTML page (similarly to Flask's
`render_template <http://flask.pocoo.org/docs/1.0/api/#flask.render_template>`_,
as before) or XML in the case of automated usage.

The example below reads in the PDB file provided by the user on the index page,
checks to make sure it contains at least one ATOM record, then writes it into
the job directory and finally submits the job:

.. literalinclude:: ../examples/frontend-submit.py
   :language: python

It uses the following template as ``submit.html``, providing the ``job``
and ``email`` variables, to notify the user:

.. literalinclude:: ../examples/submit.html
   :language: html+jinja

Results page
------------

The results page is used to display the results of a job, and is implemented
by providing a ``results`` function.
The function can either display the job results directly, or it can
display links to allow output files to be downloaded. In the latter case,
URLs to these files can be generated by calling
:meth:`CompletedJob.get_results_file_url`.

The example below assumes the backend generates a single output file on
success, ``output.pdb``, and a log file, ``log``, on failure.
It uses the utility function :func:`saliweb.frontend.get_completed_job` to get a
:class:`CompletedJob` object from the URL (this will show an error message
if the job has not completed, or the password is invalid) and then looks for
files in the job directory using the :meth:`CompletedJob.get_path` method:

.. literalinclude:: ../examples/frontend-results.py
   :language: python

This also uses the function
:func:`saliweb.frontend.render_results_template`, which as before will either
display an HTML page (similarly to Flask's
`render_template <http://flask.pocoo.org/docs/1.0/api/#flask.render_template>`_),
or XML in the case of automated usage.

On successful job completion, it shows the ``results_ok.html`` Jinja template,
which uses the :meth:`CompletedJob.get_results_file_url` method to show a
link to download ``output.pdb`` and the
:meth:`CompletedJob.get_results_available_time` method
to tell the user how long the results page will be available for:

.. literalinclude:: ../examples/results_ok.html
   :language: html+jinja

On failure it shows a similar page that links to the log file:

.. literalinclude:: ../examples/results_failed.html
   :language: html+jinja

Results files
-------------

If individual results files can be downloaded, a ``results_file`` function
should be provided. Similar to the results page, this looks up the job
information using the URL, then sends it to the user using Flask's
`send_from_directory <http://flask.pocoo.org/docs/1.0/api/#flask.send_from_directory>`_
function. The user is prevented from downloading other files that may be
present in the job directory, getting an HTTP 404 (file not found) error
instead, using the Flask `abort <http://flask.pocoo.org/docs/1.0/api/#flask.abort>`_ function:

.. literalinclude:: ../examples/frontend-results-file.py
   :language: python

.. note::

   The "results files" don't have to actually exist as real files in the
   job directory. Files can also be constructed on the fly and their contents
   returned to the user in a custom Flask
   `Response <http://flask.pocoo.org/docs/1.0/api/#flask.make_response>`_ object.

Alternative submit/results page for short jobs
----------------------------------------------

For short jobs, it may not be desirable for job submission to pop up a page
containing a 'results' link that the user then needs to click on (as the job
may be complete by that point). In this case, the job submission page can
redirect straight to the job results page using
:func:`saliweb.frontend.redirect_to_results_page`. To avoid the user seeing
an uninformative 'job is still running' page, this page should be
overridden using the ``still_running_template`` argument to
:func:`saliweb.frontend.get_completed_job`. (Normally this would display
something very similar to the submit page, but can auto-refresh if desired
using :meth:`saliweb.frontend.StillRunningJob.get_refresh_time`.) The resulting
logic would look similar to:

.. literalinclude:: ../examples/frontend-submit-redirect.py
   :language: python

It uses the following template as ``running.html``, providing the ``job``
variable (which is a :class:`saliweb.frontend.StillRunningJob` object),
to notify the user and auto-refresh:

.. literalinclude:: ../examples/running.html
   :language: html+jinja

See LigScore at https://github.com/salilab/ligscore/ for a web service that
uses this submit/results logic.

.. _add_pages:

Additional pages
----------------

Additional pages can be added if desired, simply by adding more Python
functions with appropriate URLs (and adding the names of the functions to
the ``get_navigation_links`` function in the ``layout.html`` Jinja template).
Typically these just use ``render_template`` to show some content:

.. literalinclude:: ../examples/frontend-additional.py
   :language: python

Controlling page access
=======================

By default, all pages can be viewed by both anonymous and logged-in users.
This can be modified, for example to restrict access only to named users, by
checking the value of ``flask.g.user`` in any function, which
is either a :class:`LoggedInUser` object or ``None``.

If access should be denied, simply call 
`flask.abort <http://flask.pocoo.org/docs/1.0/api/#flask.abort>`_
with a suitable HTTP error code, e.g. 401 (for "unauthorized").
