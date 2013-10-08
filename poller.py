import requests
import json

base = "http://daphee.kd.io:8080"

secret = requests.post(base+"/api/login",data={"username":"daphee","pw":"felix2006"}).content

print "Got secret:",secret

_id = "0"

while True:
    print "Polling from ID '%s'" % _id
    response = requests.post(base+"/api/get",data={"secret":secret,"operation":"newer_than","_id":_id},stream=True)
    last = None
    for line in response.iter_lines():
        print "Got line:",line
        obj = json.loads(line)
        last = obj
    if not last == None:
        _id = last["_id"]
    