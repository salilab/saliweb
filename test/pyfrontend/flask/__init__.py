# Mock of the Flask module

def url_for(fname, *args):
    return fname + ";" + str(args)


class Markup(object):
    def __init__(self, txt):
        self.txt = txt


class Blueprint(object):
    def __init__(self, name, modname, *args, **kwargs):
        self.name, self.modname, self.args = name, modname, args
        self.kwargs = kwargs


current_app = None
g = {}


class Flask(object):
    def __init__(self, name, *args, **kwargs):
        self.name, self.args, self.kwargs = name, args, kwargs
        self.debug = True
        self.config = {}
        global current_app
        current_app = self

    def errorhandler(self, meth):
        return meth

    def register_blueprint(self, bp):
        pass


def render_template(fname, *args):
    pass
