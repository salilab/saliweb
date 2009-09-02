.. _backend:

Backend
*******

The backend is a set of Python classes that manages jobs after the
initial submission. This typically runs from a cronjob on our 'modbase'
machine, picking up submitted jobs from the frontend, submitting jobs
to the cluster and gathering results, and doing any necessary pre- or
post-processing.

The backend is implemented by the :mod:`saliweb.backend` Python module.
