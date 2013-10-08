import requests
import json,sys

base = "http://localhost:8080"

secret = None

if len(sys.argv) == 2:
	secret = sys.argv[1]
else:
	secret = requests.post(base+"/api/login",data={"username":"daphee","pw":"felix2006"}).content

print "Got secret:",secret

_id = "0"

while True:
	print "Polling from ID '%s'" % _id
	response = requests.post(base+"/api/get",data={"secret":secret,"operation":"newer_than","_id":_id})
	last = None
	for msg in json.loads(response.content):
		print msg["time"],"-",msg["author"]+":",msg["content"]
		last = msg
	if not last == None:
		_id = last["_id"]
	"""response = requests.post(base+"/api/get",data={"secret":secret,"operation":"newer_than","_id":_id},stream=True)
	for line in response.iter_content():
		print line,"""
