@tool
extends RefCounted
## Live source buffers and draft resources shared by document operations.
var host: EditorPlugin
var states: Dictionary = {}

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host

func script_buffer(uri: String) -> TextEdit:
	var editor := EditorInterface.get_script_editor()
	var script: Script
	for candidate: Script in editor.get_open_scripts():
		if candidate.resource_path == uri:
			script = candidate
			break
	if not script: return null
	var previous: Script = editor.get_current_script()
	if previous != script: EditorInterface.edit_script(script, -1, 0, false)
	var base: ScriptEditorBase = editor.get_current_editor()
	var text: TextEdit = base.get_base_editor() as TextEdit if base and editor.get_current_script() == script else null
	if previous and previous != script: EditorInterface.edit_script(previous, -1, 0, false)
	return text

func _disk_source(uri: String) -> String:
	return FileAccess.get_file_as_string(uri) if FileAccess.file_exists(uri) else ""

func _disk_revision(uri: String) -> Variant:
	return _disk_source(uri).sha256_text() if FileAccess.file_exists(uri) else null

func ensure_resource(uri: String, create: bool = false) -> Resource:
	var resource: Resource = host.resource_uri(uri)
	if resource or not create: return resource
	if not uri.begins_with("res://") or uri.get_extension() not in ["gd", "gdshader"]: return null
	resource = GDScript.new() if uri.ends_with(".gd") else Shader.new()
	resource.resource_path = uri
	host.register_resource(resource)
	return resource

func source_info(uri: String) -> Dictionary:
	if not uri.begins_with("res://") or uri.get_extension() not in ["gd", "gdshader"]:
		return host.fail("UNSUPPORTED_LANGUAGE", "Use a .gd or .gdshader project file.")
	var exists_on_disk: bool = FileAccess.file_exists(uri)
	if not exists_on_disk and not states.has(uri):
		return host.fail("FILE_NOT_FOUND", "Source file does not exist.")
	var disk: String = _disk_source(uri)
	var source: String = disk
	var buffer: TextEdit = script_buffer(uri) if uri.ends_with(".gd") else null
	var resource: Resource = host.resource_uri(uri)
	var source_kind: String = "disk"
	if buffer:
		source = buffer.text
		source_kind = "editor"
	elif states.has(uri) and states[uri].get("dirty", false):
		source = str(states[uri].get("source", ""))
		source_kind = "store"
	elif resource is Script and not exists_on_disk:
		source = resource.source_code
		source_kind = "resource"
	elif resource is Shader:
		source = resource.code
		source_kind = "resource" if source != disk else "disk"
	var disk_revision: Variant = _disk_revision(uri)
	var current_revision: String = source.sha256_text()
	var external_change: bool = false
	# Saving a scene can also persist its external script. Reconcile a matching
	# disk/source pair before checking conflicts or reporting pending saves.
	if exists_on_disk and source == disk and states.has(uri):
		states[uri] = {"source": source, "disk_revision": disk_revision, "dirty": false}
	if states.has(uri) and states[uri].get("dirty", false) :
		external_change = states[uri].get("disk_revision", disk_revision) != disk_revision
	return {"uri": uri, "source": source, "revision": current_revision, "disk_revision": disk_revision, "exists_on_disk": exists_on_disk, "unsaved": not exists_on_disk or source != disk, "buffer": source_kind, "external_change": external_change}

func set_source(uri: String, source: String, resource: Resource = null) -> void:
	var disk: String = _disk_source(uri)
	if not resource: resource = ensure_resource(uri, true)
	if resource:
		resource.resource_path = uri
		host.register_resource(resource)
	if resource is Script:
		var buffer: TextEdit = script_buffer(uri)
		if buffer and buffer.text != source:
			buffer.begin_complex_operation()
			buffer.select_all()
			buffer.insert_text_at_caret(source)
			buffer.deselect()
			buffer.end_complex_operation()
		resource.source_code = source
	elif resource is Shader:
		resource.code = source
	var disk_revision: Variant = states[uri].disk_revision if states.has(uri) and states[uri].dirty else _disk_revision(uri)
	var dirty: bool = not FileAccess.file_exists(uri) or source != disk
	states[uri] = {"source": source, "disk_revision": disk_revision, "dirty": dirty}
	if resource:
		EditorInterface.set_object_edited(resource, dirty)

func source_matches(uri: String, revision: String) -> bool:
	var info: Dictionary = source_info(uri)
	return not info.has("error") and not info.external_change and info.revision == revision

func mark_saved(uri: String) -> void:
	var info: Dictionary = source_info(uri)
	if info.has("error"): return
	var source: String = _disk_source(uri) if FileAccess.file_exists(uri) else str(info.source)
	states[uri] = {"source": source, "disk_revision": _disk_revision(uri), "dirty": false}
	var buffer: TextEdit = script_buffer(uri) if uri.ends_with(".gd") else null
	if buffer: buffer.tag_saved_version()
	var resource: Resource = host.resource_uri(uri)
	if resource: EditorInterface.set_object_edited(resource, false)

func overlays() -> Dictionary:
	var result: Dictionary = {}
	for uri: String in states:
		if states[uri].get("dirty", false): result[uri] = str(states[uri].get("source", ""))
	var editor := EditorInterface.get_script_editor()
	for script: Script in editor.get_open_scripts():
		var uri: String = script.resource_path
		var buffer: TextEdit = script_buffer(uri)
		if buffer and buffer.text != _disk_source(uri): result[uri] = buffer.text
	return result

func restore_source(uri: String, before: Variant) -> void:
	if before is String:
		set_source(uri, str(before))
		var resource: Resource = host.resources.get(uri)
		if resource is Script: resource.reload(true)
		return
	if not FileAccess.file_exists(uri):
		var resource: Resource = host.resources.get(uri)
		if resource: resource.resource_path = ""
		states.erase(uri)
		host.resources.erase(uri)
		return
	set_source(uri, FileAccess.get_file_as_string(uri))
	mark_saved(uri)

func move_state(from: String, to: String) -> void:
	if states.has(from):
		states[to] = states[from]
		states.erase(from)

func dirty_uris() -> Array[String]:
	var result: Array[String] = []
	for uri: String in states:
		if states[uri].get("dirty", false): result.append(uri)
	return result
