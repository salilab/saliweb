# Mock of the Flask module

def url_for(fname, _external=False, *args, **kwargs):
    prefix = 'https://' if _external else ''
    return prefix + fname + ";" + str(args) + str(kwargs)


class Markup(object):
    def __init__(self, txt):
        self.txt = txt
    def __str__(self):
        return self.txt


class Blueprint(object):
    def __init__(self, name, modname, *args, **kwargs):
        self.name, self.modname, self.args = name, modname, args
        self.kwargs = kwargs


current_app = None

class _GlobalObj(object):
    pass
g = _GlobalObj()


class _MockConfig(dict):
    def from_object(self, obj):
        pass


class Flask(object):
    def __init__(self, name, *args, **kwargs):
        self.name, self.args, self.kwargs = name, args, kwargs
        self.debug = True
        self.config = _MockConfig()
        global current_app
        current_app = self
        self.before_request_handlers = []
        self.error_handlers = {}
        self.teardown_app_handlers = []
        self.teardown_request_handlers = []

    def errorhandler(self, code_or_exception):
        def real_decorator(func):
            self.error_handlers[code_or_exception] = func
            return func
        return real_decorator

    def before_request(self, f):
        self.before_request_handlers.append(f)
        return f

    def teardown_appcontext(self, f):
        self.teardown_app_handlers.append(f)
        return f

    def teardown_request(self, f):
        self.teardown_request_handlers.append(f)
        return f

    def register_blueprint(self, bp):
        pass


def render_template(fname, *args, **kwargs):
    return "render %s with %s, %s" % (fname, str(args), str(kwargs))


def redirect(endpoint, code=302):
    return "redirect to %s, code %d" % (endpoint, code)
