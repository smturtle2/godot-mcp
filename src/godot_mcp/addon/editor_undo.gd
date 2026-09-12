@tool
extends RefCounted
## Native editor commands keep the manager's action stacks and UndoRedo in sync.
var host: EditorPlugin
var revision: int = 0

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host
	host.get_undo_redo().history_changed.connect(_changed)
	host.get_undo_redo().version_changed.connect(_changed)

func shutdown() -> void:
	var manager := host.get_undo_redo()
	if manager.history_changed.is_connected(_changed): manager.history_changed.disconnect(_changed)
	if manager.version_changed.is_connected(_changed): manager.version_changed.disconnect(_changed)

func _changed() -> void:
	revision += 1

func matches(edit: Dictionary) -> bool:
	return edit.get("editor_revision", -1) == revision

func _command() -> Dictionary:
	# These shortcut resources identify the scene menu independently of locale,
	# focus, configured keys, or the position of the Undo menu item.
	var settings := EditorInterface.get_editor_settings()
	var save_all: Shortcut = settings.get_shortcut("editor/save_all_scenes")
	var undo: Shortcut = settings.get_shortcut("ui_undo")
	if not save_all or not undo: return {}
	for node: Node in EditorInterface.get_base_control().find_children("*", "PopupMenu", true, false):
		var menu: PopupMenu = node as PopupMenu
		var scene_menu: bool = false
		var undo_index: int = -1
		for index: int in menu.item_count:
			var shortcut: Shortcut = menu.get_item_shortcut(index)
			if shortcut == save_all: scene_menu = true
			if shortcut == undo: undo_index = index
		if scene_menu and undo_index >= 0: return {"menu": menu, "index": undo_index}
	return {}

func undo(edit: Dictionary) -> Dictionary:
	if not matches(edit): return host.fail("EDIT_CONFLICT", "Another editor action changed the native Undo order.")
	var command: Dictionary = _command()
	if command.is_empty(): return host.fail("UNDO_UNAVAILABLE", "The editor Undo command is unavailable; no history was changed.")
	var menu: PopupMenu = command.menu
	if menu.is_item_disabled(command.index): return host.fail("UNDO_UNAVAILABLE", "The editor Undo command is disabled; no history was changed.")
	var history: UndoRedo = host.get_undo_redo().get_history_undo_redo(edit.history_id)
	var before: int = history.get_version()
	var prior_revision: int = revision
	menu.id_pressed.emit(menu.get_item_id(command.index))
	if history.get_version() == before or revision == prior_revision:
		return host.fail("UNDO_NOT_APPLIED", "The requested native Undo was not observed. The MCP edit record was retained.", {"edit_id": edit.edit_id})
	return {"undone": edit.edit_id}
