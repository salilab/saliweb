Installation
************

There is no need for most users to install the web framework. It is already
installed for you by our sysadmins on the 'modbase' server machine.

Sysadmins: if you do need to make modifications to the framework itself,
this can be done by checking out the Subversion repository at
https://svn.salilab.org/saliweb/trunk to a directory on modbase, making your
changes, writing test cases to exercise those changes, running 'scons test'
to make sure the changes didn't break anything, 'svn ci' to commit the changes,
then running 'sudo scons install' to update the installed version of
the framework.
