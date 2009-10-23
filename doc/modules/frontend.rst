.. highlight:: rest

The :mod:`saliweb::frontend` Perl module
========================================

This module provides Perl functions and classes useful for implementing
the web frontend.

.. class:: saliwebfrontend(config_file, version, server_name)

   The main class used by the frontend. Typically a web service will subclass
   this class and override one or more methods to actually implement the
   web interface. The class creates a Perl CGI object which can be used to
   actually output web pages, and provides methods that behave similarly to
   the corresponding methods in CGI.pm, such as
   :meth:`~saliwebfrontend.start_html`.

   .. attribute:: htmlroot

      The top-level URL under which all static web files (HTML, style sheets,
      images) are found (read-only).

   .. attribute:: cgiroot

      The top-level URL under which all CGI scripts are found (read-only).

   .. attribute:: http_status

      The HTTP status code (e.g. 200 OK, 404 Not Found) that will be
      reported when the web page is printed.

   .. attribute:: version

      The version number of this web service (read-only).

   .. attribute:: user_name

      If a user is authenticated against the service, this is their user
      name; otherwise, it is undef (read-only).

   .. attribute:: email

      If a user is authenticated against the service, this is their email
      address; otherwise, it is undef (read-only).

   .. attribute:: modeller_key

      If a user is authenticated against the service and has already provided
      a MODELLER key, this is it; otherwise, it is undef (read-only).

   .. attribute:: cgi

      A pointer to the CGI.pm object used to display HTML (read-only).

   .. attribute:: index_url
                  submit_url
                  queue_url
                  help_url
                  news_url
                  contact_url
                  results_url

      Absolute URLs to each web page (read-only).

   .. method:: get_navigation_links()

      Return a reference to a list of navigation links, used by
      :meth:`~saliwebfrontend.get_header`. This should be overridden for each
      service to add links to pages to submit jobs, show help, list jobs
      in the queue, etc.

   .. method:: get_project_menu()

      Return an HTML fragment which will be displayed in a project menu,
      used by :meth:`~saliwebfrontend.get_header`. This can contain general
      information about the service, links, etc., and should be overridden
      for each service.

   .. method:: display_index_page()
               display_submit_page()
               display_queue_page()
               display_help_page()
               display_results_page()

      Convenience methods designed to be called from CGI scripts. Each displays
      a complete web page by calling :meth:`~saliwebfrontend.start_html`,
      :meth:`~saliwebfrontend.get_header`, :meth:`~saliwebfrontend.get_footer`,
      and :meth:`~saliwebfrontend.end_html`. The actual page content is obtained
      from a similarly named get_*_page() method; for example,
      :meth:`~saliwebfrontend.display_index_page` calls
      :meth:`~saliwebfrontend.get_index_page`.
      Each method also calls :meth:`~saliwebfrontend.check_page_access` to
      check whether access to the page is permitted.

   .. method:: get_index_page()

      Return the HTML content of the index page. This is empty by default, and
      must be overridden for each web service. Typically this will display a
      form for user input (multi-page input can be supported if intermediate
      values are passed between pages).

   .. method:: get_submit_page()

      Return the HTML content of the submit page (that shown when a job is
      submitted to the backend). This is empty by default, and
      must be overridden for each web service. Typically this method will
      perform checks on the input data (throwing an
      :exc:`~saliweb::frontend.InputValidationError`
      to report any problems), then call :meth:`~saliwebfrontend.make_job`
      and its own :meth:`~saliweb::frontend.IncomingJob.submit` method to
      actually submit the job to the cluster, then point the user to the URL
      where job results can be obtained.
      
   .. method:: get_results_page(job)

      Return the HTML content of the results page (that shown when the user
      tries to view job results). It is passed a
      :class:`~saliweb::frontend.CompletedJob` object
      that contains information such as the name of the job and the time
      at which job results will be removed, and is run in the job's directory.
      This method is empty by default, and
      must be overridden for each web service. Typically this method will
      display any job failures (e.g. log files), display the job results
      directly, or provide a set of links to allow result files to be
      downloaded. In the last case, these URLs are simply the main results
      URL with an additional 'file' parameter that gives the file name;
      see :meth:`~saliwebfrontend.allow_file_download` and
      :meth:`~saliwebfrontend.get_file_mime_type`.

   .. method:: get_queue_page()

      Return the HTML content of the queue page. By default this simply shows
      all jobs in the queue in date order, plus some basic help text. (Note that
      there is currently no interface defined to do this any differently. If
      you need to customize the queue page, please talk to Ben so we can design
      a suitable interface.)

   .. method:: get_help_page(type)

      Return the HTML content of help, contact or news pages; the passed *type*
      parameter will be *help*, *contact*, or *news*. By default this
      simply displays a suitable text file installed as part of the web
      service in the ``txt`` directory, named ``help.txt``, ``contact.txt`` or
      ``news.txt`` respectively.

   .. method:: check_page_access(page_type)

      Check whether access to the given *page_type* is allowed. *page_type*
      is one of 'index', 'submit', 'queue', 'results', 'help'. It should
      simply return if access is allowed, or throw an
      :exc:`~saliweb::frontend.AccessDeniedError` exception if access is not
      permitted. By default, it simply returns, allowing all access.

   .. method:: allow_file_download(file)

      When downloading a results file (see
      :meth:`~saliwebfrontend.get_results_page`) this
      method is called to check whether the file is allowed to be downloaded,
      and should return true if it is. (For example, the job results directory
      may contain intermediate output files that should not be downloaded for
      efficiency or security reasons.) By default, this method always returns
      true.

   .. method:: get_file_mime_type(file)

      When downloading a results file (see
      :meth:`~saliwebfrontend.get_results_page`) this
      method is called to get the correct MIME type for the file. By default,
      it always returns 'text/plain'.

   .. method:: make_job(jobname, email)

      This creates and returns a new :class:`~saliweb::frontend.IncomingJob`
      object that
      represents a new job, using a user-provided job name and email address
      (the latter may be undef). The new job has its own directory into which
      input files can be placed, and once this is finished,
      :meth:`~saliweb::frontend.IncomingJob.submit` should be called to
      actually submit the job. This is typically used in
      :meth:`~saliwebfrontend.get_submit_page`.

   .. method:: help_link(target)

      Given an HTML anchor target, this returns an HTML fragment that creates
      a link to the help pages.

   .. method:: start_html([style])

      Return the content of the head section of the web page, containing
      scripts, style sheets, and the title. If *style* is provided, this is
      the URL for a CSS style sheet; if not provided, a default Sali lab
      style is used.

   .. method:: end_html()

      Return the content of the end of the web page.

   .. method:: get_header()

      Return the header of each web page, which contains navigation links
      (provided by :meth:`~saliwebfrontend.get_navigation_links`), a side
      menu for the service (provided by
      :meth:`~saliwebfrontend.get_project_menu`), and links to other services.

   .. method:: get_footer()

      Return the footer of each web page. By default, this is empty, but it
      can be subclassed to display references, contact addresses etc.

.. module:: saliweb::frontend
   :synopsis: Functionality required by the web frontend.


.. class:: IncomingJob

   This represents a new job that is being submitted to the backend. These
   objects are created by calling :meth:`~saliwebfrontend.make_job`.
   Each new job has a unique name and a directory into which input files can
   be placed. Once all input files are in place, :meth:`submit` should be called   to submit the job to the backend.

   .. attribute:: name

      The name of the job. Note that this is not necessarily the same
      as the name given by the user, since it must be unique, and fit in our
      database schema. (The user-provided name is thus sanitized if necessary
      and a unique suffix added.)

   .. attribute:: directory

      The directory on disk for this job. Input files should be placed in this
      directory prior to calling :meth:`submit`.

   .. attribute:: results_url

      The URL where this job's results will be found when it is complete.

   .. method:: submit()

      Submits the job to the backend to run on the cluster.


.. class:: CompletedJob

   This represents a job that has completed, and for which results are
   available. These objects are created automatically and passed to
   :meth:`saliwebfrontend.get_results_page`, and can be queried to get
   information about the job.

   .. attribute:: name

      The name of the job.

   .. attribute:: directory

      The directory on disk containing job results.

   .. attribute:: results_url

      The URL where this job's results can be found.

   .. attribute:: unix_archive_time

      The Unix time (seconds since the epoch, in UTC) at which job results
      will become unavailable. (Use standard Perl functions such as ``gmtime``
      and ``strftime`` to make this human-readable, or use
      :attr:`to_archive_time` or :meth:`get_results_available_time` instead.)
      If the backend is configured to never archive job results, this will
      return undef.

   .. attribute:: to_archive_time

      A human-readable string giving the time from now at which job results
      will become unavailable (e.g. '6 days', '24 hours'). 
      If the backend is configured to never archive job results, or the
      time has already passed, this will return undef.
      See also :meth:`get_results_available_time`.

   .. method:: get_results_available_time()

      This will return a short paragraph, suitable for
      adding to a human-readable results page, indicating how long the results
      will be available for.
      If the backend is configured to never archive job results, or the time
      has already passed, this will simply return an empty string.

   .. method:: get_results_file_url(file)

      Given a file which is an output file from the job, this will return
      a URL which can be used to download the file. The filename should be
      relative to the job directory, not an absolute path.


.. exception:: AccessDeniedError(message)

   This exception is raised if the end user does not have permission to view
   a page. It is generally raised from within
   :meth:`~saliwebfrontend.check_page_access`.

.. exception:: InputValidationError(message)

   This exception is typically used to report failures with job submission
   (due to invalid user input) from within
   :meth:`~saliwebfrontend.get_submit_page` or functions it calls. These
   errors are handled by reporting them to the user and asking them to
   fix their input accordingly.

.. exception:: InternalError(message)
               DatabaseError(message)

   These exceptions are used to report fatal errors in the frontend, such
   as an inability to create necessary directories or files (e.g. the disk
   filled up), failure to connect to the MySQL database, etc. These errors
   are reported to the server admin so that they can fix the problem.

.. function:: check_required_email(email)

   Check a provided email address. If the address is empty or is invalid,
   throw an :exc:`InputValidationError` exception.

.. function:: check_optional_email(email)

   Check a provided email address. This is similar to
   :func:`check_required_email`, except that only invalid addresses cause
   an error; it is OK to provide an empty address.

.. function:: check_modeller_key(modkey)

   Check a provided MODELLER key. If the key is empty or invalid,
   throw an :exc:`InputValidationError` exception.
