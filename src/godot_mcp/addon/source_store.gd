@tool
extends RefCounted
## One revision baseline for editor buffers, MCP drafts, validation and persistence.
var host: EditorPlugin
var states: Dictionary = {}
var buffers: Dictionary = {}
var observing: bool = false
var writing: bool = false
var staging: bool = false
var stopped: bool = false
const MAX_BASE_VERSIONS := 256
const MAX_BASE_BYTES := 16 * 1024 * 1024
const MAX_SOURCE_BYTES := 1000000
var bases: Dictionary = {}
var base_bytes: int = 0

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host
	var editor := EditorInterface.get_script_editor()
	editor.editor_script_changed.connect(_active_script_changed)
	editor.script_close.connect(_script_closing)
	observe_open_buffers.call_deferred()

func shutdown() -> void:
	stopped = true
	var editor := EditorInterface.get_script_editor()
	if editor.editor_script_changed.is_connected(_active_script_changed): editor.editor_script_changed.disconnect(_active_script_changed)
	if editor.script_close.is_connected(_script_closing): editor.script_close.disconnect(_script_closing)
	for uri: String in buffers.keys(): _forget_buffer(uri)

func _cached_buffer(uri: String) -> TextEdit:
	if not buffers.has(uri): return null
	return buffers[uri].ref.get_ref() as TextEdit

func _forget_buffer(uri: String) -> void:
	var buffer: TextEdit = _cached_buffer(uri)
	if buffer and buffer.text_changed.is_connected(buffers[uri].changed):
		buffer.text_changed.disconnect(buffers[uri].changed)
	buffers.erase(uri)

func _active_script_changed(script: Script) -> void:
	if stopped or observing or not script: return
	var editor := EditorInterface.get_script_editor()
	var base: ScriptEditorBase = editor.get_current_editor()
	if base and editor.get_current_script() == script:
		var buffer: TextEdit = base.get_base_editor() as TextEdit
		if buffer: _track_buffer(script.resource_path, buffer)
	else:
		observe_open_buffers.call_deferred()

func _script_closing(script: Script) -> void:
	if not stopped and script: _after_close.call_deferred(script.resource_path)

func _after_close(uri: String) -> void:
	if stopped: return
	for script: Script in EditorInterface.get_script_editor().get_open_scripts():
		if script.resource_path == uri: return
	_forget_buffer(uri)
	# Closing the editor discards or saves its buffer. Never resurrect discarded
	# text from the observer's last copy on a later read.
	if states.has(uri) and states[uri].get("origin") == "editor": states.erase(uri)

func observe_open_buffers() -> void:
	if stopped or observing: return
	observing = true
	for script: Script in EditorInterface.get_script_editor().get_open_scripts():
		if script.resource_path.ends_with(".gd"): script_buffer(script.resource_path)
	observing = false

func script_buffer(uri: String) -> TextEdit:
	var cached: TextEdit = _cached_buffer(uri)
	if cached:
		_record_buffer_version(uri, cached)
		return cached
	var editor := EditorInterface.get_script_editor()
	var script: Script
	for candidate: Script in editor.get_open_scripts():
		if candidate.resource_path == uri:
			script = candidate
			break
	if not script: return null
	var previous: Script = editor.get_current_script()
	var was_observing: bool = observing
	observing = true
	if previous != script: EditorInterface.edit_script(script, -1, 0, false)
	var base: ScriptEditorBase = editor.get_current_editor()
	var text: TextEdit = base.get_base_editor() as TextEdit if base and editor.get_current_script() == script else null
	if text: _track_buffer(uri, text)
	if previous and previous != script: EditorInterface.edit_script(previous, -1, 0, false)
	observing = was_observing
	return text

func _disk(uri: String) -> Dictionary:
	var exists: bool = FileAccess.file_exists(uri)
	var source: String = FileAccess.get_file_as_string(uri) if exists else ""
	return {"exists": exists, "source": source, "revision": source.sha256_text() if exists else null}

func _remember(uri: String, source: String, revision: String) -> bool:
	var key: String = uri + "\n" + revision
	if bases.has(key): return true
	var bytes: int = source.to_utf8_buffer().size()
	if bytes > MAX_SOURCE_BYTES: return false
	while not bases.is_empty() and (bases.size() >= MAX_BASE_VERSIONS or base_bytes + bytes > MAX_BASE_BYTES):
		var oldest: String = bases.keys()[0]
		base_bytes -= int(bases[oldest].bytes)
		bases.erase(oldest)
	bases[key] = {"source": source, "bytes": bytes}
	base_bytes += bytes
	return true

func base_source(uri: String, revision: String) -> Dictionary:
	var key: String = uri + "\n" + revision
	if not bases.has(key):
		return host.fail("BASE_REVISION_EXPIRED", "The original source is no longer retained. Read current source and make a fresh patch.", {"uri": uri, "base_revision": revision})
	return {"source": bases[key].source, "revision": revision}

func _track_buffer(uri: String, buffer: TextEdit) -> void:
	if not uri.begins_with("res://") or not uri.ends_with(".gd"): return
	if _cached_buffer(uri) == buffer:
		_record_buffer_version(uri, buffer)
		return
	_forget_buffer(uri)
	var revision: String = buffer.text.sha256_text()
	var disk: Dictionary = _disk(uri)
	if not states.has(uri):
		# A saved version is useful only when its contents were observed. An
		# already-dirty buffer does not reveal what its saved version contained.
		var known: bool = revision == disk.revision or buffer.get_version() == buffer.get_saved_version()
		states[uri] = {"source": buffer.text, "base_disk_revision": revision if known else null, "base_known": known, "dirty": revision != disk.revision, "origin": "editor"}
	var changed: Callable = _buffer_changed.bind(uri)
	buffers[uri] = {"ref": weakref(buffer), "revisions": {buffer.get_version(): revision}, "saved_version": buffer.get_saved_version(), "changed": changed}
	buffer.text_changed.connect(changed)
	_record_buffer_version(uri, buffer)

func _record_buffer_version(uri: String, buffer: TextEdit) -> void:
	if not buffers.has(uri): return
	var record: Dictionary = buffers[uri]
	var revision: String = buffer.text.sha256_text()
	var version: int = buffer.get_version()
	var saved_version: int = buffer.get_saved_version()
	record.revisions[version] = revision
	if saved_version != record.saved_version and states.has(uri):
		# UI save/reload/undo may retag the saved version without a text signal.
		# Use that version's observed content, never the current disk as its past.
		states[uri].base_known = record.revisions.has(saved_version)
		states[uri].base_disk_revision = record.revisions.get(saved_version)
		record.saved_version = saved_version
	while record.revisions.size() > 256:
		var removed: bool = false
		for old: int in record.revisions.keys():
			if old != version and old != saved_version:
				record.revisions.erase(old)
				removed = true
				break
		if not removed: break

func _buffer_changed(uri: String) -> void:
	var buffer: TextEdit = _cached_buffer(uri)
	if not buffer: return
	_record_buffer_version(uri, buffer)
	if writing or not states.has(uri): return
	states[uri].pending_publication = false
	states[uri].source = buffer.text
	states[uri].origin = "editor"
	states[uri].dirty = not states[uri].base_known or buffer.text.sha256_text() != states[uri].base_disk_revision

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
	var disk: Dictionary = _disk(uri)
	if not disk.exists and not states.has(uri): return host.fail("FILE_NOT_FOUND", "Source file does not exist.")
	var source: String = disk.source
	var buffer: TextEdit = script_buffer(uri) if uri.ends_with(".gd") else null
	var resource: Resource = host.resource_uri(uri)
	var origin: String = "disk"
	if states.get(uri, {}).get("pending_publication", false):
		source = str(states[uri].source)
		origin = "store"
	elif buffer:
		source = buffer.text
		origin = "editor"
	elif states.has(uri) and states[uri].get("dirty", false):
		source = str(states[uri].source)
		origin = "store"
	elif resource is Script and not disk.exists:
		source = resource.source_code
		origin = "resource"
	elif resource is Shader:
		source = resource.code
		origin = "resource" if source != disk.source else "disk"
	var revision: String = source.sha256_text()
	if not states.has(uri):
		states[uri] = {"base_known": origin == "disk" or revision == disk.revision, "base_disk_revision": disk.revision, "source": source, "dirty": false}
	var state: Dictionary = states[uri]
	if disk.exists and revision == disk.revision:
		state.base_known = true
		state.base_disk_revision = disk.revision
	state.source = source
	state.origin = origin
	state.dirty = not disk.exists or revision != disk.revision
	var conflict: String = "baseline_unknown" if not state.base_known else ("external_change" if state.base_disk_revision != disk.revision else "none")
	return {"uri": uri, "source": source, "revision": revision, "disk_revision": disk.revision, "base_disk_revision": state.base_disk_revision if state.base_known else null, "baseline_known": state.base_known, "exists_on_disk": disk.exists, "unsaved": state.dirty, "buffer": origin, "external_change": conflict != "none", "conflict": conflict, "base_retained": _remember(uri, source, revision)}

func set_source(uri: String, source: String, resource: Resource = null) -> void:
	var disk: Dictionary = _disk(uri)
	if disk.exists or states.has(uri): source_info(uri)
	if not states.has(uri): states[uri] = {"base_known": true, "base_disk_revision": disk.revision}
	if not resource: resource = ensure_resource(uri, true)
	if resource:
		resource.resource_path = uri
		host.register_resource(resource)
	if staging:
		states[uri].source = source
		states[uri].dirty = not disk.exists or source != disk.source
		states[uri].origin = "store"
		states[uri].pending_publication = true
		return
	states[uri].pending_publication = false
	var buffer: TextEdit = script_buffer(uri) if resource is Script else null
	writing = true
	if resource is Script:
		if buffer and buffer.text != source:
			buffer.begin_complex_operation()
			buffer.select_all()
			buffer.insert_text_at_caret(source)
			buffer.deselect()
			buffer.end_complex_operation()
		resource.source_code = source
	elif resource is Shader: resource.code = source
	writing = false
	var state: Dictionary = states[uri]
	state.source = source
	state.dirty = not disk.exists or source != disk.source
	state.origin = "editor" if buffer else "store"
	if disk.exists and source == disk.source:
		state.base_known = true
		state.base_disk_revision = disk.revision
	if buffer: _record_buffer_version(uri, buffer)
	if resource: EditorInterface.set_object_edited(resource, state.dirty)

func publish_sources(uris: Array) -> void:
	var pending: Dictionary = {}
	for uri: String in uris:
		var info: Dictionary = source_info(uri)
		if info.has("error"): continue
		pending[uri] = info.source
	for uri: String in pending:
		var resource: Resource = host.resources.get(uri)
		# Populate every GDScript before a buffer notification can parse a peer.
		if resource is Script: resource.source_code = pending[uri]
	for uri: String in pending: set_source(uri, pending[uri], host.resources.get(uri))

func has_pending_sources(uris: Array) -> bool:
	for uri: String in uris:
		if states.get(uri, {}).get("pending_publication", false): return true
	return false

func source_matches(uri: String, revision: String) -> bool:
	var info: Dictionary = source_info(uri)
	return not info.has("error") and not info.external_change and info.revision == revision

func mark_saved(uri: String) -> void:
	var info: Dictionary = source_info(uri)
	if info.has("error") or info.unsaved: return
	states[uri].base_known = true
	states[uri].base_disk_revision = info.disk_revision
	states[uri].dirty = false
	var buffer: TextEdit = script_buffer(uri) if uri.ends_with(".gd") else null
	if buffer:
		buffer.tag_saved_version()
		_record_buffer_version(uri, buffer)
	var resource: Resource = host.resource_uri(uri)
	if resource: EditorInterface.set_object_edited(resource, false)

func overlays() -> Dictionary:
	observe_open_buffers()
	var result: Dictionary = {}
	for uri: String in states.keys():
		var info: Dictionary = source_info(uri)
		if not info.has("error") and info.unsaved: result[uri] = info.source
	return result

func conflicts(uris: Array = []) -> Array:
	observe_open_buffers()
	var result: Array = []
	var targets: Array = states.keys() if uris.is_empty() else uris
	for uri: String in targets:
		var info: Dictionary = source_info(uri)
		if not info.has("error") and info.external_change:
			result.append({"uri": uri, "code": "BASELINE_UNKNOWN" if not info.baseline_known else "EXTERNAL_CHANGE", "base_disk_revision": info.base_disk_revision, "disk_revision": info.disk_revision, "revision": info.revision})
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
	_forget_buffer(from)
	if states.has(from):
		states[to] = states[from]
		states.erase(from)

func remove_state(uri: String) -> void:
	_forget_buffer(uri)
	states.erase(uri)
	for key: String in bases.keys():
		if key.begins_with(uri + "\n"):
			base_bytes -= int(bases[key].bytes)
			bases.erase(key)

func dirty_uris() -> Array[String]:
	var result: Array[String] = []
	for uri: String in overlays(): result.append(uri)
	return result
