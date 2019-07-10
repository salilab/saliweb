.. highlight:: rest

The :mod:`saliweb::Test` Perl module
====================================

This module provides Perl functions and classes useful for testing
the legacy Perl CGI web frontend.

.. class:: saliwebTest(module_name)

   The main utility class used to test the frontend. *module_name* should be the
   same of the Perl module that implements the frontend.

   .. method:: make_frontend()

      Make and return a new Perl frontend object (of the class given by
      *module_name* when this class was created).
