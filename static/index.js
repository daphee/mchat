wsLocation = "ws://"+window.location.host+"/websocket";
syncing = false;
buffer = [];

function nano(template, data) {
  return template.replace(/\{([\w\.]*)\}/g, function(str, key) {
    var keys = key.split("."), v = data[keys.shift()];
    for (var i = 0, l = keys.length; i < l; i++) v = v[keys[i]];
    return (typeof v !== "undefined" && v !== null) ? v : "";
  });
}

function addStatus(status){
	var html = "<p style='color:red;'>"+status+"</p>";
	$("#messages").append(html);
}

function addMessage(msg){
	var template = "<p class='message' data-id='{_id}'><i>{time}</i><b> {author}: </b>{content}</p>";
	$("#messages").append(nano(template,msg));
}

function createWebSocket(){
	ws = new WebSocket(wsLocation);
	ws.onopen = function(evt){
		addStatus("Verbindung hergestellt");
		if(!syncing)
			sync();
	}
	ws.onclose = function(evt){
		addStatus("Verbindung abgebrochen.");
		if(syncing){
			console.log("ERROR: Connection lost while syncing.");
			syncing = false;
		}
		setTimeout(createWebSocket,5000);
	}
	ws.onmessage = function(evt) {
		var msg = $.parseJSON(evt.data);
		if(msg["type"]=="msg" && "time" in msg && "author" in msg && "content" in msg && "_id" in msg){
			if(syncing){
				buffer.push(msg);
				return;
			}
			addMessage(msg);
		}
		else if(msg["type"]=="response" && msg["operation"]=="newer_than" && syncing){
			var c = 0;
			$(msg["response_data"]).each(function(i,el){
				addMessage(el);
				c++;
			});
			console.log("Synced "+c+" messages");
			clearBuffer();
			syncing = false;
		}
	}
}

function waitForSocket(){
	if(ws.readyState != ws.OPEN)
		setTimeout(waitForSocket,250);
}

function sendMessage(msg){
	var packet = {"type":"send","msg":msg};
	console.log("Sending:"+JSON.stringify(packet));
	ws.send(JSON.stringify(packet));
}

function sync(){
	syncing = true;
	packet = {"type":"request","operation":"newer_than"}
	var id;
	if($(".message").length==0)
		id = "0";
	else {
		id = $("#messages > .message").last().attr("data-id");
	}
	console.log("Syncing. Newest:"+id);
	packet["_id"] = id;
	waitForSocket();
	ws.send(JSON.stringify(packet));
}

function clearBuffer(){
	$(buffer).each(function(i,el){
		var exists = false;
		$(".message").each(function(i,el){
			if(el["_id"]==$(el).attr("data-id")){
				exists = true;
				return false;
			}
		});
		if(!exists){
			addMessage(el);
		}
	});
}

createWebSocket();
$(document).ready(function(){
	$("textarea").keydown(function(evt){
		if(evt.which==13 && !evt.shiftKey){
			var val = $(this).val();
			$(this).val("");
			sendMessage(val);
		}
	});
});