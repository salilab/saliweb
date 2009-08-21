import subprocess
import re
import sys

# Version check; we need 2.4 for subprocess, decorators
if sys.version_info[0:2] < [2,4]:
    raise ImportError("This module requires Python 2.4 or later")

class InvalidStateError(Exception):
    """Exception raised for invalid job states"""
    pass

class JobState(object):
    """Simple state machine for jobs"""
    __valid_states = ['INCOMING', 'PREPROCESSING', 'RUNNING',
                      'POSTPROCESSING', 'COMPLETED', 'FAILED',
                      'EXPIRED', 'ARCHIVED']
    __valid_transitions = [['INCOMING', 'PREPROCESSING'],
                           ['PREPROCESSING', 'RUNNING'],
                           ['RUNNING', 'POSTPROCESSING'],
                           ['POSTPROCESSING', 'COMPLETED'],
                           ['COMPLETED', 'ARCHIVED'],
                           ['ARCHIVED', 'EXPIRED'],
                           ['FAILED', 'INCOMING']]
    def __init__(self, state):
        if state in self.__valid_states:
            self.__state = state
        else:
            raise InvalidStateError("%s is not in %s" \
                                    % (state, str(self.__valid_states)))
    def __str__(self):
        return "<JobState %s>" % self.get()
    def get(self):
        """Get current state, as a string."""
        return self.__state
    @staticmethod
    def get_valid_states():
        return JobState.__valid_states[:]
    def transition(self, newstate):
        """Change state to `newstate`. Raises an InvalidStateError if the
           new state is not valid."""
        tran = [self.__state, newstate]
        if newstate == 'FAILED' or tran in self.__valid_transitions:
            self.__state = newstate
        else:
            raise InvalidStateError("Cannot transition from %s to %s" \
                                    % (self.__state, newstate))

class Config(object):
    """This class holds configuration information such as directory
       locations, etc."""
    def __init__(self, fname):
        """Read configuration data from a file."""
        pass

class Database(object):
    """Management of the job database.
       Can be subclassed to add extra columns to the tables for
       service-specific metadata, or to use a different database engine.
       `jobcls` should be a subclass of Job, which will be used to instantiate
       new job objects.
    """
    def __init__(self, jobcls):
        self._jobcls = jobcls

    def create_tables(self):
        """Create all tables in the database to hold job state."""
        pass

    def get_all_jobs_in_state(self, state, name=None, after_time=None):
        # Query relevant MySQL state table
        # - if after_time is given, add 'WHERE after_time < timenow' to query
        # - if name is given, add 'WHERE name = name' to query
        # Convert each row into a Python dict
        # Create new Job object, passing the jobdict
        # yield new object
        pass
    def _update_job(self, jobdict, oldstate=None):
        # if state changed (oldstate not None and oldstate != jobdict.state):
        #     remove from old state table
        #     add to new state table
        # else:
        #     update job in the job state table
        pass


class WebService(object):
    def __init__(self, config, db):
        pass

    def get_job_by_name(self, state, name):
        # call db.get_all_jobs_in_state(state, name), return first hit
        pass

    def do_all_processing(self):
        # call each of the process_* methods below
        pass

    def process_incoming_jobs(self):
        # call db.move_incoming_to_jobs()
        # for each job in db.get_all_jobs_in_state(INCOMING) call job._try_run()
        pass

    def process_completed_jobs(self):
        # for each job in db.get_all_jobs_in_state(RUNNING) call job._try_complete()
        pass

    def process_old_jobs(self):
        # Use a state file to ensure this is run only once per day
        # for each job in db.get_all_jobs_in_state(COMPLETED, 'archive_time') call job._try_archive()
        # for each job in db.get_all_jobs_in_state(ARCHIVED, 'expire_time') call job._try_expire()
        pass


class Job(object):
    # If exceptions occur in any method other than _fail(), call _fail()
    def __init__(self, db, jobdict):
        # Sanity check; make sure jobdict is OK (if not, call _fail)
        pass
    def _try_run(self):
        # set state to PREPROCESSING
        # set jobdict.preprocess_time = time now
        # call self.preprocess()
        # set state to RUNNING
        # set jobdict.run_time = time now
        # call self.run()
        # set runjob_id to return value
        # call db._update_job if runjob_id not None
        pass
    def _try_complete(self):
        # assert that state == RUNNING
        # check for 'done' file in directory, if not present:
        #    if check_completed(runjob_id) is True, call _fail (SGE crash)
        #    otherwise, just return: job isn't done yet
        # set jobdict.postprocess_time = time now
        # set state to POSTPROCESSING
        # call self.postprocess()
        # set jobdict.end_time = time now
        # set jobdict.archive_time = end_time + configured time to archive
        # set jobdict.expire_time = end_time + configured time to expire
        # set state to COMPLETED
        # email user if requested
        pass
    def _try_archive(self):
        # set state to ARCHIVED
        # call self.archive()
        pass
    def _try_expire(self):
        # set state to EXPIRED
        # call self.expire()
        pass
    def set_state(self, state):
        # change job state (transitions enforced by JobState class)
        # move job to different directory if necessary
        # call db._update_job(oldstate)
        pass
    def _get_state(self):
        # get job state (jobdict.state) as string
        pass
    def _fail(self, reason):
        # Users do not call directly - raise exception instead
        # set state to FAILED
        # set jobdict.failure to reason (e.g. a Python exception w/traceback)
        # if an exception occurs here, email the admin (catastrophic error)
        pass

    def run(self):
        # to be implemented by the user
        # e.g. generate script, pass to SGERunner
        pass
    def check_completed(self, runjob_id):
        # do nothing by default
        # can be overridden by the user to call SGERunner.check_completed()
        pass
    def archive(self):
        # do nothing by default
        # can be overridden by user to gzip files, etc.
        pass
    def expire(self):
        # delete job directory
        # can be overridden by user to mail admin, etc.
        pass
    def preprocess(self):
        # can be overridden by user
        pass
    def postprocess(self):
        # can be overridden by user
        pass

class SGERunner(object):
    """Run a set of commands on the QB3 SGE cluster.

       To use, pass a string `script` containing a set of shell commands to run,
       and use `interpreter` to specify the shell (e.g. `/bin/sh`, `/bin/csh`)
       or other interpreter (e.g. `/usr/bin/python`) that will run them.
       These commands will be automatically modified to update a job state
       file at job start and end, if your interpreter is `/bin/sh`, `/bin/csh`,
       `/bin/bash` or `/bin/tcsh`. If you want to use a different interpreter
       you will need to manually add code to your script to update the job
       state file.

       Once done, you can optionally call :meth:`set_sge_options` to set SGE
       options, then call :meth:`run` to submit the job.
    """

    _env = {'SGE_CELL': 'qb3',
            'SGE_ROOT': '/ccpr1/sge6',
            'SGE_QMASTER_PORT': '536',
            'SGE_EXECD_PORT': '537'}
    _arch = 'lx24-amd64'

    def __init__(self, script, interpreter='/bin/sh'):
        self._opts = ''
        self._script = script
        self._interpreter = interpreter

    def set_sge_options(self, opts):
        """Set the SGE options to use, as a string,
           for example '-N foo -l mydisk=1G'
        """
        self._opts = opts

    def run(self, rundir):
        """Generate an SGE script in `rundir` and run it. Return the
           SGE job ID."""
        fh = open(os.path.join(rundir, 'sge-script.sh'), 'w')
        self._write_sge_script(fh)
        fh.close()
        return self._qsub(rundir, 'sge-script.sh')

    def _write_sge_script(self, fh):
        print >> fh, "#!" + self._interpreter
        print >> fh, "#$ -S " + self._interpreter
        print >> fh, "#$ -cwd"
        if self._opts:
            print >> fh, '#$ ' + self._opts
        # Update job state file at job start and end
        if self._interpreter in ('/bin/sh', '/bin/bash'):
            print >> fh, "_SALI_JOB_DIR=`pwd`"
        if self._interpreter in ('/bin/csh', '/bin/tcsh'):
            print >> fh, "setenv _SALI_JOB_DIR `pwd`"
        if self._interpreter in ('/bin/sh', '/bin/bash', '/bin/csh',
                                 '/bin/tcsh'):
            print >> fh, 'echo "STARTED" > ${_SALI_JOB_DIR}/job-state'
        print >> fh, self._script
        if self._interpreter in ('/bin/sh', '/bin/bash', '/bin/csh',
                                 '/bin/tcsh'):
            print >> fh, 'echo "DONE" > ${_SALI_JOB_DIR}/job-state'

    @classmethod
    def _qsub(cls, rundir, script):
        """Submit a job script to the cluster."""
        cmd = '%s/bin/%s/qsub' % (cls._env['SGE_ROOT'], cls._arch)
        p = subprocess.Popen([cmd, script], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, cwd=rundir, env=cls._env)
        out = p.stdout.read()
        err = p.stderr.read()
        ret = p.wait()
        if ret != 0:
            raise OSError("qsub failed with code %d and stderr %s" % (ret, err))
        m = re.match("Your job(\-array)? ([\d]+)(\.\d+\-\d+:\d+)? " + \
                     "\(.*\) has been submitted", out)
        if m:
            return m.group(2)
        else:
            raise OSError("Could not parse qsub output %s" % out)

    @classmethod
    def check_completed(cls, runjob_id):
        """Return True only if SGE reports that the given job has finished."""
        cmd = '%s/bin/%s/qstat' % (cls._env['SGE_ROOT'], cls._arch)
        p = subprocess.Popen([cmd, '-j', runjob_id], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, env=cls._env)
        out = p.stdout.read()
        err = p.stderr.read()
        ret = p.wait()
        if ret != 0:
            raise OSError("qstat failed with code %d and stderr %s" \
                          % (ret, err))
        # todo: raise an exception if job is in Eqw state, dr, etc.
        return out.startswith("Following jobs do not exist:")


class SaliSGERunner(SGERunner):
    """Run commands on the Sali SGE cluster instead of the QB3 cluster."""
    _env = {'SGE_CELL': 'sali',
            'SGE_ROOT': '/home/sge61'}
