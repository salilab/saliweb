import saliweb.backend
import sys


def check_not_running(web):
    try:
        pid = web.get_running_pid()
        if pid is not None:
            raise ValueError("The backend is running (pid %d). "
                             "Please stop it first." % pid)
    except saliweb.backend.StateFileError:
        return


def main(webservice):
    web = webservice.get_web_service(webservice.config)
    check_not_running(web)
    print("""This will delete ALL jobs from the web service, including
completed jobs. (Typically this is used to 'restore to factory settings'.)

The database table will be deleted.

All files in job directories will be deleted (even files that do not correspond
to jobs in the database).

This action CANNOT be undone.

Are you SURE you want to delete ALL jobs?
""")
    sys.stdout.write("Enter exactly YES to proceed: ")
    reply = sys.stdin.readline().rstrip('\r\n')
    if reply == 'YES':
        web._delete_all_jobs()
    else:
        print("Canceled.")
