@tool
extends RefCounted
## Before/after images remain owned until the importer is quiet and undo is registered.
var before: Dictionary
var after: Dictionary = {}
var paths: Array
var finalized: bool = false

func _init(owned_paths: Array) -> void:
	paths = owned_paths.duplicate()
	before = snapshot(paths)

static func snapshot(owned_paths: Array) -> Dictionary:
	var files: Dictionary = {}
	for path: String in owned_paths:
		files[path] = FileAccess.get_file_as_bytes(path) if FileAccess.file_exists(path) else null
	return files

static func matches(files: Dictionary) -> bool:
	for path: String in files:
		if files[path] == null:
			if FileAccess.file_exists(path): return false
		elif not FileAccess.file_exists(path) or FileAccess.get_file_as_bytes(path) != files[path]: return false
	return true

func changed_paths() -> Array:
	var current: Dictionary = after if finalized else snapshot(paths)
	var changed: Array = []
	for path: String in paths:
		if before.get(path) != current.get(path): changed.append(path)
	return changed

func finalize() -> void:
	after = snapshot(paths)
	finalized = true
