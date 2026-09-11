@tool
extends RefCounted
## Bounded per-stream byte collection; decoding happens once after process exit.
const MAX_BYTES: int = 200000
var buffers: Dictionary = {"stdout": PackedByteArray(), "stderr": PackedByteArray()}
var seen: Dictionary = {"stdout": 0, "stderr": 0}
var truncated: Dictionary = {"stdout": false, "stderr": false}

func append(stream: String, bytes: PackedByteArray) -> void:
	if not buffers.has(stream): return
	seen[stream] += bytes.size()
	var room: int = MAX_BYTES - buffers[stream].size()
	if room > 0:
		buffers[stream] += bytes.slice(0, mini(room, bytes.size()))
	if bytes.size() > maxi(room, 0): truncated[stream] = true

func _decode(stream: String) -> String:
	var bytes: PackedByteArray = buffers[stream]
	if truncated[stream] and not bytes.is_empty():
		var start: int = bytes.size() - 1
		while start >= 0 and (bytes[start] & 0xc0) == 0x80: start -= 1
		if start >= 0:
			var lead: int = bytes[start]
			var width: int = 4 if lead >= 0xf0 and lead <= 0xf4 else (3 if lead >= 0xe0 and lead <= 0xef else (2 if lead >= 0xc2 and lead <= 0xdf else 1))
			if bytes.size() - start < width: bytes = bytes.slice(0, start)
	return bytes.get_string_from_utf8()

func result() -> Dictionary:
	return {"stdout": _decode("stdout"), "stderr": _decode("stderr"), "truncated": truncated.stdout or truncated.stderr, "stdout_truncated": truncated.stdout, "stderr_truncated": truncated.stderr, "stdout_bytes": seen.stdout, "stderr_bytes": seen.stderr}
