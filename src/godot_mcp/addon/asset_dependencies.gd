@tool
extends RefCounted
## The same dependency resolution is used by resource inspection and deletion plans.
const MAX_FILES := 20000
const TEXT_EXTENSIONS := ["gd", "gdshader", "tscn", "tres", "godot", "cfg", "import", "json", "cs"]
var host: EditorPlugin

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host

func resolve(value: String, owner: String = "") -> String:
	var parts: PackedStringArray = value.trim_prefix("*").split("::")
	var first: String = parts[0]
	if first.begins_with("uid://"):
		var uid: int = ResourceUID.text_to_id(first)
		if uid != ResourceUID.INVALID_ID and ResourceUID.has_id(uid): return ResourceUID.get_id_path(uid)
		return parts[2] if parts.size() > 2 else ""
	if first.begins_with("res://"): return first.simplify_path()
	if not owner.is_empty() and not first.contains("://"):
		return owner.get_base_dir().path_join(first).simplify_path()
	return ""

func project_files() -> Dictionary:
	var pending: Array[String] = ["res://"]
	var files: Array[String] = []
	while not pending.is_empty():
		var path: String = pending.pop_back()
		var dir := DirAccess.open(path)
		if not dir: return host.fail("REFERENCE_SCAN_FAILED", "Cannot inspect project directory.", {"uri": path})
		for name: String in dir.get_directories():
			if name.begins_with(".") or dir.is_link(name): continue
			pending.append(path.path_join(name))
		for name: String in dir.get_files():
			if name.begins_with(".") or dir.is_link(name): continue
			files.append(path.path_join(name))
			if files.size() > MAX_FILES: return host.fail("LIMIT_EXCEEDED", "Reference discovery is limited to 20000 project files; narrow the project before deletion.")
	files.sort()
	return {"files": files}

func _add(refs: Array, owner: String, target: String, kind: String, detail: String, revision: String = "") -> void:
	var item: Dictionary = {"owner": owner, "target": target, "kind": kind, "detail": detail, "confidence": "candidate" if kind.ends_with("literal") else "confirmed", "owner_revision": revision}
	if item not in refs: refs.append(item)

func _values(value: Variant, owner: String, targets: Dictionary, refs: Array, kind: String, detail: String, seen: Dictionary, depth: int = 0) -> void:
	if depth > 16: return
	if value is Resource:
		var path: String = value.resource_path.get_slice("::", 0)
		if targets.has(path) and path != owner: _add(refs, owner, path, kind, detail)
		var id: int = value.get_instance_id()
		if seen.has(id): return
		seen[id] = true
		for prop: Dictionary in value.get_property_list():
			if int(prop.usage) & PROPERTY_USAGE_STORAGE: _values(value.get(prop.name), owner, targets, refs, kind, detail, seen, depth + 1)
	elif value is String or value is StringName:
		var path: String = resolve(str(value), owner)
		if targets.has(path): _add(refs, owner, path, kind + "_literal", detail)
	elif value is Array or value is PackedStringArray:
		for item: Variant in value: _values(item, owner, targets, refs, kind, detail, seen, depth + 1)
	elif value is Dictionary:
		for key: Variant in value:
			_values(key, owner, targets, refs, kind, detail, seen, depth + 1)
			_values(value[key], owner, targets, refs, kind, detail, seen, depth + 1)

func inspect(targets: Dictionary) -> Dictionary:
	var inventory: Dictionary = project_files()
	if inventory.has("error"): return inventory
	var refs: Array = []
	var overlays: Dictionary = host.documents.store.overlays()
	var literals := RegEx.new()
	literals.compile("[\"']([^\"'\\n]+)[\"']")
	var recognized: PackedStringArray = ResourceLoader.get_recognized_extensions_for_type("Resource")
	var skipped: Array = []
	for owner: String in inventory.files:
		if targets.has(owner): continue
		var revision: String = ""
		if owner.get_extension() in recognized and not overlays.has(owner):
			var dependencies: PackedStringArray = ResourceLoader.get_dependencies(owner)
			for dependency: String in dependencies:
				var target: String = resolve(dependency)
				if targets.has(target):
					if revision.is_empty(): revision = FileAccess.get_sha256(owner)
					_add(refs, owner, target, "dependency", dependency, revision)
		if owner.get_extension() in TEXT_EXTENSIONS:
			var file := FileAccess.open(owner, FileAccess.READ)
			if not file: return host.fail("REFERENCE_SCAN_FAILED", "Cannot read a possible reference owner.", {"uri": owner})
			if file.get_length() > 4 * 1024 * 1024:
				skipped.append(owner)
				continue
			var source: String = str(overlays.get(owner, file.get_as_text()))
			revision = source.sha256_text()
			for literal: RegExMatch in literals.search_all(source):
				var target: String = resolve(literal.get_string(1), owner)
				if targets.has(target): _add(refs, owner, target, "source_literal" if overlays.has(owner) else "file_literal", literal.get_string(1), revision)
	# Draft owners are absent from the disk inventory.
	for owner: String in overlays:
		if targets.has(owner) or owner in inventory.files: continue
		for literal: RegExMatch in literals.search_all(str(overlays[owner])):
			var target: String = resolve(literal.get_string(1), owner)
			if targets.has(target): _add(refs, owner, target, "source_literal", literal.get_string(1), str(overlays[owner]).sha256_text())
	var affected_scenes: Array = []
	var histories: Dictionary = {}
	for root: Node in EditorInterface.get_open_scene_roots():
		var owner: String = root.scene_file_path if not root.scene_file_path.is_empty() else "godot://unsaved-scenes/" + str(root.get_instance_id())
		var before: int = refs.size()
		if not targets.has(owner):
			var nodes: Array[Node] = [root]
			while not nodes.is_empty():
				var node: Node = nodes.pop_back()
				for child: Node in node.get_children(): nodes.append(child)
				for prop: Dictionary in node.get_property_list():
					if int(prop.usage) & PROPERTY_USAGE_STORAGE:
						_values(node.get(prop.name), owner, targets, refs, "open_scene", str(root.get_path_to(node)) + ":" + str(prop.name), {})
		if targets.has(owner) or refs.size() != before:
			affected_scenes.append(owner)
			var history := host.get_undo_redo().get_history_undo_redo(host.get_undo_redo().get_object_history_id(root))
			histories[owner] = history.get_version() if history else 0
	for prop: Dictionary in ProjectSettings.get_property_list():
		if int(prop.usage) & PROPERTY_USAGE_STORAGE:
			_values(ProjectSettings.get_setting(prop.name), "res://project.godot", targets, refs, "setting", str(prop.name), {})
	var cached: Dictionary = host.resources.duplicate()
	for path: String in inventory.files:
		if ResourceLoader.has_cached(path): cached[path] = ResourceLoader.get_cached_ref(path)
	var dirty: Array = []
	for owner: String in cached:
		var resource: Resource = cached[owner]
		if not resource: continue
		var before: int = refs.size()
		if not targets.has(owner): _values(resource, owner, targets, refs, "cached_resource", resource.get_class(), {})
		if (targets.has(owner) or refs.size() != before) and EditorInterface.is_object_edited(resource): dirty.append(owner)
	var settings: Dictionary = host.assets.settings_snapshot()
	if settings.has("error"): return settings
	for ref: Dictionary in refs:
		if ref.owner == "res://project.godot": ref.owner_revision = str(settings.revision)
	refs.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return JSON.stringify(a) < JSON.stringify(b))
	affected_scenes.sort()
	dirty.sort()
	return {"references": refs, "affected_scenes": affected_scenes, "scene_histories": histories, "dirty_resources": dirty, "settings_unsaved": not settings.saved, "coverage": {"saved_dependencies": "ResourceLoader dependencies resolved by UID with path fallback", "literals": "Quoted paths in current source buffers and authored text files", "live": "Open scene properties, known cached resources, and current project settings (nested depth 16)", "excluded": ["Dynamically assembled paths", "Hidden directories and symlinks", "References outside this project"], "skipped_large_text_files": skipped}}
