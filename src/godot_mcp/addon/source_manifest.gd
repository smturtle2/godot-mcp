extends RefCounted
## Shared, bounded provenance for editor-launched games. File identity is not
## evidence that every file was loaded or that a behavior was executed.
const EXCLUDED := [".git", ".godot", ".godot-mcp", ".venv", ".pytest_cache", ".ruff_cache"]
const EXTENSIONS := ["gd", "gdshader", "gdshaderinc", "tscn", "tres", "scn", "res"]
const REQUEST := "res://.godot-mcp/run-source-request.json"
const SCOPE := "project settings, scripts, shaders, scenes and resource files; excludes caches, symlinks and other asset formats"
const MAX_FILES := 20000
const MAX_BYTES := 512 * 1024 * 1024

static func capture() -> Dictionary:
	var files: Dictionary = {}
	var skipped: Array = []
	var message: String = _walk("res://", files, skipped, [0, 0])
	var sorted: Dictionary = {}
	var paths: Array = files.keys()
	paths.sort()
	for uri: String in paths: sorted[uri] = files[uri]
	skipped.sort()
	return {"files": sorted, "snapshot_id": JSON.stringify(sorted).sha256_text(), "scope": SCOPE, "complete": message.is_empty() and skipped.is_empty(), "skipped_paths": skipped, "reason": message}

static func _walk(path: String, files: Dictionary, skipped: Array, budget: Array) -> String:
	var directory := DirAccess.open(path)
	if not directory: return "Cannot read source manifest directory: " + path
	directory.list_dir_begin()
	var name: String = directory.get_next()
	while not name.is_empty():
		var uri: String = path.path_join(name)
		if name in EXCLUDED:
			pass
		elif directory.is_link(name):
			skipped.append(uri)
		elif directory.current_is_dir():
			var message: String = _walk(uri, files, skipped, budget)
			if not message.is_empty(): return message
		else:
			budget[0] += 1
			if budget[0] > MAX_FILES: return "Source manifest exceeds 20000 project files."
			if uri == "res://project.godot" or uri.get_extension() in EXTENSIONS:
				var file := FileAccess.open(uri, FileAccess.READ)
				if not file: return "Cannot read source manifest file: " + uri
				budget[1] += file.get_length()
				file.close()
				if budget[1] > MAX_BYTES: return "Source manifest exceeds 512 MiB."
				var digest: String = FileAccess.get_sha256(uri)
				if digest.is_empty(): return "Cannot hash source manifest file: " + uri
				files[uri] = digest
		name = directory.get_next()
	directory.list_dir_end()
	return ""

static func differences(before: Dictionary, after: Dictionary) -> Array:
	var changed: Array = []
	for uri: String in before:
		if before[uri] != after.get(uri): changed.append(uri)
	for uri: String in after:
		if not before.has(uri): changed.append(uri)
	changed.sort()
	return changed

static func startup() -> Dictionary:
	var request: Variant = JSON.parse_string(FileAccess.get_file_as_string(REQUEST)) if FileAccess.file_exists(REQUEST) else null
	if not request is Dictionary: return {"state": "unverified", "reason": "No editor source manifest request."}
	var observed: Dictionary = capture()
	return {"run_id": request.get("run_id", ""), "token": request.get("token", ""), "observed": observed}
