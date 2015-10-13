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

   .. attribute:: txtdir

      The absolute path to the directory containing files installed
      with :meth:`~saliweb.build.InstallTXT`.

   .. attribute:: http_status

      The HTTP status code (e.g. 200 OK, 404 Not Found) that will be
      reported when the web page is printed.

   .. attribute:: version

      The version number of this web service (read-only).

   .. attribute:: version_link

      An HTML fragment that shows the version as a link to the github page
      for this web service, if `github` is set in the config file (if not,
      returns the same content as `version`). Read-only.

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

   .. attribute:: dbh

      The database handle.

   .. attribute:: index_url
                  submit_url
                  queue_url
                  help_url
                  faq_url
                  links_url
                  about_url
                  news_url
                  contact_url
                  results_url
                  download_url

      Absolute URLs to each web page (read-only).

   .. method:: get_header_page_title()

      Return the HTML fragment used to display the page title inside a div in
      the page header. By default, this just displays the lab logo and the page
      title, but can be overridden if desired.

   .. method:: get_lab_navigation_links()

      Return a reference to a list of lab resources and services, used by
      :meth:`~saliwebfrontend.get_header`. This can be overridden in
      subclasses to add additional links.

   .. method:: get_navigation_links()

      Return a reference to a list of navigation links, used by
      :meth:`~saliwebfrontend.get_header`. This should be overridden for each
      service to add links to pages to submit jobs, show help, list jobs
      in the queue, etc.

   .. method:: get_project_menu()

      Return an HTML fragment which will be displayed in a project menu,
      used by :meth:`~saliwebfrontend.get_header`. This can contain general
      information about the service, links, etc., and should be overridden
      for each service. Usually, it is displayed on the left side of the web
      page. On very narrow screens (e.g. smart phones in portrait mode) it is
      omitted.

   .. method:: display_index_page()
               display_submit_page()
               display_queue_page()
               display_help_page()
               display_results_page()
               display_download_page()

      Convenience methods designed to be called from CGI scripts. Each displays
      a complete web page by calling :meth:`~saliwebfrontend.start_html`,
      :meth:`~saliwebfrontend.get_header`, :meth:`~saliwebfrontend.get_footer`,
      and :meth:`~saliwebfrontend.end_html`. The actual page content is obtained
      from a similarly named get_*_page() method; for example,
      :meth:`~saliwebfrontend.display_index_page` calls
      :meth:`~saliwebfrontend.get_index_page`.
      Each method also calls :meth:`~saliwebfrontend.check_page_access` to
      check whether access to the page is permitted, and
      :meth:`~saliwebfrontend.get_page_is_responsive` to determine whether
      the page is responsive (resizeable).

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
      downloaded (by calling
      :meth:`~saliweb::frontend.CompletedJob.get_results_file_url`).

   .. method:: get_queue_page()

      Return the HTML content of the queue page. By default this simply shows
      all jobs in the queue in date order, plus some basic help text. (Note that
      there is currently no interface defined to do this any differently. If
      you need to customize the queue page, please talk to Ben so we can design
      a suitable interface.)

   .. method:: get_help_page(type)

      Return the HTML content of help, contact, FAQ, links, about, or news
      pages; the passed *type* parameter will be *help*, *contact*, *faq*,
      *links*, *about*, or *news*. By default
      this simply displays a suitable text file installed as part of the web
      service in the ``txt`` directory, named ``help.txt``, ``contact.txt``,
      ``faq.txt``, ``links.txt``, ``about.txt``, or ``news.txt`` respectively.

   .. method:: get_download_page()

      Return the HTML content of the download page. This is empty by default.

   .. method:: check_page_access(page_type)

      Check whether access to the given *page_type* is allowed. *page_type*
      is one of 'index', 'submit', 'queue', 'results', 'help', 'download'.
      It should simply return if access is allowed, or throw an
      :exc:`~saliweb::frontend.AccessDeniedError` exception if access is not
      permitted. By default, it simply returns, allowing all access, for all
      pages except the submit page, from which certain IPs are blocked.

   .. method:: get_page_is_responsive(page_type)

      Returns true iff the given page is 'responsive', that is it can be
      safely resized to be much larger or smaller than the default size.
      Pages that are *not* responsive will be displayed at the default size,
      which doesn't look great on most mobile devices for example (the user
      will typically have to resize and/or pan the screen, or read very small
      text). A responsive page will be resized to fit the smartphone screen,
      which could also look bad if page elements aren't designed to scale.

      *page_type* is as for :meth:`~saliweb::frontend.check_page_access`. By
      default, the queue and help pages are marked as responsive. It can be
      overridden if other pages (such as the index page) are also resizable.

   .. method:: download_results_file(job, file)

      This method is called to download a single results file (when the user
      follows a URL provided by
      :meth:`~saliweb::frontend.CompletedJob.get_results_file_url`), provided
      that :meth:`~saliwebfrontend.allow_file_download` returns true.
      It is called in the job directory with a
      :class:`~saliweb::frontend.CompletedJob` object and a relative path,
      and is expected to print out the HTTP header and then the contents
      of the file. By default, the method uses the MIME type returned by
      :meth:`~saliwebfrontend.get_file_mime_type` in the header, then prints
      out the file if it physically exists on disk, or if it does not but a
      gzip-compressed version of it does (with .gz extension) it decompresses
      the file and prints that. This method can be overridden, for example
      to download other "files" which don't really exist on the disk.

   .. method:: allow_file_download(file)

      When downloading a results file (see
      :meth:`~saliwebfrontend.download_results_file`) this
      method is called to check whether the file is allowed to be downloaded,
      and should return true if it is. (For example, the job results directory
      may contain intermediate output files that should not be downloaded for
      efficiency or security reasons.) By default, this method always returns
      true.

   .. method:: get_file_mime_type(file)

      When downloading a results file (see
      :meth:`~saliwebfrontend.download_results_file`) this
      method is called to get the correct
      `MIME type <http://en.wikipedia.org/wiki/Internet_media_type>`_
      for the file. By default, it always returns 'text/plain'. You may need
      to override this, for example, if some of your results files are tar
      files ('application/x-tar') or PNG images ('image/png').

   .. method:: get_submit_parameter_help()

      Return a reference to a list of parameters accepted by the submit page.
      This is used to document the REST web service, and should be overridden
      for each service. Each parameter should be the result of calling
      :meth:`~saliwebfrontend.parameter` or
      :meth:`~saliwebfrontend.file_parameter`.

   .. method:: parameter(key, help[, optional])

      Represent a single parameter (with help), used as input to
      :meth:`~saliwebfrontend.get_submit_parameter_help`. 'key' should match
      the name of the parameter used in the HTML form on the index page.

   .. method:: file_parameter(key, help[, optional])

      Represent a single file upload parameter (with help), used as input to
      :meth:`~saliwebfrontend.get_submit_parameter_help`.

   .. method:: make_job(jobname)

      This creates and returns a new :class:`~saliweb::frontend.IncomingJob`
      object that represents a new job, using a user-provided job name.
      The new job has its own directory into which
      input files can be placed, and once this is finished,
      :meth:`~saliweb::frontend.IncomingJob.submit` should be called to
      actually submit the job. This is typically used in
      :meth:`~saliwebfrontend.get_submit_page`.

   .. method:: resume_job(jobname)

      This creates and returns a :class:`~saliweb::frontend.IncomingJob`
      object that represents an incoming job. This job must have been previously
      created using :meth:`make_job`, and jobname must match the true name
      of that job (:attr:`saliweb::frontend.IncomingJob.name`) not the
      original user-provided name. This is used with multiple-page submissions,
      e.g. if the user must upload several files into the job directory
      before the job is submitted. Once done,
      :meth:`~saliweb::frontend.IncomingJob.submit` should be called to
      actually submit the job.

   .. method:: help_link(target)

      Given an HTML anchor target, this returns an HTML fragment that creates
      a link to the help pages.

   .. method:: start_html([style])

      Return the content of the head section of the web page, containing
      scripts, style sheets, and the title. If *style* is provided, this is
      the URL for a CSS style sheet; if not provided, a default Sali lab
      style is used. It usually does not make sense to override this method
      in derived classes (instead, override
      :meth:`~saliwebfrontend.get_start_html_parameters`).

   .. method:: get_start_html_parameters(style)

      Return a hash of arguments suitable for passing to CGI.pm's start_html()
      method. This can be overridden in derived classes, for example to add
      additional scripts or CSS style sheets.

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
      This is only filled in when :meth:`submit` is called. Attempting to
      query this attribute before then will result in an :exc:`InternalError`.

   .. method:: submit([email])

      Submits the job to the backend to run on the cluster. If an email
      address is provided, it is notified when the job completes.


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
      relative to the job directory, not an absolute path. The actual download
      of the file is handled by :meth:`~saliwebfrontend.download_results_file`.


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

.. function:: pdb_code_exists(code)

   Return true iff the PDB code (e.g. 1abc) exists in our local copy of the PDB.

.. function:: get_pdb_code(code, outdir)

   Look up the PDB code (e.g. 1abc) in our local copy of the PDB, and 
   copy it into the given directory (usually an incoming job directory).
   The file will be named in standard PDB fashion, e.g. pdb1abc.ent.
   The full path to the file is returned. If the code is invalid or does
   not exist, throw an :exc:`InputValidationError` exception.

.. function:: get_pdb_chains(code_and_chains, outdir)

   Similar to :func:`get_pdb_code`, find a PDB in our database, and make a
   new PDB containing just the requested one-letter chains (if any) in the given
   directory. The PDB code and the chains are separated by a colon. (If there
   is no colon, no chains, or the chains are just '-', this does the same thing
   as :func:`get_pdb_code`.) For example, '1xyz:AC' would make a new PDB file
   containing just the A and C chains from the 1xyz PDB.
   The full path to the file is returned. If the code is invalid or does
   not exist, or at least one chain is specified that is not in the PDB
   file, throw an :exc:`InputValidationError` exception.
