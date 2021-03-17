import saliweb.backend
import logging

class Job(saliweb.backend.Job):
    runnercls = saliweb.backend.WyntonSGERunner

    def run(self):
        # Uncomment to get all logging output
        # self.logger.setLevel(logging.DEBUG)
        self.logger.info('Starting run method')
        script = """
for f in *.pdb; do
  grep '^HETATM' $f > $f.het
done
"""
        r = self.runnercls(script)
        self.logger.warning('Setting SGE options to diva1=1G')
        r.set_options('-l diva1=1G')
        self.logger.info('Ending run method')
        return r
