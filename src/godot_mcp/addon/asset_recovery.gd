@tool
extends RefCounted
## Durable deletion intent plus moved bytes. Recovery is derived from the disk, not a completed RPC.
const ROOT := "res://.godot-mcp/deletions"
var host: EditorPlugin

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host

func valid_id(id: String) -> bool:
	return id.begins_with("deletion-") and id.trim_prefix("deletion-").length() == 32 and id.trim_prefix("deletion-").is_valid_hex_number()

func directory(id: String) -> String:
	return ROOT.path_join(id)

func blob(id: String, uri: String) -> String:
	return directory(id).path_join("files").path_join(uri.sha256_text())

func safe(id: String) -> bool:
	return valid_id(id) and host.paths_safe(directory(id))

func save(record: Dictionary) -> Error:
	var id: String = record.deletion_id
	if not safe(id): return ERR_INVALID_PARAMETER
	var path: String = directory(id).path_join("manifest.json")
	if not host.paths_safe(path) or not host.paths_safe(path + ".tmp"): return ERR_INVALID_PARAMETER
	var error: Error = DirAccess.make_dir_recursive_absolute(directory(id))
	if error != OK: return error
	var file := FileAccess.open(path + ".tmp", FileAccess.WRITE)
	if not file: return FileAccess.get_open_error()
	file.store_string(JSON.stringify(record))
	file.flush()
	error = file.get_error()
	file.close()
	if error != OK: return error
	return DirAccess.rename_absolute(path + ".tmp", path)

func create(plan: Dictionary) -> Dictionary:
	var id: String = "deletion-" + Crypto.new().generate_random_bytes(16).hex_encode()
	var record: Dictionary = {"format": 1, "deletion_id": id, "created_at": Time.get_datetime_string_from_system(true), "mode": plan.options.mode, "state": "deleting", "roots": plan.options.paths, "entries": plan.entries.duplicate(true)}
	# Permanent mode retains only intent and hashes, never a source recovery copy.
	if record.mode == "permanent":
		for entry: Dictionary in record.entries: entry.erase("source")
	var error: Error = DirAccess.make_dir_recursive_absolute(directory(id).path_join("files")) if safe(id) else ERR_INVALID_PARAMETER
	if error == OK: error = save(record)
	if error != OK: return host.fail("RECOVERY_RECORD_FAILED", "Cannot persist deletion intent; no project asset was removed.", {"error": error_string(error)})
	return record

func read_record(id: String) -> Dictionary:
	if not safe(id): return host.fail("INVALID_DELETION_ID", "Use a deletion_id returned by delete_assets or get_context.")
	var path: String = directory(id).path_join("manifest.json")
	if not host.paths_safe(path): return host.fail("INVALID_PATH", "Deletion metadata contains a symlink.")
	if not FileAccess.file_exists(path): return host.fail("DELETION_NOT_FOUND", "This deletion record is unavailable or has been purged.", {"deletion_id": id})
	var record: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not record is Dictionary or record.get("format") != 1 or record.get("deletion_id") != id or record.get("mode") not in ["recoverable", "permanent"] or not record.get("state") is String or not record.get("roots") is Array or not record.get("entries") is Array:
		return host.fail("RECOVERY_RECORD_INVALID", "Deletion metadata is unreadable; no asset was changed.", {"deletion_id": id})
	for entry: Variant in record.entries:
		if not entry is Dictionary or not entry.get("uri") is String or not entry.get("kind") in ["file", "draft", "directory"]:
			return host.fail("RECOVERY_RECORD_INVALID", "Invalid deletion entry.", {"deletion_id": id})
		if entry.kind == "file" and (not entry.get("sha256") is String or str(entry.sha256).length() != 64): return host.fail("RECOVERY_RECORD_INVALID", "Invalid file recovery hash.", {"deletion_id": id})
	return record

func available(record: Dictionary, entry: Dictionary) -> bool:
	if record.mode != "recoverable": return false
	if entry.kind == "file": return host.paths_safe(blob(record.deletion_id, entry.uri)) and FileAccess.file_exists(blob(record.deletion_id, entry.uri))
	if entry.kind == "directory" and record.state == "deleting": return not DirAccess.dir_exists_absolute(entry.uri)
	return entry.get("removed", false) and not entry.get("restored", false)

func summary(record: Dictionary) -> Dictionary:
	var paths: Array = []
	var retained_sources: Array = []
	for entry: Dictionary in record.entries:
		if available(record, entry): paths.append(entry.uri)
		if entry.has("source"): retained_sources.append(entry.uri)
	return {"deletion_id": record.deletion_id, "mode": record.mode, "state": record.state, "created_at": record.get("created_at", ""), "paths": paths, "retained_sources": retained_sources, "recoverable": not paths.is_empty()}

func list_records() -> Array:
	var result: Array = []
	if not host.paths_safe(ROOT): return [{"state": "unavailable", "reason": "Recovery directory contains a symlink."}]
	var dir := DirAccess.open(ROOT)
	if not dir: return result
	for id: String in dir.get_directories():
		if not valid_id(id) or dir.is_link(id): continue
		var record: Dictionary = read_record(id)
		if record.has("error"):
			result.append({"deletion_id": id, "state": "unavailable", "reason": record.error.message})
		else:
			var item: Dictionary = summary(record)
			if record.mode == "recoverable" or record.state in ["deleting", "partial", "purging"]: result.append(item)
	return result

func signature(record: Dictionary) -> Dictionary:
	var hashes: Dictionary = {"manifest": FileAccess.get_sha256(directory(record.deletion_id).path_join("manifest.json"))}
	for entry: Dictionary in record.entries:
		if entry.kind != "file": continue
		var path: String = blob(record.deletion_id, entry.uri)
		if not host.paths_safe(path): return host.fail("INVALID_PATH", "Recovery copy contains a symlink.")
		hashes[entry.uri] = FileAccess.get_sha256(path) if FileAccess.file_exists(path) else null
	return hashes
