class SMTPRecipientsRefused(Exception):
    pass


class SMTP(object):
    def __init__(self, mail_server, mail_port):
        pass

    def sendmail(self, mail_from, mail_to, msg):
        if 'badrecip' in mail_to:
            raise SMTPRecipientsRefused("bad recipient")

    def quit(self):
        pass
