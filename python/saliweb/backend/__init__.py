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
    # Run a set of commands on the QB3 SGE cluster
    def __init__(self, script):
        pass
    def set_sge_options(self, opts):
        pass
    def run(self, rundir):
        # append 'touch rundir/donefile' to script
        # generate script file in run directory using options and script
        # run with qsub
        # return runjob_id (SGE job ID) or exception
        pass
    def check_completed(self, runjob_id):
        # Run qstat
        # Return True if job finished
        pass

class SaliSGERunner(SGERunner):
    # Run commands on the Sali SGE cluster instead of QB3
    pass
