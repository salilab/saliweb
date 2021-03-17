import re
import os
import saliweb.backend.events
from saliweb.backend.events import _JobThread


class _DRMAAJobWaiter(_JobThread):
    """Wait for a job started by a DRMAA Runner to finish"""
    def __init__(self, webservice, jobids, runner, runid):
        _JobThread.__init__(self, webservice)
        self._jobids = jobids
        self._runner = runner
        self._runid = runid

    def run(self):
        from saliweb.backend import RunnerError
        self._runner._waited_jobs.add(self._runid)
        try:
            drmaa, s = self._runner._get_drmaa()
            failed_jobids = []
            s.synchronize(self._jobids, drmaa.Session.TIMEOUT_WAIT_FOREVER,
                          False)
            for j in self._jobids:
                if not s.wait(j, drmaa.Session.TIMEOUT_WAIT_FOREVER):
                    failed_jobids.append(j)
            if len(failed_jobids) > 0:
                failure = RunnerError("Cluster jobs failed: %s. Please contact "
                                      "the cluster sysadmin."
                                      % ', '.join(failed_jobids))
            else:
                failure = None
            e = saliweb.backend.events._CompletedJobEvent(self._webservice,
                                                          self._runner,
                                                          self._runid, failure)
            self._webservice._event_queue.put(e)
        finally:
            self._runner._waited_jobs.remove(self._runid)


class _SGETasks(object):
    """Parse SGE-style '-t' option into number of job subtasks"""

    def __init__(self, opts):
        if '-t ' in opts:
            m = re.search(r'-t\s+(\d+)(?:\-(\d+)(?::(\d+))?)?', opts)
            if not m:
                raise ValueError("Invalid -t SGE option: '%s'" % opts)
            self.first = int(m.group(1))
            if m.group(2):
                self.last = int(m.group(2))
            else:
                self.last = self.first
            if m.group(3):
                self.step = int(m.group(3))
            else:
                self.step = 1
        else:
            self.first = 0

    def __bool__(self):
        return self.first != 0

    def get_run_id(self, jobids):
        """Get a run ID that represents all of the tasks in this job"""
        numjobs = (self.last - self.first + self.step) / self.step
        if len(jobids) != numjobs:
            raise ValueError("Unexpected bulk jobs return: %s; "
                             "was expecting %d jobs" % (str(jobids), numjobs))
        job, task = jobids[0].split('.')
        return job + '.%d-%d:%d' % (self.first, self.last, self.step)


class _DRMAAWrapper(object):
    """Wrapper to start up DRMAA and ensure it is closed down on exit"""

    def __init__(self, env):
        keys = [x for x in os.environ.keys() if x.startswith('SGE_')]
        for x in keys:
            del os.environ[x]
        os.environ.update(env)
        import drmaa
        s = drmaa.Session()
        s.initialize()
        self.module = drmaa
        self.session = s

    def __del__(self):
        if hasattr(self, 'session'):
            self.session.exit()
