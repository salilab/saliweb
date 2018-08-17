.. highlight:: rest

.. _backend_module:

The :mod:`saliweb.backend` Python module
========================================

.. automodule:: saliweb.backend

.. autoclass:: Config
   :members:

   .. attribute:: admin_email

      The email address of the admin.

.. autoclass:: Database
   :members:

.. autoclass:: MySQLField
   :members:

.. autoclass:: Runner
   :members:

.. autoclass:: SGERunner
   :members:

.. autoclass:: SaliSGERunner
   :members:

.. autoclass:: WyntonSGERunner
   :members:

.. autoclass:: LocalRunner
   :members:

.. autoclass:: SaliWebServiceRunner
   :members:

.. autoclass:: SaliWebServiceResult
   :members:

.. autoclass:: DoNothingRunner
   :members:

.. autoclass:: WebService
   :members:

.. autoclass:: Job
   :members:

   .. attribute:: logger

      A standard Python logger object (i.e it provides methods such as `debug`,
      `info`, `warning`) that can be used by job methods such as :meth:`run`
      (but not :meth:`expire`). By default this logger logs to a file called
      'framework.log' in the job directory; the file is created when the first
      log message is emitted. See also :meth:`get_log_handler`.

Exceptions
----------

.. autoexception:: ConfigError

.. autoexception:: InvalidStateError

.. autoexception:: RunnerError

.. autoexception:: SanityError

.. autoexception:: StateFileError
