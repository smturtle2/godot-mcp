import os

from godot_mcp import command_path


def test_register_path_zsh_quotes_spaces_and_is_idempotent(tmp_path, monkeypatch):
    home, directory = tmp_path / "home", tmp_path / "dir with 'quote'"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("ZDOTDIR", str(home))
    monkeypatch.setenv("SHELL", "/bin/zsh")
    monkeypatch.setenv("PATH", "/usr/bin")
    first = command_path.register_path(directory)
    profile = home / ".zshrc"
    original = profile.read_text()
    second = command_path.register_path(directory)
    assert "PATH configured" in first and second == first
    assert profile.read_text() == original
    assert "dir with" in profile.read_text() and "quote" in profile.read_text()
    assert profile.read_text().count("Godot MCP user command") == 1


def test_register_path_bash_preserves_profile_and_existing_path_noop(tmp_path, monkeypatch):
    home, directory = tmp_path / "home", tmp_path / "bin"
    home.mkdir()
    profile = home / ".bashrc"
    profile.write_text("export PATH=\"/usr/local/bin:$PATH\"\n")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("SHELL", "/bin/bash")
    monkeypatch.setenv("PATH", f"{directory}{os.pathsep}/usr/bin")
    assert "already" in command_path.register_path(directory)
    assert profile.read_text() == "export PATH=\"/usr/local/bin:$PATH\"\n"


def test_register_path_fish_uses_xdg_config_and_preserves_profile(tmp_path, monkeypatch):
    home, directory = tmp_path / "home", tmp_path / "bin"
    config = home / "config"
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(config))
    monkeypatch.setenv("SHELL", "/usr/bin/fish")
    command_path.register_path(directory)
    profile = config / "fish/conf.d/godot-mcp.fish"
    assert profile.is_file() and "fish_add_path" in profile.read_text()
