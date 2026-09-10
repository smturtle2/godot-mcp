#!/bin/sh
set -eu

bootstrap_url='https://raw.githubusercontent.com/smturtle2/godot-mcp/main/scripts/bootstrap.py'
uv_installer_url='https://astral.sh/uv/install.sh'
temp_dir=$(mktemp -d "${TMPDIR:-/tmp}/godot-mcp-install.XXXXXX")
cleanup() { rm -rf "$temp_dir"; }
trap cleanup EXIT HUP INT TERM

bootstrap="$temp_dir/bootstrap.py"
uv_installer="$temp_dir/uv-install.sh"
if command -v curl >/dev/null 2>&1; then
    curl --fail --silent --show-error --location "$bootstrap_url" --output "$bootstrap"
elif command -v wget >/dev/null 2>&1; then
    wget --https-only --quiet --output-document="$bootstrap" "$bootstrap_url"
else
    echo 'godot-mcp installer requires curl or wget.' >&2
    exit 1
fi

if command -v uv >/dev/null 2>&1; then
    uv_bin=$(command -v uv)
else
    user_home=${HOME:-}
    if [ -z "$user_home" ]; then
        echo 'HOME is not set; cannot locate a user-local uv installation.' >&2
        exit 1
    fi
    if command -v curl >/dev/null 2>&1; then
        curl --fail --silent --show-error --location "$uv_installer_url" --output "$uv_installer"
    elif command -v wget >/dev/null 2>&1; then
        wget --https-only --quiet --output-document="$uv_installer" "$uv_installer_url"
    else
        echo 'godot-mcp installer requires curl or wget.' >&2
        exit 1
    fi
    sh "$uv_installer"
    uv_bin="$user_home/.local/bin/uv"
    if [ ! -x "$uv_bin" ]; then
        echo "uv was not found at $uv_bin after installation." >&2
        exit 1
    fi
fi

"$uv_bin" run --no-project --python 3.13 "$bootstrap" "$@"
