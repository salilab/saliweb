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
implementing a custom 'new' method. For a web service 'foo' this should be
done in the Perl module foo.pm. This is fairly standard boilerplate:

.. literalinclude:: ../examples/frontend-new.pm
   :language: perl

The 'new' method sets the name of the service ('Foo Service' in this case)
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

Submission page
---------------

Results page
------------
