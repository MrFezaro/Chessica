class_name Robot extends Node3D

signal serverAddressChanged()

@export var moveSpeed : float = 0.1

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

##This node's position will be set according to [member Robot.chessBoardTf]
##to keep it in the correct position relative to the robot.
@export var chessBoard : Node3D
@export var target : Node3D
@export var gripping : bool = false
##Whether to listen to incoming TCP traffic.
@export var netMode : bool = true
##When in shadow mode, the robot will not send feedback and only read incoming
##messages. This means the simulator will mimic the timings of the real robot.
@export var shadowMode : bool = true

@export var manualControlSpeed : float = 0.5

@onready var ik : IterateIK3D = $Armature/Skeleton3D/CCDIK3D
@onready var netNode : RobotNetNode = $RobotNetNode

var _currentPos : Vector3 = Vector3.ZERO
var _goalPos : Vector3 = Vector3.ZERO

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
	
	if(_targetReached):
		_currentPos = Vector3(
			target.global_position.x,
			target.global_position.z,
			target.global_position.y)
		
		if(!shadowMode):
			_sendFeedback()
	return

func _netControl(delta : float) -> void:
	if(netNode.getConnectionStatus() == StreamPeerSocket.STATUS_CONNECTED):
		
		var incoming = netNode.positionOut / 1000 #from mm
		_goalPos = incoming
		var temp = _currentPos.move_toward(_goalPos, delta*moveSpeed)
		
		target.global_position = Vector3(temp.x, temp.z, temp.y)
		gripping = netNode.gripOut
		$Armature/Skeleton3D/J6/GripperBase.close = gripping
		
		
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

func _targetReached() -> bool:
	return abs(target.global_position - _currentPos) < 0.05

func _sendFeedback():
	var backPos : Vector3 = $Armature/Skeleton3D/J6/EndEffector.global_position
	#Do a little cheating because IK isn't as precise as the real thing.
	var delta : Vector3 = abs(backPos - target.global_position)
	if(delta.length() < 0.05):
		backPos = target.global_position
	
	backPos *= 1000 #To millimeters
	netNode.sendPacket(Vector4(backPos.x, backPos.z, backPos.y, gripping))
	return

func _onServerAddressChanged() -> void:
	netNode.serverAddress = serverAddress
	netNode.port = port
	netNode.reconnect()
	return
