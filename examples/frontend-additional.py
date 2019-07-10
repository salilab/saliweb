@app.route('/contact')
def contact():
    return flask.render_template('contact.html')


@app.route('/help')
def help():
    return flask.render_template('help.html')
