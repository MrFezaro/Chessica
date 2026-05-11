class_name Robot extends Node3D

signal serverAddressChanged()

##Replace this with the PLC's IP address
@export var serverAddress : String = "127.0.0.1":
	set(new):
		serverAddress = new
		serverAddressChanged.emit()

##Default port is [param 5000]. 
##This must be changed depending on what port the PLC is using.
@export var port : int = 5000:
	set(new):
		port = new
		netNode.reconnect()

@export var target : Node3D
@export var gripping : bool = false
##Whether to listen to incoming TCP traffic.
@export var netMode : bool = true

@export var manualControlSpeed : float = 0.5

@onready var ik : IterateIK3D = $Armature/Skeleton3D/CCDIK3D
@onready var netNode : RobotNetNode = $RobotNetNode

func _ready() -> void:
	ik.set_target_node(0, target.get_path())
	
	serverAddressChanged.connect(_onServerAddressChanged)
	_onServerAddressChanged()
	return

func _process(delta : float) -> void:
	if(netMode):
		_netControl(delta)
	else:
		_manualControl(delta)
	return

func _netControl(delta : float) -> void:
	if(netNode.getConnectionStatus() == StreamPeerSocket.STATUS_CONNECTED):
		target.position = netNode.positionOut
		gripping = netNode.gripOut
	return

func _manualControl(delta : float) -> void:
	var x = -Input.get_axis(&"move_left", &"move_right")
	var y = Input.get_axis(&"move_down", &"move_up")
	var z = Input.get_axis(&"move_backward", &"move_forward")
	
	target.position += Vector3(x, y, z) * manualControlSpeed * delta
	if(Input.is_action_just_pressed(&"grip_toggle")):
		gripping = !gripping
		$Armature/Skeleton3D/J6/GripperBase.close = gripping
		
		if(gripping):
			print("Gripping!")
		else:
			print("Releasing!")
	return

func _onServerAddressChanged() -> void:
	netNode.serverAddress = serverAddress
	netNode.port = port
	netNode.reconnect()
	return
