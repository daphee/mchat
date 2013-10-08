# -*- coding: utf-8 -*- 
from gevent import monkey
monkey.patch_all()
from flask import Flask,render_template,request,url_for, session,redirect,Response,abort
import pymongo,datetime
from werkzeug.wrappers import Request
from passlib.hash import sha256_crypt
import json,urlparse,random,string
from flask.sessions import SecureCookieSessionInterface
import json
from bson.objectid import ObjectId
from ws4py.server.geventserver import WebSocketWSGIApplication,WSGIServer
from gevent import queue,Timeout
import gevent
from gevent.event import Event
from ws4py.websocket import EchoWebSocket
import config
import redis,time

conn = config.get_mongo()
db = conn["mchat"]

red = config.get_red()

app = Flask(__name__)
app.secret_key = config.secret_key

NUM_MESSAGES = 50

#Encode ObjectIDs
class CustomEncoder(json.JSONEncoder):
	def default(self, obj):
		if isinstance(obj, ObjectId):
			return str(obj)
		else:
			return super(CustomEncoder, self).default(obj)

#Get newest messages
def get_newest(limit=NUM_MESSAGES):
	#Limit 'limit' elements. We sort descending because we want 'limit' from newest to oldest. 
	#Nevertheless JS processes oldest to newest. So we reverse in Python
	msgs = []
	for msg in db.messages.find().sort("time",direction=pymongo.DESCENDING).limit(limit):
		msg["time"] = msg["time"].strftime("%X %x")
		msgs.append(msg)
	msgs.reverse()
 	return msgs

#Get messages newer than id ($natural order)
#Expects string id
def get_newer_than(i):
	msgs = []
	for msg in db.messages.find({"_id":{"$gt":ObjectId(i)}}):
		msg["time"] = msg["time"].strftime("%X %x")
		msgs.append(msg)
	return msgs


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

@app.route("/api/login",methods=["POST"])
def api_login():
	if not "username" in request.form or not "pw" in request.form:
		abort(400)
	user = db.users.find_one({"username":request.form["username"]},fields=["pw"]) 
	if user == None or not sha256_crypt.verify(request.form["pw"],user["pw"]):
		abort(403)
	secret = ''.join(random.choice(string.ascii_letters+string.digits) for x in range(16))
	red.set(secret,True,ex=3600*12)
	return secret

@app.route("/api/send",methods=["POST"])
def send():
	if not "secret" in request.form or red.get(request.form["secret"])==None:
		abort(403)
	if not "author" in request.form or not "content" in request.form:
		abort(400)
	msg = {"content":str(request.form["content"]),"time":datetime.datetime.now(),
			"author":str(request.form["author"]),"type":"msg"}

	request.environ["chat.app"].sendToAll(msg)
	return "success"

class TimeoutException(Exception):
    pass

#Working!!!! Can return ms per request
"""
def chat_poller(q,i):
	#Break request after 60 seconds
	t = Timeout(60,TimeoutException)
	t.start()
	try:
		#First return messages from db
		for msg in get_newer_than(i):
			s = (json.dumps(msg,cls=CustomEncoder).replace("\n"," ")+"\n")
			q.put(s)
		#Then subscribe to the channel
		client = red.pubsub()
		client.subscribe("chat")
		chat = client.listen()
		for msg in chat:
			if msg["type"] == "message":
				s = (msg["data"].replace("\n"," ")+"\n")
				q.put(s)
	except TimeoutException:
		q.put(StopIteration)
		print "Timeout"

def get(environ,start_response):
	request = environ["chat.req"]
	if not "secret" in request.form or red.get(request.form["secret"])==None:
		abort(403)

	if not "operation" in request.form:
		abort(400)
	headers = [
		("Content-Type","application/json")
	]

	if request.form["operation"] == "newer_than":
		#Initial GET/Get newest entrys
		if not "_id" in request.form or request.form["_id"] == "0":
			msgs = get_newest()
			resp = ""
			for msg in msgs:
				resp+=(json.dumps(msg,cls=CustomEncoder).replace("\n"," ")+"\n")
			start_response("200 OK",headers)
			return resp
		else:
			q = queue.Queue()
			#headers.append(("Transfer-Encoding","chunked"))
			start_response("200 OK",headers)
			gevent.spawn(chat_poller,q,request.form["_id"])
			return q
	else:
		abort(400)
"""

@app.route("/api/get",methods=["POST"])
def get():
	if not "secret" in request.form or red.get(request.form["secret"])==None:
		abort(403)

	if not "operation" in request.form:
		abort(400)

	if request.form["operation"] == "newer_than":
		msgs = []
		if not "_id" in request.form or request.form["_id"] == "0":
			if "limit" in request.form and request.form["limit"].isdigit():
				msgs = get_newest(int(request.form["limit"]))
			else:
				msgs = get_newest()
		else:
			msgs = get_newer_than(request.form["_id"])

		#If there were no messages wait till we get the first/newest over the redis channel
		if len(msgs) == 0:
			client = red.pubsub()
			client.subscribe("chat")
			chat = client.listen()
			#For loop only to filter the subscribe-notification
			for msg in chat:
				if msg["type"] == "message":
					return "["+msg["data"]+"]"

		return json.dumps(msgs,cls=CustomEncoder)
	else:
		abort(400)
@app.route("/api/time")
def api_time():
	return str(int(time.time()))

@app.route("/")
def index():
    if not "username" in session:
        return redirect(url_for("login"))
    return render_template("index.html",username=session["username"])

class ChatWebSocket(EchoWebSocket):
	def opened(self):
		app = self.environ['chat.app']
		app.clients.append(self)

	def received_message(self, m):
		app = self.environ['chat.app']
		packet = json.loads(str(m))
		print "Got",packet
		#A Chat message was received
		if packet["type"] == "send":
			msg = {"content":packet["msg"],"time":datetime.datetime.now(),
				"author":self.environ["chat.sess"]["username"],"type":"msg"}
			app.sendToAll(msg)
		#Client wants something different
		elif packet["type"] == "request":
			#Sync or initial load
			if packet["operation"] == "newer_than":
				resp = {"type":"response","operation":"newer_than"}
				#INitial load
				if packet["_id"] == "0":
					resp["response_data"] = get_newest()
				#Sync
				else:
					resp["response_data"] = get_newer_than(packet["_id"])
				self.send(json.dumps(resp,cls=CustomEncoder))



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
		#elif path == "/api/get":
		#	environ["chat.req"] = req
		#	return get(environ,start_response)
		else:
			return app(environ,start_response)

	def sendToAll(self,msg):
		db.messages.insert(msg)
		msg["time"] = msg["time"].strftime("%X %x")
		s = json.dumps(msg,cls=CustomEncoder)
		for socket in self.clients:
			socket.send(s)
			red.publish("chat",s)

if __name__ == "__main__":
	app.debug = True
	server = WSGIServer(("0.0.0.0", 8080), Application())
	server.serve_forever()