##Helper node for [Robot] to handle networking.
##NOTE: Codesys Simulation Mode does not allow for networking.
##It purely simulates logic.
class_name RobotNetNode extends Node

var positionOut : Vector3
var gripOut : bool

var serverAddress : String
var port : int

var _pingTimer : Timer = Timer.new()
var _streamPeer : StreamPeerTCP = StreamPeerTCP.new()

func getConnectionStatus() -> StreamPeerSocket.Status:
	return _streamPeer.get_status()

func reconnect() -> void:
	_connectToServer()
	return

func sendPacket(posNGrip : Vector4) -> void:
	var msg = str(posNGrip)
	msg = msg.replace(" ", "")
	_streamPeer.put_string(msg)
	return

func _ready() -> void:
	_pingTimer.wait_time = 1
	_pingTimer.autostart = true
	_pingTimer.one_shot = false
	_pingTimer.timeout.connect(_ping)
	add_child(_pingTimer)
	return

func _process(delta : float) -> void:
	_streamPeer.poll()
	var stat = _streamPeer.get_status()
	if(stat == StreamPeerSocket.Status.STATUS_CONNECTED):
		_readPacket()
	return

#TODO Needs testing
func _readPacket() -> void:
	#PLC sends data as a STRING, formatted as:
	#(x.x,y.y,z.z,g.g)
	#Every number is separated by , and sent with 6 decimals.
	
	var availableData : int = _streamPeer.get_available_bytes()
	if(availableData == 0):
		return
	
	var incomingPacket : String = _streamPeer.get_string(availableData) 
	print("Received: %s" % incomingPacket)
	
	var startIndex = incomingPacket.find("(")+1
	var endIndex = incomingPacket.find(")", startIndex)
	if(startIndex == -1 || endIndex == -1):
		return
	
	var extracted : String = incomingPacket.substr(startIndex, endIndex - startIndex)
	
	#Split packet
	var vec : PackedFloat64Array = extracted.split_floats(",", false)
	
	if(vec.size() == 4):
		positionOut.x = vec[0]
		positionOut.y = vec[1]
		positionOut.z = vec[2]
		gripOut = vec[3] > 0 #Into bool
	else:
		print("Packet size invalid (vec.size() =/= 4).")
	
	return

func _ping() -> void:
	var status : StreamPeerSocket.Status = _streamPeer.get_status()
	if(status != StreamPeerSocket.Status.STATUS_CONNECTED):
		reconnect()
	return

func _connectToServer() -> void:
	var stat = _streamPeer.get_status()
	if(stat != StreamPeerSocket.Status.STATUS_NONE):
		if(stat == StreamPeerSocket.Status.STATUS_CONNECTING):
			print("Connecting to: %s:%s" % [serverAddress, port])
		elif(stat == StreamPeerSocket.Status.STATUS_CONNECTED):
			print("Connected to server: %s:%s" % [serverAddress, port])
		elif(stat == StreamPeerSocket.Status.STATUS_ERROR):
			print("Could not connect. Error occurred.")
		return
	
	var err : Error = _streamPeer.connect_to_host(serverAddress, port)
	
	if(err == OK && _streamPeer.get_status() == StreamPeerSocket.STATUS_CONNECTED):
		print("Connected to server %s:%s" % [_streamPeer.get_connected_host(), _streamPeer.get_connected_port()])
	else:
		print("Could not connect. Error: %s" % error_string(err))
	
	return
