import saliweb.backend
import glob

class Database(saliweb.backend.Database):
    def __init__(self, jobcls):
        saliweb.backend.Database.__init__(self, jobcls)
        self.add_field(saliweb.backend.MySQLField('number_of_pdbs', 'INTEGER'))


class Job(saliweb.backend.Job):
    runnercls = saliweb.backend.WyntonSGERunner

    def preprocess(self):
        pdbs = glob.glob("*.pdb")
        self._metadata['number_of_pdbs'] = len(pdbs)

    def run(self):
        script = """
for f in *.pdb; do
  grep '^HETATM' $f > $f.het
done
"""
        r = self.runnercls(script)
        r.set_sge_options('-l diva1=1G')
        return r
