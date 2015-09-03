Installation
************

.. _install_lab:

In the Sali lab
===============

There is no need for most users to install the web framework. It is already
installed for you by our sysadmins on the 'modbase' server machine.

Sysadmins: if you do need to make modifications to the framework itself,
this can be done by cloning the `git repository <https://github.com/salilab/saliweb>`_
to a directory on modbase, making your
changes, writing test cases to exercise those changes, running 'scons test'
to make sure the changes didn't break anything, 'git commit' and 'git push'
to commit the changes, then running 'sudo scons install' to update the
installed version of the framework.

.. _outside_lab:

Outside of the Sali lab
=======================

The framework is designed to work in the Sali lab environment, but can be
used in other environments with some modification.

Prerequisites
-------------

* SGE

* `MODELLER <http://salilab.org/modeller/>`_

* DRMAA Python bindings

* Web server (e.g. Apache)

* Filesystems (local, NFS)

* MySQL database
