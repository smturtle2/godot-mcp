extends RefCounted
## Shared, bounded provenance for editor-launched games. File identity is not
## evidence that every file was loaded or that a behavior was executed.
const EXCLUDED := [".git", ".godot", ".godot-mcp", ".venv", ".pytest_cache", ".ruff_cache"]
const REQUEST := "res://.godot-mcp/run-source-request.json"
const SCOPE := "launch scene, autoloads and declared resource dependencies; dynamic loads are not exhaustive"
const MAX_FILES := 20000
const MAX_BYTES := 512 * 1024 * 1024

static func resolve(value: String) -> String:
	var parts: PackedStringArray = value.trim_prefix("*").split("::")
	if parts[0].begins_with("uid://"):
		var id: int = ResourceUID.text_to_id(parts[0])
		return ResourceUID.get_id_path(id) if ResourceUID.has_id(id) else (parts[2] if parts.size() > 2 else "")
	return parts[0]

static func run_roots(scene: String) -> Array:
	var roots: Array = ["res://project.godot", resolve(scene)]
	for setting: Dictionary in ProjectSettings.get_property_list():
		if str(setting.name).begins_with("autoload/"): roots.append(resolve(str(ProjectSettings.get_setting(setting.name))))
	return roots

static func capture(paths: Array = [], expand: bool = true) -> Dictionary:
	var files: Dictionary = {}
	var skipped: Array = []
	var pending: Array = paths.duplicate() if not paths.is_empty() else run_roots(str(ProjectSettings.get_setting("application/run/main_scene", "")))
	var seen: Dictionary = {}
	var bytes: int = 0
	var message: String = ""
	while not pending.is_empty():
		var uri: String = resolve(str(pending.pop_back()))
		if seen.has(uri) or uri.is_empty(): continue
		seen[uri] = true
		if seen.size() > MAX_FILES:
			message = "Run dependency snapshot exceeds 20000 files."
			break
		var safe: bool = uri.begins_with("res://") and ".." not in uri.trim_prefix("res://").split("/")
		var directory: String = "res://"
		for part: String in uri.trim_prefix("res://").split("/"):
			var access := DirAccess.open(directory)
			if part in EXCLUDED or (access and access.is_link(part)): safe = false
			directory = directory.path_join(part)
		var file: FileAccess = FileAccess.open(uri, FileAccess.READ) if safe else null
		if not file:
			skipped.append(uri)
			continue
		bytes += file.get_length()
		file.close()
		if bytes > MAX_BYTES:
			message = "Run dependency snapshot exceeds 512 MiB."
			break
		files[uri] = FileAccess.get_sha256(uri)
		if str(files[uri]).is_empty(): skipped.append(uri)
		if expand and ResourceLoader.exists(uri):
			for dependency: String in ResourceLoader.get_dependencies(uri): pending.append(resolve(dependency))
	var sorted: Dictionary = {}
	var ordered: Array = files.keys()
	ordered.sort()
	for uri: String in ordered: sorted[uri] = files[uri]
	skipped.sort()
	return {"files": sorted, "snapshot_id": JSON.stringify(sorted).sha256_text(), "scope": SCOPE, "complete": message.is_empty() and skipped.is_empty(), "skipped_paths": skipped, "reason": message}

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
	var observed: Dictionary = capture(request.get("paths", []), false)
	return {"run_id": request.get("run_id", ""), "token": request.get("token", ""), "observed": observed}
