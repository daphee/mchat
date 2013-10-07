wsLocation = "ws://"+window.location.host+"/websocket";

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
	var template = "<p><i>{time}</i><b> {author}: </b>{content}</p>";
	$("#messages").append(nano(template,msg));
}

function createWebSocket(){
	ws = new WebSocket(wsLocation);
	ws.onopen = function(evt){
		addStatus("Verbindung hergestellt");
	}
	ws.onclose = function(evt){
		addStatus("Verbindung abgebrochen.");
		setTimeout(createWebSocket,5000);
	}
	ws.onmessage = function(evt) {
		var msg = $.parseJSON(evt.data);
		if("time" in msg && "author" in msg && "content" in msg){
			addMessage(msg);
		}
	}
}
createWebSocket();
$(document).ready(function(){
	$("textarea").keydown(function(evt){
		if(evt.which==13 && !evt.shiftKey){
			var val = $(this).val();
			$(this).val("");
			ws.send(val);
		}
	});
});