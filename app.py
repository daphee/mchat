# -*- coding: utf-8 -*- 
from flask import Flask,render_template,request,url_for, session,redirect,Response,abort
import pymongo,datetime
from werkzeug.wrappers import Request
from passlib.hash import sha256_crypt
import json,urlparse
from flask.sessions import SecureCookieSessionInterface
import json
from ws4py.server.geventserver import WebSocketWSGIApplication, WSGIServer
from ws4py.websocket import EchoWebSocket

conn = pymongo.MongoClient("mongodb://localhost")
db = conn["mchat"]

app = Flask(__name__)
app.secret_key = "70hn637p1iLalKE68ZuYicg9vsf5K3R4"

@app.route("/login",methods=["GET","POST"])
def login():
	if "username" in session:
		return redirect(url_for("index"))
	if not "username" in request.form or not "pw" in request.form:
		return render_template("login.html",error=False)
	user = db.users.find_one({"username":request.form["username"]},fields=["pw"]) 
	if user == None or not sha256_crypt.verify(request.form["pw"],user["pw"]):
		return render_template("login.html",error=True,errormsg="Falscher Benutzername oder Passwort")
	session["username"] = request.form["username"]
	return redirect(url_for("index"))

@app.route("/logout")
def logout():
	session.pop('username', None)
	return redirect(url_for('login'))
	
@app.route("/api/send",methods=["POST"])
def send():
	if not "username" in session or not session["username"] == "admin":
		abort(403)
	if not "author" in request.form or not "content" in request.form:
		abort(400)
	msg = {"content":str(request.form["content"]),"time":datetime.datetime.now().strftime("%X %x"),
			"author":str(request.form["author"])}

	request.environ["chat.app"].sendToAll(msg)
	return {}

@app.route("/api/get")
def get():
	if not "username" in session or not session["username"] == "admin":
		abort(403)



@app.route("/")
def index():
    if not "username" in session:
        return redirect(url_for("login"))
    entries = db.messages.find(sort=[("time",1)],limit=300)
    return render_template("index.html",entries=entries,username=session["username"])

class ChatWebSocket(EchoWebSocket):
	def opened(self):
		app = self.environ['chat.app']
		app.clients.append(self)

	def received_message(self, m):
		app = self.environ['chat.app']
		msg = {"content":str(m),"time":datetime.datetime.now(),
			"author":str(self.environ["chat.sess"]["username"])}
		db.messages.insert(msg)
		del msg["_id"]
		msg["time"] = msg["time"].strftime("%X %x")
		s = json.dumps(msg)
		app.sendToAll(s)

	def closed(self, code, reason):
		app = self.environ.pop('chat.app')
		if self in app.clients:
			app.clients.remove(self)

class Application(object):
	ws = WebSocketWSGIApplication(handler_cls=ChatWebSocket)
	clients = []
	long_clients = []
	def __call__(self,environ,start_response):
		path = environ["PATH_INFO"]

		req = Request(environ)
		i = SecureCookieSessionInterface()
		sess = i.open_session(app,req)

		environ["chat.app"] = self

		if path == "/websocket":
			if not "username" in sess:
				start_response("403 Forbidden",[])
				return ""
			environ["chat.req"] = req
			environ["chat.sess"] = sess
			self.ws(environ,start_response)
		else:
			return app(environ,start_response)

	def sendToAll(self,s):
		for socket in self.clients:
			socket.send(s)



if __name__ == "__main__":
	app.debug = True
	
	"""server = make_server('', 8080, server_class=WSGIServer,
                     handler_class=WebSocketWSGIRequestHandler,
                     app=my_app)
	server.initialize_websockets_manager()
	server.serve_forever()"""
	server = WSGIServer(("0.0.0.0", 8080), Application())
	server.serve_forever()