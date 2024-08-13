.. highlight:: rest

.. _frontend_module:

The :mod:`saliweb.frontend` Python module
=========================================

.. automodule:: saliweb.frontend

.. autoclass:: CompletedJob
   :members:

.. autoclass:: LoggedInUser
   :members:

.. autoclass:: IncomingJob
   :members:

.. autoclass:: StillRunningJob
   :members:

.. autoclass:: Parameter
   :members:

.. autoclass:: FileParameter
   :members:

.. autofunction:: make_application

.. autofunction:: get_completed_job

.. autofunction:: get_db

.. autofunction:: render_queue_page

.. autofunction:: check_email

.. autofunction:: check_modeller_key

.. autofunction:: check_mmcif

.. autofunction:: check_pdb

.. autofunction:: pdb_code_exists

.. autofunction:: get_pdb_code

.. autofunction:: get_pdb_chains

.. autofunction:: render_results_template

.. autofunction:: render_submit_template

.. autofunction:: redirect_to_results_page

.. autoexception:: InputValidationError

.. autoexception:: AccessDeniedError
