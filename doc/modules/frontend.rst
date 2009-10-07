.. highlight:: rest

The :mod:`saliweb::frontend` Perl module
========================================

.. module:: saliweb::frontend
   :synopsis: Functionality required by the web frontend.

This modules provides Perl functions and classes useful for implementing
the web frontend.

.. class:: saliweb::frontend(config_file, server_name)

   The main class used by the frontend.

   .. attribute:: htmlroot

      The top-level URL under which all static web files (HTML, style sheets,
      images) are found.

   .. attribute:: cgiroot

      The top-level URL under which all CGI scripts are found.

   .. method:: start_html([style])

      Print the head section of the web page, containing scripts, style sheets,
      and the title. If *style* is provided, this is the URL for a CSS style
      sheet; if not provided, a default Sali lab style is used.
