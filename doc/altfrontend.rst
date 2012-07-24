.. currentmodule:: saliweb.build

.. _alt_frontend:

Alternate frontends
*******************

In some cases, it may be desirable to have multiple frontends that all talk
to the same backend. The framework supports any number of such 'alternate'
frontends. Each frontend has a different human-readable service name and a
different URL from the main frontend.

To set up an alternate frontend called 'ModAlt', first add a section similar
to the following to the configuration file (see also :ref:`deploy_config`):

.. literalinclude:: ../examples/alternate.conf

This configuration file section defines the frontend's human-readable name
(ModAlt), the URL where the frontend can be found, and the internal name for
the service, which should be a single lowercase word ('modalt' in this case).

Next, create the frontend Perl module itself, similarly to the main frontend
(see :ref:`frontend_module`). The module name must match the internal name,
with a ``.pm`` extension ('modalt.pm' in this case).

Finally, instruct the build system to install the alternate frontend
(see also :ref:`deploy_build`). For the Perl module, use the regular
:meth:`~Environment.InstallPerl` method just as for the main frontend.
For the other components (CGI scripts and HTML/text support files), use the
:class:`~Environment.Frontend` class. This class takes a single argument,
which is the internal name of the frontend ('modalt' in this
case), and provides methods which are very similar to those in the main
:class:`Environment` class. An example SConstruct file is shown below:

.. literalinclude:: ../examples/SConstruct.alternate
   :language: python

Finally, ask a sysadmin to set up the URL for the new frontend.
