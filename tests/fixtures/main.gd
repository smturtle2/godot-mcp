extends Node2D
signal health_changed(value: int)
var health: int = 3
var ticks: int = 0

func _process(_delta: float) -> void:
	ticks += 1
	queue_redraw()

func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_accept"):
		health -= 1
		health_changed.emit(health)

func _draw() -> void:
	draw_rect(Rect2(0, 0, 480, 320), Color("071b33"))
	for x in range(0, 481, 20):
		draw_line(Vector2(x, 0), Vector2(x, 320), Color("123656"))
	for y in range(0, 321, 20):
		draw_line(Vector2(0, y), Vector2(480, y), Color("123656"))
	draw_rect(Rect2(40, 70, 400, 180), Color("0b2946"))
	draw_rect(Rect2(40, 70, 400, 180), Color("238bd0"), false, 2)
	draw_string(ThemeDB.fallback_font, Vector2(64, 108), "GODOT MCP / LIVE TEST", HORIZONTAL_ALIGNMENT_LEFT, -1, 20, Color("8dd5ff"))
	draw_string(ThemeDB.fallback_font, Vector2(64, 218), "INPUT > STATE > CAPTURE", HORIZONTAL_ALIGNMENT_LEFT, -1, 16, Color("62a7d7"))
	for i in range(3):
		draw_circle(Vector2(85 + i * 50, 155), 12, Color("39adff") if i < health else Color("173f62"))
