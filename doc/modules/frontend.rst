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

   .. method:: start_html([style])

      Print the head section of the web page, containing scripts, style sheets,
      and the title. If *style* is provided, this is the URL for a CSS style
      sheet; if not provided, a default Sali lab style is used.

   .. method:: end_html()

      Finish printing out a web page.

   .. method:: header()

      Print the header of each web page, which contains navigation links
      (provided by :meth:`get_navigation_links`), a side menu for the service
      (provided by :meth:`get_project_menu`), and links to other services.

   .. method:: get_navigation_links()

      Return a reference to a list of navigation links, used by
      :meth:`header`. This should be overridden for each service to add
      links to pages to submit jobs, show help, list jobs in the queue, etc.

   .. method:: get_project_menu()

      Return an HTML fragment which will be displayed in a project menu,
      used by :meth:`header`. This can contain general information about
      the service, links, etc., and should be overridden for each service.
