@tool
extends RefCounted
var host: EditorPlugin

func _init(editor_host: EditorPlugin) -> void:
	host = editor_host

func handles(method: String) -> bool:
	return method in ["get_tilemap", "edit_tileset", "paint_tiles"]

func dispatch(method: String, p: Dictionary) -> Dictionary:
	match method:
		"get_tilemap": return get_tilemap(p)
		"edit_tileset": return edit_tileset(p)
		"paint_tiles": return await paint_tiles(p)
	return host.fail("UNKNOWN_TOOL", method)

func coord(value: Dictionary) -> Vector2i:
	return Vector2i(int(value.get("x", 0)), int(value.get("y", 0)))

func cell(layer: TileMapLayer, at: Vector2i) -> Dictionary:
	var atlas: Vector2i = layer.get_cell_atlas_coords(at)
	return {"cell": {"x": at.x, "y": at.y}, "tile": {"source_id": layer.get_cell_source_id(at), "atlas": {"x": atlas.x, "y": atlas.y}, "alternative": layer.get_cell_alternative_tile(at)}}

func tile_info(ts: TileSet, limit: int = 2000) -> Dictionary:
	if not ts: return {}
	var result: Dictionary = {"resource": host.encode(ts), "tile_size": host.encode(ts.tile_size), "sources": [], "terrain_sets": [], "physics_layers": []}
	var count: int = 0
	for index: int in ts.get_source_count():
		var id: int = ts.get_source_id(index)
		var source: TileSetSource = ts.get_source(id)
		var entry: Dictionary = {"source_id": id, "class": source.get_class(), "tiles": []}
		if source is TileSetAtlasSource:
			entry.texture = host.encode(source.texture)
			entry.tile_size = host.encode(source.texture_region_size)
			for i: int in source.get_tiles_count():
				if count >= limit:
					entry.truncated = true
					break
				var at: Vector2i = source.get_tile_id(i)
				var alternatives: Array = []
				for alt: int in source.get_alternative_tiles_count(at): alternatives.append(source.get_alternative_tile_id(at, alt))
				var data: TileData = source.get_tile_data(at, 0)
				entry.tiles.append({"atlas": {"x": at.x, "y": at.y}, "alternatives": alternatives, "terrain_set": data.terrain_set, "terrain": data.terrain})
				count += 1
		result.sources.append(entry)
	for set: int in ts.get_terrain_sets_count():
		var terrains: Array = []
		for id: int in ts.get_terrains_count(set): terrains.append({"id": id, "name": ts.get_terrain_name(set, id), "color": host.encode(ts.get_terrain_color(set, id))})
		result.terrain_sets.append({"set": set, "mode": ts.get_terrain_set_mode(set), "terrains": terrains})
	for index: int in ts.get_physics_layers_count(): result.physics_layers.append({"index": index, "collision_layer": ts.get_physics_layer_collision_layer(index), "collision_mask": ts.get_physics_layer_collision_mask(index)})
	return result

func get_tilemap(p: Dictionary) -> Dictionary:
	var layer: TileMapLayer = host.resolve_node(p.get("layer", {})) as TileMapLayer
	if not layer: return host.fail("INVALID_NODE", "Use a TileMapLayer node (Godot's current tile API).")
	var coordinates: Array[Vector2i] = []
	var limit: int = int(p.get("limit", 1000))
	if p.has("region"):
		var origin: Vector2i = coord(p.region.origin)
		var size: Vector2i = coord(p.region.size)
		if size.x * size.y > 10000: return host.fail("LIMIT_EXCEEDED", "Regions are limited to 10000 cells.")
		for y: int in range(origin.y, origin.y + size.y):
			for x: int in range(origin.x, origin.x + size.x): coordinates.append(Vector2i(x, y))
	else:
		coordinates = layer.get_used_cells()
	var cells: Array = []
	for at: Vector2i in coordinates.slice(0, limit): cells.append(cell(layer, at))
	return {"layer": host.node_ref(layer), "cells": cells, "truncated": coordinates.size() > limit, "tileset": tile_info(layer.tile_set)}

func apply_resource(target: Resource, value: Resource) -> void:
	target.copy_from_resource(value)
	target.emit_changed()
	EditorInterface.set_object_edited(target, true)

func edit_tileset(p: Dictionary) -> Dictionary:
	var target: Dictionary = p.get("target", {})
	var original: TileSet = host.resolve_resource(target) as TileSet
	if not original: return host.fail("INVALID_RESOURCE", "Target must resolve to a TileSet.")
	var scope: String = p.get("scope", "node")
	if scope == "node" and not target.has("node"): return host.fail("SCOPE_REQUIRED", "Node scope requires a node property target.")
	if scope == "shared" and FileAccess.file_exists(original.resource_path.get_slice("::", 0) + ".import"): return host.fail("IMPORTED_RESOURCE", "Detach an imported TileSet with node scope.")
	var ts: TileSet = original.duplicate(true)
	var keys: Dictionary = {}
	var changed: Array = []
	for change: Dictionary in p.get("changes", []):
		var op: String = change.get("op", "")
		if op == "add_atlas":
			var texture: Texture2D = host.resource_uri(str(change.get("texture", ""))) as Texture2D
			if not texture: return host.fail("INVALID_TEXTURE", "Import a Texture2D before adding an atlas.")
			var source := TileSetAtlasSource.new()
			source.texture = texture
			source.texture_region_size = coord(change.get("tile_size", {"x": 16, "y": 16}))
			var desired: int = int(change.get("source_id", -1))
			if desired >= 0 and ts.has_source(desired): return host.fail("SOURCE_EXISTS", "Tile source ID already exists.")
			var id: int = ts.add_source(source, desired)
			if change.has("key"):
				if keys.has(change.key): return host.fail("DUPLICATE_KEY", "Atlas keys must be unique within the edit.")
				keys[change.key] = id
			changed.append({"op": op, "source_id": id, "key": change.get("key", "")})
			continue
		if op == "add_physics_layer":
			ts.add_physics_layer()
			var layer: int = ts.get_physics_layers_count() - 1
			ts.set_physics_layer_collision_layer(layer, int(change.get("collision_layer", 1)))
			ts.set_physics_layer_collision_mask(layer, int(change.get("collision_mask", 1)))
			changed.append({"op": op, "physics_layer": layer})
			continue
		if op == "add_terrain_set":
			ts.add_terrain_set()
			var set: int = ts.get_terrain_sets_count() - 1
			ts.set_terrain_set_mode(set, {"corners_and_sides": TileSet.TERRAIN_MODE_MATCH_CORNERS_AND_SIDES, "corners": TileSet.TERRAIN_MODE_MATCH_CORNERS, "sides": TileSet.TERRAIN_MODE_MATCH_SIDES}.get(change.get("mode", "corners_and_sides"), TileSet.TERRAIN_MODE_MATCH_CORNERS_AND_SIDES))
			for terrain: Dictionary in change.get("terrains", []):
				ts.add_terrain(set)
				var id: int = ts.get_terrains_count(set) - 1
				ts.set_terrain_name(set, id, terrain.name)
				if terrain.has("color"):
					var color: Variant = host.decode(terrain.color)
					if not color is Color: return host.fail("INVALID_VALUE", "Terrain color must be a Color.")
					ts.set_terrain_color(set, id, color)
			changed.append({"op": op, "terrain_set": set})
			continue
		var source_id: int = int(keys.get(change.get("source_key", ""), change.get("source_id", -1)))
		if not ts.has_source(source_id): return host.fail("SOURCE_NOT_FOUND", "Atlas source ID/key does not exist.")
		var source: TileSetAtlasSource = ts.get_source(source_id) as TileSetAtlasSource
		if not source: return host.fail("INVALID_SOURCE", "This operation requires an atlas source.")
		var at: Vector2i = coord(change.get("atlas", {}))
		var alternative: int = int(change.get("alternative", 0))
		if op == "remove_tile":
			if source.has_tile(at):
				if alternative == 0: source.remove_tile(at)
				elif source.has_alternative_tile(at, alternative): source.remove_alternative_tile(at, alternative)
			changed.append({"op": op, "source_id": source_id, "atlas": {"x": at.x, "y": at.y}})
			continue
		if op == "define_tile":
			if not source.has_tile(at):
				var size: Vector2i = coord(change.get("size", {"x": 1, "y": 1}))
				if not source.has_room_for_tile(at, size, 1, Vector2i.ZERO, 1): return host.fail("ATLAS_BOUNDS", "Tile overlaps another tile or extends outside the atlas.")
				source.create_tile(at, size)
			if alternative != 0 and not source.has_alternative_tile(at, alternative): source.create_alternative_tile(at, alternative)
		if not source.has_tile(at) or not source.has_alternative_tile(at, alternative): return host.fail("TILE_NOT_FOUND", "Tile/alternative must exist before editing it.")
		var data: TileData = source.get_tile_data(at, alternative)
		if op == "collision":
			var layer: int = int(change.get("physics_layer", 0))
			if layer >= ts.get_physics_layers_count(): return host.fail("PHYSICS_LAYER_NOT_FOUND", "Add the TileSet physics layer first.")
			var polygons: Array = change.get("polygons", [])
			data.set_collision_polygons_count(layer, polygons.size())
			for i: int in polygons.size():
				var polygon := PackedVector2Array()
				for point: Dictionary in polygons[i]: polygon.append(host.Codec.v2(point))
				data.set_collision_polygon_points(layer, i, polygon)
				data.set_collision_polygon_one_way(layer, i, change.get("one_way", false))
		elif op == "terrain" or op == "define_tile":
			if change.has("terrain_set") or change.has("terrain"):
				var set: int = int(change.get("terrain_set", 0))
				var terrain: int = int(change.get("terrain", -1))
				if set < 0 or set >= ts.get_terrain_sets_count() or terrain >= ts.get_terrains_count(set): return host.fail("TERRAIN_NOT_FOUND", "Terrain set/id does not exist.")
				data.terrain_set = set
				data.terrain = terrain
			for bit: String in change.get("peering_bits", {}):
				var terrain: int = int(change.peering_bits[bit])
				if not bit.is_valid_int() or data.terrain_set < 0 or not ts.is_valid_terrain_peering_bit(data.terrain_set, int(bit)) or terrain >= ts.get_terrains_count(data.terrain_set): return host.fail("INVALID_PEERING_BIT", "Peering bit or terrain ID is invalid for the terrain set.")
				data.set_terrain_peering_bit(int(bit), terrain)
			if change.has("probability"): data.probability = float(change.probability)
		else: return host.fail("INVALID_OPERATION", "Unknown TileSet operation.")
		changed.append({"op": op, "source_id": source_id, "atlas": {"x": at.x, "y": at.y}, "alternative": alternative})
	var result: Dictionary
	if scope == "node":
		var node: Node = host.resolve_node(target.node)
		result = host.commit_changes([{"object": node, "property": target.property, "before": original, "after": ts}], host.scene_root(target.node.scene), "Edit TileSet")
	else:
		host.begin_edit("Edit shared TileSet", original)
		host.get_undo_redo().add_do_method(self, "apply_resource", original, ts)
		host.get_undo_redo().add_undo_method(self, "apply_resource", original, original.duplicate(true))
		result = host.finish_edit(original, "Edit shared TileSet")
	result.changed = changed
	result.keys = keys
	result.scope = scope
	result.tileset = tile_info(ts)
	return result

func validate_tile(ts: TileSet, tile: Dictionary) -> String:
	var source_id: int = int(tile.get("source_id", -1))
	if source_id < 0: return ""
	if not ts or not ts.has_source(source_id): return "Tile source ID does not exist."
	var source: TileSetSource = ts.get_source(source_id)
	if source is TileSetAtlasSource:
		var at: Vector2i = coord(tile.get("atlas", {}))
		var alternative: int = int(tile.get("alternative", 0))
		var base: int = alternative & ~(TileSetAtlasSource.TRANSFORM_FLIP_H | TileSetAtlasSource.TRANSFORM_FLIP_V | TileSetAtlasSource.TRANSFORM_TRANSPOSE)
		if not source.has_tile(at) or not source.has_alternative_tile(at, base): return "Atlas tile or alternative does not exist."
	elif source is TileSetScenesCollectionSource:
		if not source.has_scene_tile(int(tile.get("alternative", 0))): return "Scene tile does not exist."
	return ""

func apply_cells(layer: TileMapLayer, cells: Array) -> void:
	for entry: Dictionary in cells:
		var at: Vector2i = coord(entry.cell)
		var tile: Dictionary = entry.tile
		if int(tile.get("source_id", -1)) < 0: layer.erase_cell(at)
		else: layer.set_cell(at, int(tile.source_id), coord(tile.get("atlas", {})), int(tile.get("alternative", 0)))

func paint_tiles(p: Dictionary) -> Dictionary:
	var layer: TileMapLayer = host.resolve_node(p.get("layer", {})) as TileMapLayer
	if not layer or not layer.tile_set: return host.fail("INVALID_NODE", "Use a TileMapLayer with a TileSet.")
	var specs: Array = p.get("cells", []).duplicate(true)
	if p.has("region"):
		var origin: Vector2i = coord(p.region.origin)
		var size: Vector2i = coord(p.region.size)
		if size.x * size.y + specs.size() > 10000: return host.fail("LIMIT_EXCEEDED", "At most 10000 input cells per edit.")
		for y: int in range(origin.y, origin.y + size.y):
			for x: int in range(origin.x, origin.x + size.x): specs.append({"cell": {"x": x, "y": y}, "tile": p.region.tile})
	if p.has("pattern"):
		var origin: Vector2i = coord(p.pattern.at)
		for entry: Dictionary in p.pattern.cells:
			var at: Vector2i = origin + coord(entry.cell)
			specs.append({"cell": {"x": at.x, "y": at.y}, "tile": entry.tile})
	if specs.size() > 10000: return host.fail("LIMIT_EXCEEDED", "At most 10000 input cells per edit.")
	if specs.is_empty() and not p.has("terrain"): return host.fail("EMPTY_EDIT", "Provide cells, a region, a pattern or terrain.")
	for spec: Dictionary in specs:
		var error: String = validate_tile(layer.tile_set, spec.tile)
		if not error.is_empty(): return host.fail("INVALID_TILE", error)
	var before_coords: Array[Vector2i] = layer.get_used_cells()
	if before_coords.size() > 100000: return host.fail("LIMIT_EXCEEDED", "This layer exceeds the 100000-cell transaction limit.")
	var before: Array = []
	for at: Vector2i in before_coords: before.append(cell(layer, at))
	var staged := TileMapLayer.new()
	staged.tile_set = layer.tile_set
	apply_cells(staged, before)
	apply_cells(staged, specs)
	var requested: Dictionary = {}
	for spec: Dictionary in specs: requested[coord(spec.cell)] = true
	if p.has("terrain"):
		var terrain: Dictionary = p.terrain
		var set: int = int(terrain.get("set", 0))
		var id: int = int(terrain.get("id", -1))
		if set >= layer.tile_set.get_terrain_sets_count() or id >= layer.tile_set.get_terrains_count(set):
			staged.free()
			return host.fail("TERRAIN_NOT_FOUND", "Terrain set/id does not exist.")
		var coordinates: Array[Vector2i] = []
		for value: Dictionary in terrain.cells:
			var at: Vector2i = coord(value)
			coordinates.append(at)
			requested[at] = true
		if terrain.get("mode", "connect") == "path": staged.set_cells_terrain_path(coordinates, set, id, terrain.get("ignore_empty", true))
		else: staged.set_cells_terrain_connect(coordinates, set, id, terrain.get("ignore_empty", true))
	var all: Dictionary = {}
	for at: Vector2i in before_coords: all[at] = true
	for at: Vector2i in staged.get_used_cells(): all[at] = true
	var old: Array = []
	var new: Array = []
	var neighbors: Array = []
	for at: Vector2i in all:
		var a: Dictionary = cell(layer, at)
		var b: Dictionary = cell(staged, at)
		if a.tile != b.tile:
			old.append(a)
			new.append(b)
			if not requested.has(at): neighbors.append(b)
	staged.free()
	if new.is_empty(): return {"changed": [], "auto_connected": [], "count": 0, "saved": false}
	host.begin_edit("Paint tiles", layer)
	host.get_undo_redo().add_do_method(self, "apply_cells", layer, new)
	host.get_undo_redo().add_undo_method(self, "apply_cells", layer, old)
	var result: Dictionary = host.finish_edit(layer, "Paint tiles")
	await host.get_tree().process_frame
	result.changed = new
	result.auto_connected = neighbors
	result.count = new.size()
	return result
