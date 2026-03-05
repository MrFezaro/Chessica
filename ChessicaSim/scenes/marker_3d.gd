extends Marker3D

var speed : float = 0.1

func _input(event: InputEvent) -> void:
	if(event.is_action(&"ui_up")):
		position.x += speed
	elif(event.is_action(&"ui_down")):
		position.x -= speed
	
	if(event.is_action(&"ui_left")):
		position.z -= speed
	elif(event.is_action(&"ui_right")):
		position.z += speed
	return
