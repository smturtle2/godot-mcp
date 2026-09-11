@tool
extends RefCounted
## Discovery and search use one live-source store, including never-saved drafts.
const MAX_FILES := 20000
const MAX_ENTRIES := 40000
const MAX_TEXT_BYTES := 2 * 1024 * 1024
const TEXT_EXTENSIONS := ["gd", "gdshader", "tscn", "tres", "godot", "cfg", "txt", "json"]
var host: EditorPlugin
var store: RefCounted

func _excluded_component(name: String) -> bool:
	return name.begins_with(".")

func _init(editor_host: EditorPlugin, source_store: RefCounted) -> void:
	host = editor_host
	store = source_store

func _in_scope(uri: String, scope: String) -> bool:
	return uri == scope or uri.begins_with(scope.trim_suffix("/") + "/")

func _catalog(scope: String, recursive: bool = true, include_overlays: bool = true) -> Dictionary:
	if not scope.begins_with("res://") or not host.paths_safe(scope): return host.fail("INVALID_PATH", "Search scope must remain in the project.")
	var candidates: Dictionary = {}
	var directories: Dictionary = {}
	var pending: Array[String] = [scope]
	var skipped: Array = []
	var complete: bool = true
	var entries: int = 0
	while not pending.is_empty():
		var path: String = pending.pop_back()
		if not DirAccess.dir_exists_absolute(path):
			if FileAccess.file_exists(path): candidates[path] = true
			if candidates.size() >= MAX_FILES:
				complete = pending.is_empty()
				break
			continue
		var directory := DirAccess.open(path)
		if not directory:
			skipped.append(path)
			complete = false
			continue
		directory.list_dir_begin()
		var name: String = directory.get_next()
		while not name.is_empty():
			entries += 1
			if entries > MAX_ENTRIES:
				complete = false
				break
			if directory.is_link(name):
				skipped.append(path.path_join(name))
				complete = false
			elif not _excluded_component(name):
				var child: String = path.path_join(name)
				if DirAccess.dir_exists_absolute(child):
					directories[child] = true
					if recursive: pending.append(child)
				else: pending.append(child)
			name = directory.get_next()
		directory.list_dir_end()
		if entries > MAX_ENTRIES: break
	if include_overlays:
		for uri: String in store.overlays():
			if _in_scope(uri, scope): candidates[uri] = true
	var uris: Array = candidates.keys()
	uris.sort()
	var dirs: Array = directories.keys()
	dirs.sort()
	return {"uris": uris, "directories": dirs, "complete": complete and skipped.is_empty(), "skipped_files": skipped}

func source_uris() -> Dictionary:
	var catalog: Dictionary = _catalog("res://")
	if catalog.has("error"): return catalog
	var uris: Array = []
	for uri: String in catalog.uris:
		if uri.get_extension() in ["gd", "gdshader"] and not uri.begins_with("res://addons/godot_mcp/"): uris.append(uri)
	catalog.uris = uris
	return catalog

func symbols(source: String) -> Array:
	var regex := RegEx.new()
	regex.compile("(?m)^(?:static[ \\t]+)?(?:func|class_name|class|signal|var|const)[ \\t]+([A-Za-z_][A-Za-z0-9_]*)")
	var result: Array = []
	var previous: int = 0
	var line: int = 1
	var line_start: int = 0
	for matched: RegExMatch in regex.search_all(source):
		var offset: int = matched.get_start(1)
		var segment: String = source.substr(previous, offset - previous)
		line += segment.count("\n")
		if segment.contains("\n"): line_start = previous + segment.rfind("\n") + 1
		result.append({"name": matched.get_string(1), "line": line, "column": offset - line_start + 1, "offset": offset})
		previous = offset
	return result

func _take(state: Dictionary, item: Dictionary, info: Dictionary) -> bool:
	if state.skip > 0:
		state.skip -= 1
		return false
	if state.matches.size() == state.limit:
		state.more = true
		return true
	if not info.is_empty():
		item.revision = info.revision
		item.unsaved = info.unsaved
		item.base_retained = info.base_retained
	state.matches.append(item)
	return false

func search(p: Dictionary) -> Dictionary:
	var mode: String = str(p.get("mode", "name"))
	var query: String = str(p.get("query", ""))
	if mode != "list" and query.strip_edges().is_empty(): return host.fail("INVALID_ARGUMENT", "query is required and must be nonempty for name, content, and symbol modes.")
	if mode != "list" and mode not in ["name", "content", "symbol"]: return host.fail("INVALID_ARGUMENT", "mode must be name, content, symbol, or list.")
	if mode != "list" and p.has("recursive"): return host.fail("INVALID_ARGUMENT", "recursive is only supported in list mode.")
	var recursive: bool = bool(p.get("recursive", true))
	var catalog: Dictionary = _catalog(str(p.get("scope", "res://")), recursive, mode != "list")
	if catalog.has("error"): return catalog
	if mode == "list": return _list(catalog, p, recursive)
	query = query.to_lower()
	var offset: int = maxi(0, int(p.get("offset", 0)))
	var state: Dictionary = {"matches": [], "skip": offset, "limit": clampi(int(p.get("limit", 100)), 1, 1000), "more": false}
	var scanned: int = 0
	for uri: String in catalog.uris:
		var source_kind: bool = uri.get_extension() in ["gd", "gdshader"]
		var type: String = ("GDScript" if uri.ends_with(".gd") else "Shader") if source_kind else EditorInterface.get_resource_filesystem().get_file_type(uri)
		if not p.get("types", []).is_empty() and type not in p.types and not (type == "GDScript" and "Script" in p.types): continue
		if mode == "symbol" and not source_kind: continue
		if mode == "content" and uri.get_extension() not in TEXT_EXTENSIONS: continue
		var info: Dictionary = {}
		var source: String = ""
		if source_kind:
			info = store.source_info(uri)
			if info.has("error"):
				catalog.complete = false
				catalog.skipped_files.append(uri)
				continue
			source = info.source
		elif mode != "name":
			var file := FileAccess.open(uri, FileAccess.READ)
			if not file or file.get_length() > MAX_TEXT_BYTES:
				catalog.complete = false
				catalog.skipped_files.append(uri)
				continue
			source = file.get_as_text()
		if mode != "name" and source.to_utf8_buffer().size() > MAX_TEXT_BYTES:
			catalog.complete = false
			catalog.skipped_files.append(uri)
			continue
		scanned += 1
		if mode == "name":
			if uri.to_lower().contains(query) and _take(state, {"uri": uri, "type": type}, info): break
		elif mode == "symbol":
			for symbol: Dictionary in symbols(source):
				if str(symbol.name).to_lower().contains(query):
					symbol.uri = uri
					symbol.type = type
					if _take(state, symbol, info): break
		else:
			var lines: PackedStringArray = source.split("\n")
			for line: int in lines.size():
				var column: int = lines[line].to_lower().find(query)
				if column >= 0 and _take(state, {"uri": uri, "line": line + 1, "column": column + 1, "text": lines[line].substr(maxi(0, column - 120), 1000), "type": type}, info): break
		if state.more: break
	return {"matches": state.matches, "searched_files": scanned, "has_more": state.more, "next_offset": offset + state.matches.size() if state.more else null, "complete": catalog.complete, "skipped_files": catalog.skipped_files, "scope": "project paths plus live source drafts; dot paths and symlinks excluded; pagination observes current state"}

func _list(catalog: Dictionary, p: Dictionary, recursive: bool) -> Dictionary:
	var entries: Array = []
	for uri: String in catalog.uris:
		var type: String = "GDScript" if uri.ends_with(".gd") else ("Shader" if uri.ends_with(".gdshader") else EditorInterface.get_resource_filesystem().get_file_type(uri))
		if not p.get("types", []).is_empty() and type not in p.types and not (type == "GDScript" and "Script" in p.types): continue
		entries.append({"uri": uri, "type": type, "kind": "file"})
	for uri: String in catalog.directories:
		if not p.get("types", []).is_empty() and "Directory" not in p.types: continue
		entries.append({"uri": uri, "type": "Directory", "kind": "directory"})
	# Inspect the store's keys only: listing drafts must not load source text or retain a base.
	for uri: String in store.states.keys():
		if FileAccess.file_exists(uri): continue
		if not _in_scope(uri, str(p.get("scope", "res://"))) or not uri.get_extension() in ["gd", "gdshader"]: continue
		var relative: String = uri.trim_prefix(str(p.get("scope", "res://")).trim_suffix("/")).trim_prefix("/")
		if not recursive and relative.contains("/"): continue
		if not bool(store.states[uri].get("dirty", false)) or Array(relative.split("/")).any(func(part: String) -> bool: return _excluded_component(part)): continue
		var type: String = "GDScript" if uri.ends_with(".gd") else "Shader"
		if not p.get("types", []).is_empty() and type not in p.types and not (type == "GDScript" and "Script" in p.types): continue
		entries.append({"uri": uri, "type": type, "kind": "draft"})
	entries.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return str(a.uri) + str(a.kind) < str(b.uri) + str(b.kind))
	var offset: int = maxi(0, int(p.get("offset", 0)))
	var limit: int = clampi(int(p.get("limit", 100)), 1, 1000)
	var matches: Array = entries.slice(offset, offset + limit)
	var more: bool = offset + matches.size() < entries.size()
	return {"matches": matches, "searched_files": catalog.uris.size(), "has_more": more, "next_offset": offset + matches.size() if more else null, "complete": catalog.complete, "skipped_files": catalog.skipped_files, "scope": "project files and directories plus live source drafts; dot paths and symlinks excluded; query is ignored in list mode; recursive controls directory traversal; pagination observes current state"}
