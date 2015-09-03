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

* SGE. The framework expects to be run on a machine that is a submit host to a Sun GridEngine compute cluster
  (or a compatible product, such as `OGE <http://www.oracle.com/us/products/tools/oracle-grid-engine-075549.html>`_
  or `OGS <http://gridscheduler.sourceforge.net/>`_). The framework talks to SGE via DRMAA, so you will also need
  the `DRMAA Python bindings <https://github.com/pygridtools/drmaa-python>`_. The framework contains classes to
  talk to the two SGE installations available in the Sali lab - :class:`SGERunner` and :class:`SaliSGERunner`
  in :file:`saliweb/python/saliweb/backend/__init__.py`. To work in your environment, add a new subclass to that file
  (see the implementation of :class:`SaliSGERunner` for an example) setting the `SGE_CELL` and `SGE_ROOT` environment
  variables appropriately, setting `DRMAA_LIBRARY_PATH` to the location of your :file:`libdrmaa.so` file, setting
  `_runner_name` to a unique value, and setting `_qstat` to the full path to your :file:`qstat` binary.

* `MODELLER <http://salilab.org/modeller/>`_. The framework needs your academic MODELLER license key (in order for
  the `check_modeller_key() function <http://salilab.org/saliweb/modules/frontend.html#saliweb::frontend.check_modeller_key>`_
  to work). It obtains this by parsing the :file:`config.py` file in your MODELLER installation. The framework is hardcoded
  to use the path of the Sali lab's own installation; to use outside of the Sali lab you will need to edit
  :file:`perl/saliweb/SConscript` and change the path to :file:`config.py`.

* Web server (e.g. Apache)

* Filesystems (local, NFS)

* MySQL database
