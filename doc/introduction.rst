Introduction
************

The Sali lab web framework aims to provide a simple set of classes and modules
to simplify the process of deploying a web service. It is designed for typical
Sali lab web applications - that is to say, jobs that are submitted from a
web interface but that then run on one or more cluster nodes for a possibly
long period of time.

The framework is split up into four distinct parts:

* The *frontend* consists of HTML pages and Perl-CGI scripts that interact
  with an end user. It handles the uploading of input files, the initial
  submission of jobs, displaying a queue of all jobs in the system, and
  showing the results of completed jobs. It can also potentially handle
  user logins.

* The *backend* is a set of Python classes that manages jobs after the
  initial submission. This typically runs from a cronjob on our 'modbase'
  machine, picking up submitted jobs from the frontend, submitting jobs
  to the cluster and gathering results, and doing any necessary pre- or
  post-processing.

* The *build system* is a set of extensions to SCons that simplifies the
  procedure of setting up a web service and installing everything in the
  correct locations and with the right permissions.

* *Monitoring* is typically set up by a sysadmin, and ensures that the
  web service, once set up and made available to end users, is correctly
  functioning.

The web framework stores all persistent data about the jobs in a MySQL database.

The framework aims to be:

* *Comprehensive*: can handle simple services like ModLoop and complex
  services like CM-MR.

* *Robust*: full error checking is done at each step of the process;
  job failures are caught and reported to the server admin.

* *Extensible*: a service can be set up without user authentication,
  but this can be simply added in later. The backend Python classes provide
  multiple hooks to allow each step of the job to be modified.

* *Secure*: by default, file permissions should be set up sensibly. There
  should be no need for world-writeable directories or other hacks to allow
  files to be passed from the web server to the cluster. The backend runs as
  a different user from the web server, so it is unlikely that a bug in the
  frontend can be used to break into the cluster.

* *Efficient*: it is straightforward to configure the system so that
  long-term data from jobs are not left on expensive disks such as NetApp,
  but are instead moved to park disks or deleted.

* *Easy to use*: given a simple workflow, it should be easy to deploy a
  simple web server that implements it.
