class_name Robot extends Node3D

@export var serverAddress : String = "127.0.0.1"
@export var port : int = 54045
@export var target : Node3D
@export var gripping : bool = false

@onready var ik : IterateIK3D = $Armature/Skeleton3D/CCDIK3D

var _pingTimer : Timer = Timer.new()
var _streamPeer : StreamPeerTCP = StreamPeerTCP.new()

func _ready() -> void:
	ik.set_target_node(0, target.get_path())
	
	_pingTimer.wait_time = 5
	_pingTimer.autostart = true
	_pingTimer.one_shot = false
	_pingTimer.timeout.connect(_ping)
	
	_connectToServer()
	return

func _process(delta : float) -> void:
	_streamPeer.poll()
	var stat = _streamPeer.get_status()
	if(stat == StreamPeerSocket.Status.STATUS_CONNECTED):
		_readPacket()
	return

#TODO Needs testing
func _readPacket() -> void:
	#According to Codesys, floats are sent as float32 and bools as 1 byte
	
	#TODO: Test
	var result : Array = _streamPeer.get_data(3*4 + 1)
	var err : Error = result[0]
	if(err == OK):
		var data : PackedByteArray = result[1]
		target.x = data.decode_float(0)
		target.y = data.decode_float(4*1)
		target.z = data.decode_float(4*2)
		gripping = data.decode_u8(4*2 + 1) > 0 #Into bool
	else:
		print("Error '%s' occurred when getting packet." % error_string(err))
	return

func _ping() -> void:
	var status : StreamPeerSocket.Status = _streamPeer.get_status()
	if(status == StreamPeerSocket.Status.STATUS_ERROR):
		print("Connection error. Attempting reconnection.")
		_connectToServer()
	return

func _connectToServer() -> void:
	_pingTimer.paused = true
	var err : Error = _streamPeer.connect_to_host(serverAddress, port)
	while _streamPeer.poll() != OK:
		if(err == ERR_CANT_CONNECT || err == ERR_CONNECTION_ERROR):
			print("Connection error '%s'. Retrying." % error_string(err))
			
		err =  _streamPeer.connect_to_host(serverAddress, port)
		
	if(err == OK):
		print("Connected to server %s:%s" % [_streamPeer.get_connected_host(), _streamPeer.get_connected_port()])
	elif(err == ERR_TIMEOUT):
		print("Connection timed out.")
	else:
		print("Could not connect.")
	
	_pingTimer.paused = false
	return
