import saliweb.backend
import glob
import gzip
import os

class Job(saliweb.backend.Job):
    runnercls = saliweb.backend.SGERunner

    def run(self):
        script = """
for f in *.pdb; do
  grep '^HETATM' $f > $f.het
done
"""
        r = self.runnercls(script)
        r.set_sge_options('-l diva1=1G')
        return r

    def archive(self):
        for f in glob.glob('*.pdb'):
            fin = open(f, 'rb')
            fout = gzip.open(f + '.gz', 'wb')
            fout.writelines(fin)
            fin.close()
            fout.close()
            os.unlink(f)
