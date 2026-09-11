@tool
extends RefCounted
## Packs a viewport image and its pixel-to-viewport coordinate mapping.

const Codec = preload("res://addons/godot_mcp/codec.gd")
const MAX_PNG_BYTES: int = 16 * 1024 * 1024

static func _fail(code: String, message: String) -> Dictionary:
	return {"error": {"code": code, "message": message}}

static func pack(image: Image, p: Dictionary, metadata: Dictionary, viewport_size: Vector2) -> Dictionary:
	if image == null or image.is_empty():
		return _fail("CAPTURE_FAILED", "Capture image is empty.")

	var original := image.get_size()
	var crop := Rect2i(Vector2i.ZERO, original)
	if p.has("rect"):
		var requested: Dictionary = p.get("rect", {})
		if not requested is Dictionary:
			return _fail("INVALID_RECT", "Capture rectangle must be an object.")
		var origin_value: Variant = requested.get("origin", {})
		var size_value: Variant = requested.get("size", {})
		if not origin_value is Dictionary or not size_value is Dictionary:
			return _fail("INVALID_RECT", "Capture rectangle must include origin and size objects.")
		var requested_rect := Rect2i(Vector2i(Codec.v2(origin_value)), Vector2i(Codec.v2(size_value)))
		if not requested_rect.has_area():
			return _fail("INVALID_RECT", "Capture rectangle has no area.")
		crop = requested_rect.intersection(crop)
		if not crop.has_area():
			return _fail("INVALID_RECT", "Capture rectangle is outside the image.")

	var output: Image = image.get_region(crop)
	var has_width := p.has("max_width")
	var has_height := p.has("max_height")
	if has_width or has_height:
		var max_width: int = output.get_width()
		var max_height: int = output.get_height()
		if has_width:
			max_width = int(p.get("max_width", 0))
		if has_height:
			max_height = int(p.get("max_height", 0))
		if max_width <= 0 or max_height <= 0:
			return _fail("INVALID_DIMENSIONS", "Maximum capture dimensions must be positive.")
		var resize_scale := minf(1.0, minf(float(max_width) / output.get_width(), float(max_height) / output.get_height()))
		if resize_scale < 1.0:
			output.resize(maxi(1, int(output.get_width() * resize_scale)), maxi(1, int(output.get_height() * resize_scale)))

	var png := output.save_png_to_buffer()
	if png.size() > MAX_PNG_BYTES:
		return _fail("CAPTURE_TOO_LARGE", "Capture PNG exceeds 16 MiB; crop the capture or provide explicit max dimensions.")

	var result: Dictionary = metadata.duplicate()
	result["image_base64"] = Marshalls.raw_to_base64(png)
	result["width"] = output.get_width()
	result["height"] = output.get_height()
	result["viewport_size"] = Codec.encode(viewport_size)
	result["pixel_size"] = Codec.encode(original)
	result["crop"] = Codec.encode(crop)
	result["scale"] = Codec.encode(Vector2(float(output.get_width()) / crop.size.x, float(output.get_height()) / crop.size.y))
	var axis_factor := Vector2(crop.size) / Vector2(output.get_size()) * viewport_size / Vector2(original)
	var capture_to_viewport := Transform2D(Vector2(axis_factor.x, 0.0), Vector2(0.0, axis_factor.y), Vector2(crop.position) * viewport_size / Vector2(original))
	result["mapping"] = {"target": metadata.get("kind"), "capture_to_viewport": Codec.encode(capture_to_viewport)}
	return result
