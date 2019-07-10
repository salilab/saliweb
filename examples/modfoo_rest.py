#!/usr/bin/python

from saliweb import web_service

results = web_service.run_job('https://modbase.compbio.ucsf.edu/modfoo/job',
                              ['input_pdb=@input.pdb', 'job_name=testjob'])
