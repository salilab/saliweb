.. highlight:: rest

The :mod:`saliweb::frontend` Perl module
========================================

.. module:: saliweb::frontend
   :synopsis: Functionality required by the web frontend.

This modules provides Perl functions and classes useful for implementing
the web frontend.

.. class:: saliweb::frontend(config_file, server_name)

   The main class used by the frontend. Typically a web service will subclass
   this class and override one or more methods to actually implement the
   web interface. The class creates a Perl CGI object which can be used to
   actually output web pages, and provides methods that behave similarly to
   the corresponding methods in CGI.pm, such as :meth:`start_html`.

   .. attribute:: htmlroot

      The top-level URL under which all static web files (HTML, style sheets,
      images) are found.

   .. attribute:: cgiroot

      The top-level URL under which all CGI scripts are found.

   .. attribute:: email

      If a user is authenticated against the service, this is their email
      address; otherwise, it is undef.

   .. method:: get_navigation_links()

      Return a reference to a list of navigation links, used by
      :meth:`header`. This should be overridden for each service to add
      links to pages to submit jobs, show help, list jobs in the queue, etc.

   .. method:: get_project_menu()

      Return an HTML fragment which will be displayed in a project menu,
      used by :meth:`header`. This can contain general information about
      the service, links, etc., and should be overridden for each service.

   .. method:: display_index_page()
               display_submit_page()
               display_queue_page()
               display_help_page()
               display_results_page()

      Convenience methods designed to be called from CGI scripts. Each displays
      a complete web page by calling :meth:`start_html`, :meth:`header`,
      :meth:`footer`, and :meth:`end_html`. The actual page content is obtained
      from a similarly named get_*_page() method; for example,
      :meth:`display_index_page` calls :meth:`get_index_page`.

   .. method:: get_index_page()

      Return the HTML content of the index page. This is empty by default, and
      must be overridden for each web service. Typically this will display a
      form for user input (multi-page input can be supported if intermediate
      values are passed between pages).

   .. method:: get_submit_page()

      Return the HTML content of the submit page (that shown when a job is
      submitted to the backend). This is empty by default, and
      must be overridden for each web service. Typically this method will
      perform checks on the input data (calling :meth:`failure` to report any
      problems), call :meth:`make_job` and :meth:`submit_job` to actually
      submit the job to the cluster, then point the user to the URL where
      job results can be obtained.
      
   .. method:: get_results_page()

      Return the HTML content of the results page (that shown when the user
      tries to view job results). This is empty by default, and
      must be overridden for each web service. Typically this method will
      display any job failures (e.g. log files), display the job results
      directly, or provide a set of links to allow result files to be
      downloaded. In the last case, these URLs are simply the main results
      URL with an additional 'file' parameter that gives the file name;
      see :meth:`allow_file_download` and :meth:`get_file_mime_type`.

   .. method:: get_queue_page()

      Return the HTML content of the queue page. By default this simply shows
      all jobs in the queue in date order, plus some basic help text.

   .. method:: get_help_page()

      Return the HTML content of help, contact or news pages. By default this
      simply displays a suitable text file installed as part of the web
      service in the ``txt`` directory, named ``help.txt``, ``contact.txt`` or
      ``news.txt`` respectively.

   .. method:: allow_file_download(file)

      When downloading a results file (see :meth:`get_results_page`) this
      method is called to check whether the file is allowed to be downloaded,
      and should return true if it is. (For example, the job results directory
      may contain intermediate output files that should not be downloaded for
      efficiency or security reasons.) By default, this method always returns
      true.

   .. method:: get_file_mime_type(file)

      When downloading a results file (see :meth:`get_results_page`) this
      method to get the correct MIME type for the file. By default, it always
      returns 'text/plain'.

   .. method:: make_job(jobname)

      This takes a user-provided job name, sanitizes it to make sure that is
      compatible with our databases and does not conflict with an existing
      job name, creates a directory for the job's input files, and finally
      returns the sanitized job name and the directory. This is typically used
      in :meth:`get_submit_page` prior to calling :meth:`submit_job`.

   .. method:: submit_job(jobname)

      This submits a job, previously set up by :meth:`make_job`, to the backend.

   .. method:: help_link(target)

      Given an HTML anchor target, this returns an HTML fragment that creates
      a link to the help pages.

   .. method:: failure(message)

      This formats an error message and returns the HTML fragment. It is
      usually used to report failures with job submission from within
      :meth:`get_submit_page`.

   .. method:: start_html([style])

      Return the content of the head section of the web page, containing
      scripts, style sheets, and the title. If *style* is provided, this is
      the URL for a CSS style sheet; if not provided, a default Sali lab
      style is used.

   .. method:: end_html()

      Return the content of the end of the web page.

   .. method:: header()

      Return the header of each web page, which contains navigation links
      (provided by :meth:`get_navigation_links`), a side menu for the service
      (provided by :meth:`get_project_menu`), and links to other services.

   .. method:: footer()

      Return the footer of each web page. By default, this is empty, but it
      can be subclassed to display references, contact addresses etc.



.. function:: check_required_email(email)

   Check a provided email address. Return undef if an email is provided and
   it is a valid address; otherwise, return an error string.

.. function:: check_optional_email(email)

   Check a provided email address. This is similar to
   :func:`check_required_email`, except that no error is returned if no
   email address was provided.
