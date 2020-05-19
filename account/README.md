This is a simple [Flask](https://palletsprojects.com/p/flask/) application
to manage user accounts for web services hosted at
https://modbase.compbio.ucsf.edu/

## Configuration

1. Create a file `Makefile.include` in the same directory as `Makefile` that
   sets the `WEBTOP` variable to a directory readable by Apache.

2. Create a configuration file `<WEBTOP>/instance/account.cfg`. This should
   be readable only by Apache (since it contains passwords) and contain
   a number of key=value pairs:
   - `SECRET_KEY`: a long random password, used by Flask to encrypt
     session cookies.
   - `MAIL_SERVER`, `MAIL_PORT`, `MAIL_FROM`: host and port to
     connect to to send emails, and the From: address for these emails.
     This is used for sending password resets, and letting the admins know
     when an internal error occurs.
   - `MAIL_TO` a Python list of email addresses to send traceback information to
     when an internal error occurs.
   - `DATABASE_USER`, `DATABASE_PASSWD`, `DATABASE_SOCKET`: parameters to
     connect to the MySQL server.

3. Add a suitable `WSGIScriptAlias` rule to the Apache configuration pointing
   `/account` to `<WEBTOP>/account.wsgi`.

## Deployment

Use `make test` to test changes to the application, and `make install` to
deploy it (this will install the files to the `WEBTOP` directory).
