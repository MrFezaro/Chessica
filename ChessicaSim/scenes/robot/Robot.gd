class_name Robot extends Node3D

@export var target : Node3D

@onready var ik : IterateIK3D = $Armature/Skeleton3D/CCDIK3D

func _ready() -> void:
	ik.set_target_node(0, target.get_path())
	return
