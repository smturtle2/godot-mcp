@tool
extends SceneTree

## Validate snapshot source files without opening scenes or instantiating user scripts.
const LogBuffer = preload("res://addons/godot_mcp/log_buffer.gd")

var logger: Logger

func _initialize() -> void:
	logger = LogBuffer.new()
	OS.add_logger(logger)
	var args: PackedStringArray = OS.get_cmdline_user_args()
	if args.size() < 2:
		_finish({}, "Expected INPUT_JSON and OUTPUT_JSON arguments.")
		return
	var input: Variant = JSON.parse_string(FileAccess.get_file_as_string(args[0]))
	if not input is Dictionary:
		_finish({}, "INPUT_JSON must contain a JSON object.")
		return
	var result: Dictionary = {"sources": []}
	var revisions: Dictionary = input.get("revisions", {})
	for uri_value: Variant in input.get("uris", []):
		result.sources.append(validate_uri(str(uri_value), revisions))
	_finish(result, "")

func validate_uri(uri: String, revisions: Dictionary) -> Dictionary:
	var supplied_revision: String = str(revisions.get(uri, ""))
	var item: Dictionary = {"uri": uri, "revision": supplied_revision, "state": "unavailable", "valid": null, "entries": [], "scope": "snapshot"}
	if not uri.begins_with("res://") or uri.get_extension().to_lower() not in ["gd", "gdshader"]:
		return item
	if not ResourceLoader.exists(uri):
		return item
	var cursor: int = logger.read().cursor
	var resource: Resource = ResourceLoader.load(uri)
	if not resource or (not resource is Script and not resource is Shader):
		item.state = "unavailable"
		item.entries = entries_since(cursor, uri)
		return item
	var source: String
	var valid: bool
	var diagnostics: Array = []
	if resource is Script:
		source = resource.source_code
		valid = resource.reload(true) == OK
	else:
		source = resource.code
		resource.get_rid()
		diagnostics = entries_since(cursor, uri)
		valid = diagnostics.filter(func(entry: Dictionary) -> bool: return entry.kind == "error").is_empty()
	item.revision = source.sha256_text()
	item.valid = valid
	item.state = "valid" if valid else "invalid"
	if resource is Script:
		diagnostics = entries_since(cursor, uri)
	item.entries = diagnostics
	return item

func entries_since(cursor: int, current_uri: String) -> Array:
	var entries: Array = []
	for raw: Dictionary in logger.read(cursor).entries:
		var entry: Dictionary = raw.duplicate(true)
		var location: String = str(entry.get("uri", ""))
		if location.is_empty():
			entry.uri = current_uri
			entry.origin = "source"
		elif location == current_uri:
			entry.origin = "source"
		elif location.begins_with("res://"):
			entry.origin = "dependency"
		else:
			entry.origin = "engine"
		entries.append(entry)
	return entries

func _finish(result: Dictionary, failure: String) -> void:
	var args: PackedStringArray = OS.get_cmdline_user_args()
	var output_path: String = str(args[1]) if args.size() > 1 else ""
	var payload: Dictionary = result
	var exit_code := 0
	if not failure.is_empty():
		payload = {"error": failure, "sources": []}
		exit_code = 2
	if output_path.is_empty():
		push_error("Validation runner: output path is missing.")
		quit(2)
		return
	var file := FileAccess.open(output_path, FileAccess.WRITE)
	if not file:
		push_error("Validation runner: cannot open output file: " + output_path)
		quit(2)
		return
	file.store_string(JSON.stringify(payload))
	if file.get_error() != OK and file.get_error() != ERR_FILE_EOF:
		push_error("Validation runner: cannot write output file: " + output_path)
		quit(2)
		return
	file.close()
	quit(exit_code)
