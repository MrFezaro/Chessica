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
@export var _basePort : int = 5000

var _port : int = _basePort

##This node's position will be set according to [member Robot.chessBoardTf]
##to keep it in the correct position relative to the robot.
@export var chessBoard : Node3D
@export var target : Node3D
@export var gripping : bool = false
##Whether to listen to incoming TCP traffic.
@export var netMode : bool = true

##When in shadow mode, the simulated robot will connect to port [code]_basePort + 1[/code].
##Feedback will be sent to the PLC, but ignored by it. This is due to the
##connection logic at the PLC which expects initial positions and feedback to work.
@export var shadowMode : bool = true:
	set(new):
		shadowMode = new
		if(shadowMode):
			_port = _basePort + 1
		else:
			_port = _basePort
		serverAddressChanged.emit()
		if(netNode != null):
			netNode.reconnect()

@export var manualControlSpeed : float = 0.5

@onready var ik : IterateIK3D = $Armature/Skeleton3D/CCDIK3D
@onready var netNode : RobotNetNode = $RobotNetNode

var _currentPos : Vector3 = Vector3.ZERO
var _goalPos : Vector3 = Vector3.ZERO

func _ready() -> void:
	ik.set_target_node(0, target.get_path())
	
	if(shadowMode):
		_port = _basePort + 1 #Logic in setter not triggering on first try
	
	serverAddressChanged.connect(_onServerAddressChanged)
	serverAddressChanged.emit()
	return

func _process(delta : float) -> void:
	if(netMode):
		_netControl(delta)
	else:
		_manualControl(delta)
	
	if(_targetReached):
		_currentPos = target.global_position
	
	_sendFeedback() #_basePort + 1 ignores feedback at PLC
	return

func _netControl(delta : float) -> void:
	if(netNode.getConnectionStatus() == StreamPeerSocket.STATUS_CONNECTED):
		
		var incoming = netNode.positionOut / 1000 #from mm
		_goalPos = Vector3(incoming.y, incoming.z, incoming.x)
		$GoalPosMesh.global_position = Vector3(incoming.y, incoming.z, incoming.x)
		
		var temp = _currentPos.move_toward(_goalPos, delta*moveSpeed)
		target.global_position = temp
		
		gripping = netNode.gripOut
		$Armature/Skeleton3D/J6/GripperBase.close = gripping
	else:
		netNode.reconnect()
		
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
	#Do a little cheating because sim IK isn't as precise as the real thing.
	var delta : Vector3 = abs(backPos - target.global_position)
	if(delta.length() < 0.05):
		backPos = target.global_position
	
	backPos *= 1000 #To millimeters
	netNode.sendPacket(Vector4(backPos.y, backPos.z, backPos.x, gripping))
	return

func _onServerAddressChanged() -> void:
	netNode.serverAddress = serverAddress
	netNode.port = _port
	netNode.reconnect()
	return
