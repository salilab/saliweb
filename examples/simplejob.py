import saliweb.backend
import glob
import gzip
import os

class Job(saliweb.backend.Job):
    runnercls = saliweb.backend.WyntonSGERunner

    def run(self):
        script = """
for f in *.pdb; do
  grep '^HETATM' $f > $f.het
done
"""
        r = self.runnercls(script)
        r.set_options('-l diva1=1G')
        return r

    def archive(self):
        for f in glob.glob('*.pdb'):
            with open(f, 'rb') as fin, gzip.open(f + '.gz', 'wb') as fout:
                fout.writelines(fin)
            os.unlink(f)
