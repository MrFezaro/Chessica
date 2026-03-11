extends MeshInstance3D

@export var speed : float = 0.2
@export var closePosition : Vector3 = Vector3(0.1, 0, 0)

var close : bool = false

@onready var finger1 : Node3D = $Endpoint/Finger1
@onready var finger1Start : Vector3 = finger1.position
@onready var finger2 : Node3D = $Endpoint/Finger2
@onready var finger2Start : Vector3 = finger2.position

func _process(delta: float) -> void:
	var s = delta * speed
	if(close):
		finger1.position = finger1.position.move_toward(finger1Start - closePosition, s)
		finger2.position = finger2.position.move_toward(finger2Start + closePosition, s)
	else:
		finger1.position = finger1.position.move_toward(finger1Start, s)
		finger2.position = finger2.position.move_toward(finger2Start, s)
	return
