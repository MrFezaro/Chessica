class_name Robot extends Node3D

@export var serverAddress : String = "127.0.0.1":
	set(new):
		serverAddress = new
		netNode.reconnect()

@export var port : int = 54045:
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
	
	netNode.serverAddress = serverAddress
	netNode.port = port
	return

func _process(delta: float) -> void:
	if(netMode):
		if(netNode.positionOut == Vector3.ZERO):
			printerr("Incoming network target position is '%s'. Ignoring." % netNode.positionOut)
		else:
			target.position = netNode.positionOut
			gripping = netNode.gripOut
	else:
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
