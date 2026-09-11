"""Acceptance coverage for the named editor mutation payloads."""
from __future__ import annotations

import os

import pytest

from godot_mcp.bridge import ToolError

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("GODOT_MCP_INTEGRATION") != "1", reason="opt-in real editor"),
]


def ref(path: str = ".", scene: str = "res://main.tscn") -> dict:
    return {"scene": scene, "path": path}


def vector(x: float, y: float) -> dict:
    return {"$type": "Vector2", "x": x, "y": y}


async def call(bridge, tool_name: str, **arguments):
    result = await bridge.call(tool_name, arguments)
    assert result, f"{tool_name} returned empty (check GDScript runtime errors)"
    return result


def prepare_peering_probe(project):
    plugin = project / "addons/godot_mcp/plugin.gd"
    source = plugin.read_text()
    signature = "func dispatch(method: String, p: Dictionary) -> Dictionary:\n"
    source = source.replace(signature, signature + '''
	if method == "_test_peering":
		var layer: TileMapLayer = resolve_node(p.node)
		var data: TileData = layer.tile_set.get_source(0).get_tile_data(Vector2i.ZERO, 0)
		var bits: Dictionary = {}
		for bit: int in [0, 8, 12, 15]: bits[str(bit)] = data.get_terrain_peering_bit(bit)
		return {"terrain": data.terrain, "bits": bits}
''')
    plugin.write_text(source)


@pytest.mark.parametrize("editor", [prepare_peering_probe], indirect=True)
async def test_named_animation_and_tileset_batches(editor, tmp_path):
    bridge, _ = editor

    await call(
        bridge,
        "create_nodes",
        parent=ref(),
        nodes=[
            {"name": "Anim", "source": {"class": "AnimationPlayer"}},
            {"name": "Tiles", "source": {"class": "TileMapLayer"}},
        ],
    )

    created = await call(
        bridge,
        "edit_animation",
        player=ref("Anim"),
        name="named",
        create=True,
        length=1,
        tracks=[
            {
                "add": {
                    "kind": "value",
                    "path": "Tiles:position",
                    "keys": [{"set": {"time": 0, "value": vector(0, 0)}}],
                }
            }
        ],
    )
    assert created["scope"] == "local" and created["track_count"] == 1

    updated = await call(
        bridge,
        "edit_animation",
        player=ref("Anim"),
        name="named",
        tracks=[
            {
                "update": {
                    "index": 0,
                    "keys": [
                        {"set": {"time": 1, "value": vector(4, 0)}},
                        {"remove": {"time": 0}},
                    ],
                }
            }
        ],
    )
    assert updated["track_count"] == 1
    animation = await call(bridge, "get_animation", node=ref("Anim"), animation="named")
    assert [key["time"] for key in animation["animations"][0]["tracks"][0]["keys"]] == [1]

    removed = await call(
        bridge,
        "edit_animation",
        player=ref("Anim"),
        name="named",
        tracks=[{"remove": {"index": 0}}],
    )
    assert removed["track_count"] == 0

    await call(bridge, "create_resource", **{"class": "TileSet", "assign_to": {"node": ref("Tiles"), "property": "tile_set"}})
    await call(bridge, "save_documents", uris=["res://main.tscn"])
    atlas = tmp_path / "named.svg"
    atlas.write_text('<svg xmlns="http://www.w3.org/2000/svg" width="32" height="16"><rect width="32" height="16" fill="#138cf2"/></svg>')
    imported = await call(bridge, "import_assets", files=[{"source": atlas.as_uri(), "destination": "res://art/named.svg"}])
    assert imported["assets"][0]["imported"]

    local_target = {"local": {"scene": "res://main.tscn", "path": "Tiles", "property": "tile_set"}}
    changes = [
        {"add_atlas": {"texture": "res://art/named.svg", "key": "atlas"}},
        {"add_physics_layer": {}},
        {"add_terrain_set": {"terrains": [{"name": "ground"}]}},
        {
            "define_tile": {
                "source": {"id": 0.0},
                "atlas": {"x": 0, "y": 0},
                "set": {"terrain_set": 0, "terrain": 0, "probability": 0.5},
            }
        },
        {
            "collision": {
                "source": {"key": "atlas"},
                "atlas": {"x": 0, "y": 0},
                "polygons": [],
            }
        },
        {"terrain": {"source": {"key": "atlas"}, "atlas": {"x": 0, "y": 0}, "set": {"terrain_set": 0, "terrain": 0}}},
        {"remove_tile": {"source": {"key": "atlas"}, "atlas": {"x": 0, "y": 0}}},
    ]
    edited = await call(bridge, "edit_tileset", target=local_target, changes=changes)
    assert edited["scope"] == "local" and len(edited["changed"]) == 7
    assert edited["changed"][0]["source_id"] == 0
    before = await call(bridge, "get_tilemap", layer=ref("Tiles"))
    with pytest.raises(ToolError):
        await call(
            bridge,
            "edit_tileset",
            target=local_target,
            changes=[{"define_tile": {"source": {"key": "missing"}, "atlas": {"x": 0, "y": 0}}}],
        )
    with pytest.raises(ToolError):
        await call(
            bridge,
            "edit_tileset",
            target=local_target,
            changes=[
                {"define_tile": {"source": {"id": 0.5}, "atlas": {"x": 0, "y": 0}}},
            ],
        )
    with pytest.raises(ToolError):
        await call(
            bridge,
            "edit_tileset",
            target=local_target,
            changes=[{"define_tile": {"source": {"id": -1}, "atlas": {"x": 0, "y": 0}}}],
        )
    after = await call(bridge, "get_tilemap", layer=ref("Tiles"))
    assert len(after["tileset"]["sources"]) == len(before["tileset"]["sources"])
    await call(bridge, "undo_edit", edit_id=edited["edit_id"])

    configured = await call(
        bridge, "edit_tileset", target=local_target,
        changes=[
            {"add_atlas": {"texture": "res://art/named.svg", "key": "clear"}},
            {"add_terrain_set": {"terrains": [{"name": "ground"}]}},
            {"define_tile": {"source": {"key": "clear"}, "atlas": {"x": 0, "y": 0}, "set": {"terrain_set": 0, "terrain": 0, "peering_bits": {"0": 0, "8": 0, "12": 0, "15": 0}}}},
        ],
    )
    configured_data = await call(bridge, "_test_peering", node=ref("Tiles"))
    assert configured_data == {"terrain": 0, "bits": {"0": 0, "8": 0, "12": 0, "15": 0}}
    for invalid_set in ({"peering_bits": {"1": 0}}, {"peering_bits": {"16": 0}}, {"peering_bits": {"0": -2}}, {"terrain": -2}):
        with pytest.raises(ToolError):
            await call(bridge, "edit_tileset", target=local_target, changes=[
                {"terrain": {"source": {"id": 0}, "atlas": {"x": 0, "y": 0}, "set": invalid_set}},
            ])
        assert await call(bridge, "_test_peering", node=ref("Tiles")) == configured_data
    cleared = await call(bridge, "edit_tileset", target=local_target, changes=[
        {"terrain": {"source": {"id": 0.0}, "atlas": {"x": 0, "y": 0}, "set": {"terrain": -1, "peering_bits": {"0": -1, "8": -1, "12": -1, "15": -1}}}},
    ])
    assert await call(bridge, "_test_peering", node=ref("Tiles")) == {"terrain": -1, "bits": {"0": -1, "8": -1, "12": -1, "15": -1}}
    await call(bridge, "undo_edit", edit_id=cleared["edit_id"])
    assert await call(bridge, "_test_peering", node=ref("Tiles")) == configured_data
    await call(bridge, "undo_edit", edit_id=configured["edit_id"])

    shared_target = {"shared": {"node": {"scene": "res://main.tscn", "path": "Tiles", "property": "tile_set"}}}
    shared = await call(
        bridge,
        "edit_tileset",
        target=shared_target,
        changes=[{"add_physics_layer": {}}],
    )
    assert shared["scope"] == "shared"
