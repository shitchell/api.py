#!/usr/bin/env python3

# It's servers all the way down
from bottle import route, get, post, run, install, ServerAdapter, static_file, template, TEMPLATE_PATH, redirect, request, response, view
from cheroot.ssl.builtin import BuiltinSSLAdapter
from cheroot import wsgi
import ssl
import pkgutil
import os

# Other imports
import sys
import json
import time
from bottle.ext import sqlite
import urllib.parse
import urllib.request

# Port
PORT = 6997

# Registered emails
EMAIL_TO = [
    "shaun@shitchell.com",
    "shauniedude@gmail.com",
    "shaun@fruitsofpassion.org",
    "sandy@sandyali.com",
    "hello@nfcmasters.com"
]

# Set the package filepath
PKG_FILEPATH = os.path.dirname(os.path.abspath(__file__))

# Static files directory
STATIC_DIRECTORY = PKG_FILEPATH + "/htdocs/static/"

# Template directories
TEMPLATE_DIRECTORIES = [
    PKG_FILEPATH + "/htdocs/templates/"
]

# Enable cors
class EnableCors(object):
    name = 'enable_cors'
    api = 2

    def apply(self, fn, context):
        def _enable_cors(*args, **kwargs):
            response.headers['Access-Control-Allow-Origin'] = '*'
            response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, OPTIONS'
            response.headers['Access-Control-Allow-Headers'] = 'Origin, Accept, Content-Type, X-Requested-With, X-CSRF-Token'

            if request.method != 'OPTIONS':
                return fn(*args, **kwargs)

        return _enable_cors

# Enable ssl
class SSLServer(ServerAdapter):
    def run(self, handler):
        server = wsgi.Server((self.host, self.port), handler)
        chain = "/etc/letsencrypt/live/quizlet.shitchell.com/fullchain.pem"
        cert = "/etc/letsencrypt/live/quizlet.shitchell.com/cert.pem"
        key = "/etc/letsencrypt/live/quizlet.shitchell.com/privkey.pem"
        server.ssl_adapter = BuiltinSSLAdapter(cert, key, chain)

        # By default, the server will allow negotiations with old protocols,
        # so we only allow TLSv1.2
        server.ssl_adapter.context.options |= ssl.OP_NO_TLSv1
        server.ssl_adapter.context.options |= ssl.OP_NO_TLSv1_1

        try:
            server.start()
        finally:
            server.stop()

# Template helper functions
def last_modified(filepath):
    pass

# Package relative static filepaths
def _static_file(filepath):
    response = static_file("htdocs/" + filepath, PKG_FILEPATH)
    response.set_header("Cache-Control", "public, max-age=604800")
    return response

# JSON response
def _json_response(status: str = "success", error: str = None, **kwargs):
    response.content_type = 'application/json'
    # Format kwargs
#    kwargs_str = dict()
#    for kwarg in kwargs:
#        key = str(kwarg)
#        value = str(kwargs[key])
#        kwargs_str[key] = value
    res = {"status": str(status), "payload": kwargs}
    return json.dumps(res, indent=4)

def _json_response_error(error: str, **kwargs):
    return _json_response(status="error", reason=error, **kwargs)

# Simple HTML escape
def _html_escape(text):
    return text.replace("<", "&lt;").replace(" ", "&nbsp;").replace("\n", "<br />")

# Send email
def sendmail(recipient, body, html=None, sender="no-reply@shitchell.com", sender_name="", subject="No Subject"):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    # Create message
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = "%s <%s>" % (sender_name, sender)
    msg["Reply-To"] = sender
    msg["Sender"] = sender
    msg["To"] = recipient

    # Add text and html parts
    if not html:
        html = """<font face="monospace"><pre>%s</pre></font>""" % _html_escape(body)
    part_text = MIMEText(body, "plain")
    part_html = MIMEText(html, "html")
    msg.attach(part_text)
    msg.attach(part_html)
    
    # Connect to local SMTP server
    s = smtplib.SMTP("localhost")
    s.sendmail(sender, {recipient, EMAIL_TO[0]}, msg.as_string())
    s.quit()

# Verify that the database includes the tracker table
TRACKER_VERIFIED = False
def _tracker_verify_table(db):
    global TRACKER_VERIFIED
    
    if not TRACKER_VERIFIED:
        try:
            db.execute('CREATE TABLE tracker (id INTEGER PRIMARY KEY AUTOINCREMENT, timestamp INTEGER, ip TEXT NOT NULL, ref TEXT, useragent TEXT, headers TEXT)')
        except:
            pass
        TRACKER_VERIFIED = True

# Log request headers
def _tracker_log_request(request, db):
    ip = request.headers.get("Remote-Addr")
    ref = request.headers.get("Referer")
    useragent = request.headers.get("User-Agent")

    db.execute('INSERT INTO tracker VALUES (NULL, ?, ?, ?, ?, ?)', (
        int(time.time()),
        ip,
        ref,
        useragent,
        json.dumps(dict(request.headers))
    ))

@route('/')
def do_index():
    return _json_response(message="one comes after two")

@get('/mail')
def do_mail_GET():
    return do_mail()

@post('/mail')
def do_mail():
    to = request.query.get("to") or request.forms.get("to") or EMAIL_TO[0]
    body = request.query.get("msg") or request.forms.get("msg")
    name = request.query.get("name") or request.forms.get("name")
    email = request.query.get("from") or request.forms.get("from")
    subject = request.query.get("subject") or request.forms.get("subject")
    antispam = request.query.get("url") or request.forms.get("url")

    # Discard empty body messages
    if not body:
        return _json_response_error("body is empty")
    
    # Verify recipient
    if (to not in EMAIL_TO):
        try:
            to = EMAIL_TO[int(to)]
        except:
            return _json_response_error("'%s' cannot receive emails through this API" % to)
    if antispam:
        to = EMAIL_TO[0]
    print("sending mail to:", to)
    
    # Format sender
    sender = ""
    if name:
        if email:
            sender += '"%s" ' % name
        else:
            sender += name
    if email:
        if name:
            sender += "<%s>" % email
        else:
            sender += email

    # Format message
    msg_text = """
Sender:  %s
Subject: %s
-----------------------------
%s
-----------------------------

~Technical~
IP:      %s
Referer: %s
""" % (sender, subject, body, request.environ.get("HTTP_REMOTE_ADDR"), request.environ.get("HTTP_REFERER"))

    msg_html = """
%s
<div style="font-size: 1em; font-family: arial, sans;">
<hr />
<b>%s</b>
<hr />
%s
<br />
<br />
</div>
<pre style="font-size: 0.95em;">
IP:  %s
Ref: %s
</pre>
""" % (_html_escape(sender), subject, _html_escape(body), request.environ.get("HTTP_REMOTE_ADDR"), request.environ.get("HTTP_REFERER"))

    # Add domain or api to subject
    source = urllib.parse.urlparse(request.environ.get("HTTP_REFERER")).hostname or "api"
    # Filter out requests with url parameter
    if antispam:
        subject = "[%s] [SPAM] %s" % (source, subject)
        sender="spam@shitchell.com"
    else:
        subject = "[%s] %s" % (source, subject)
        sender="no-reply@shitchell.com"

    try:
        sendmail(to, msg_text, html=msg_html, sender_name="Contact API", subject=subject, sender=sender)
    except Exception as e:
        return _json_response_error(str(e))
    return _json_response(name=name, email=email, subject=subject, msg=body)

@get('/headers')
def do_headers():
    return _json_response(**request.headers)

@route('/pixel.gif')
def do_pixel_gif(db):
    # Make sure the tracker table exists
    _tracker_verify_table(db)

    # Log the user's information
    _tracker_log_request(request, db)

    # Display the gif
    return _static_file("img/pixel.gif")

@route('/pixel')
def do_pixel(db):
    _tracker_verify_table(db)
    # Get the most recent entry
    limit = 5
    try:
        limit = int(request.query.limit)
    except Exception as e:
        pass
    if limit < 0:
        limit = 0
    elif limit > 100:
        limit = 100
    recent = db.execute('SELECT * FROM tracker ORDER BY timestamp DESC LIMIT ?', [str(limit)]).fetchall()
    requests = []
    for req in recent:
        data = {}
        data['id'] = req[0]
        data['timestamp'] = req[1]
        data['ip'] = req[2]
        data['ref'] = req[3]
        data['user_agent'] = req[4]
        data['headers'] = req[5]
        data['headers'] = json.loads(data['headers'])
        requests.append(data)

    # Return the result as json
    return _json_response(recent=requests)

@route('/src')
def do_src():
    response.content_type = 'text/plain'

    html = ""
    url = request.query.get("url") or request.forms.get("url")
    if url:
        try:
            html = urllib.request.urlopen(url).read()
        except:
            pass
    return html            

@route('/pixel-demo')
@view('pixel')
def do_pixel_html():
    return {"title": "test"}

@route('/test')
def do_test():
    return "test"

@route('/static/<path:path>')
def do_static(path):
    return _static_file("static/" + path)

def main():
    global PORT
    
    # Allow CORS
    install(EnableCors())
    
    # Set the port
    if len(sys.argv) > 1:
        try:
            PORT = int(sys.argv[1])
        except:
            pass
    
    # Add the template directory
    for directory in TEMPLATE_DIRECTORIES:
        TEMPLATE_PATH.insert(0, directory)

    # Create the sqlite plugin
    plugin_sqlite = sqlite.Plugin(dbfile='app.db')
    
    # Run the server
    run(host='0.0.0.0', port=PORT, debug=True, server=SSLServer, reloader=True, plugins=[plugin_sqlite])

if __name__ == "__main__":
    while True:
        try:
            main()
        except Exception as e:
            import time
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            print("[%s:%s] %s: %s" % (fname, exc_tb.tb_lineno, exc_type.__name__, e), file=sys.stderr)
            print("Restarting after 5 seconds...", file=sys.stderr)
            time.sleep(5)