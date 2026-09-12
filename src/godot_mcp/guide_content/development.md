# Godot development choices

Godot offers several ways to implement a game. Choose according to the user's design, the existing project, and the parts that need to change. The options below explain technical benefits and tradeoffs. They do not prescribe a genre, visual style, game mechanic, or project architecture. Examples illustrate possibilities rather than required templates.

## Scenes, scripts, and composition

A scene stores a node hierarchy and configured properties. It is useful for a structure that should be visible and editable in the editor, such as a character, a room, or a reusable UI component. Instancing the same scene lets changes to its source flow to its instances. Per-instance overrides allow variation without copying the entire structure.

Scripts express behavior and can also construct nodes. Runtime generation fits structures determined by data or gameplay, such as a generated dungeon or an inventory populated at runtime. It can still instantiate authored scenes. A small unique behavior does not need a separate scene merely to satisfy a pattern.

Composition works well when components have distinct behavior or lifetimes. Inherited scenes fit variants that share a base hierarchy, but deep inheritance makes changes depend on more layers. A self-contained scene is easier to reuse when its public configuration and signals describe its relationship to its surroundings. A scene with intentionally close coupling to its parent is also a valid local design.

For example, a projectile scene might contain its visual, collision, and movement script. A spawner can create instances and configure their speed. A large procedural effect might instead create and manage its elements in one script if that better matches its performance and editing needs.

With MCP, `create_scene` creates an authored scene, `create_nodes` can instantiate scenes or create engine nodes, and `apply_script_changes` implements behavior. The `work` section explains these calls. [Scene organization](https://docs.godotengine.org/en/stable/tutorials/best_practices/scene_organization.html), [Scenes versus scripts](https://docs.godotengine.org/en/stable/tutorials/best_practices/scenes_versus_scripts.html).

## Resources and editable data

Resources hold data and can be saved separately or embedded in a scene. They suit reusable materials, animation libraries, shapes, and configuration that benefits from Inspector editing. Exported script properties make relevant values editable and persistable without changing source for each adjustment.

Shared resources make common changes propagate to their users. Separate copies fit values that should diverge. This is a scope decision: changing a shared material's color can affect several objects. Mutable per-instance state, such as a particular enemy's current health, needs an ownership model appropriate to that instance even if its default stats are shared.

For a small configuration, exported properties may be enough. A reusable collection of related settings may fit a custom Resource. Dictionaries or other runtime data can be suitable when editor serialization is unnecessary. Godot supports custom Resources, but the MCP `create_resource` path directly creates engine classes only; inspect actual supported resources and classes when choosing an MCP editing route.

`get_resource` reports values and known users; `update_resource` distinguishes local and shared targets. Imported resources require attention to their import ownership, explained in `model`. [Resources](https://docs.godotengine.org/en/stable/tutorials/scripting/resources.html), [Exported properties](https://docs.godotengine.org/en/stable/tutorials/scripting/gdscript/gdscript_exports.html).

## Communication and lifetime

Direct calls and references are useful when one object deliberately owns or depends on another. Signals suit events whose producer need not know every listener, such as a button selection or an enemy's defeat. Too many relayed signals can make control flow harder to follow; a direct call can be clearer for a simple local relationship.

A parent or another owning system can connect independent scenes. Autoloads suit services or state that intentionally outlive individual scenes, such as a session manager. State used by only one scene can stay with that scene. Neither an all-global architecture nor a universal signal bus is required.

`update_signals` handles persistent editor connections. Script changes can add code and bindings together. Runtime connections belong in script when their lifetime is dynamic. [Scene organization](https://docs.godotengine.org/en/stable/tutorials/best_practices/scene_organization.html), [Autoloads versus regular nodes](https://docs.godotengine.org/en/stable/tutorials/best_practices/autoloads_versus_regular_nodes.html).

## UI layout and presentation

Containers manage child placement and sizing. They fit rows, columns, grids, and other layouts that should adapt to content. Anchors and offsets fit controls positioned relative to a parent. Direct or custom layout can fit intentionally free-form interfaces. Manual child positions inside a Container may be overwritten by its layout rules.

Themes share fonts, colors, and styles. Per-control overrides fit local exceptions; shared Theme changes fit a consistent update across several screens. A reusable scene helps repeated components evolve together. Runtime-generated controls fit content-dependent structure and can use the same Themes and component scenes.

For a shop, one option is a reusable item scene instantiated inside a Container and populated from data. An artistic interface arranged along an irregular path may instead need custom placement. Neither choice determines the game's visual style.

`get_scene` can report actual Control layout; node and resource edits configure layout and styling. [Containers](https://docs.godotengine.org/en/stable/tutorials/ui/gui_containers.html), [Themes](https://docs.godotengine.org/en/stable/tutorials/ui/gui_skinning.html).

## Animation

AnimationPlayer suits authored timelines with coordinated property tracks. AnimationTree adds state transitions or blending when motion depends on game state. Tweens suit lightweight interpolation toward values determined at runtime. Script-driven animation is appropriate when the motion itself is procedural.

For example, a carefully timed door sequence may fit an AnimationPlayer. A changing UI number or one-off fade may fit a Tween. Locomotion that blends direction and speed may benefit from AnimationTree. Complexity should follow the behavior being implemented.

MCP provides animation track editing, graph editing, and pose preview. Preview does not execute method or audio tracks. Tween behavior is written in scripts. [Animation introduction](https://docs.godotengine.org/en/stable/tutorials/animation/introduction.html), [AnimationTree](https://docs.godotengine.org/en/stable/tutorials/animation/animation_tree.html), [Tween](https://docs.godotengine.org/en/stable/classes/class_tween.html).

## World implementation and project organization

TileMapLayer and TileSet fit grid-based 2D worlds with reusable tiles, terrain connections, and collision data. Scene instances fit objects with their own behavior. Procedural meshes, custom drawing, or other data-driven representations fit worlds whose structure does not match a tile grid. A project can combine these approaches.

For procedural content, keeping generation inputs distinct from generated output can make tuning and regeneration easier. Editor generation is useful when the result needs manual editing; runtime generation fits content that changes during play. `@tool` scripts are an option for needed editor behavior, not a prerequisite for procedural systems.

Organizing related scenes, scripts, and assets together can make a feature easy to move and understand. Existing project conventions may instead organize by asset type or another useful boundary. Use names and ownership that help the people developing this project.

`edit_tileset` and `paint_tiles` cover tile authoring. Scripts implement generators, and scene/resource tools configure their inputs. [Tilemaps](https://docs.godotengine.org/en/stable/tutorials/2d/using_tilemaps.html), [Project organization](https://docs.godotengine.org/en/stable/tutorials/best_practices/project_organization.html), [Running code in the editor](https://docs.godotengine.org/en/stable/tutorials/plugins/running_code_in_the_editor.html).
