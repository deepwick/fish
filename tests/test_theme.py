import shutil
import subprocess
from pathlib import Path

import pytest

from deepwick_spec.ansi import style_of
from deepwick_spec.check_port import check_port
from deepwick_spec.palette import load_palette
from deepwick_spec.tui import capture, tmux_available

REPO = Path(__file__).resolve().parents[1]
PALETTE = load_palette()
C = PALETTE.colors


def isolated_env(tmp_path, **extra):
    dirs = {"HOME": tmp_path / "home"}
    for kind in ("CONFIG", "DATA", "STATE", "CACHE"):
        dirs[f"XDG_{kind}_HOME"] = tmp_path / kind.lower()
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    env = {key: str(path) for key, path in dirs.items()}
    env.update(GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1")
    env.update({key: str(value) for key, value in extra.items()})
    return env


THEME = REPO / "deepwick.theme"
requires_fish = pytest.mark.skipif(shutil.which("fish") is None, reason="requires fish")
COLOR_VARS = {
    f"fish_color_{n}" for n in (
        "normal", "command", "keyword", "quote", "redirection", "end", "error", "param", "valid_path", "option",
        "comment", "selection", "operator", "escape", "autosuggestion", "cwd", "cwd_root", "user", "host",
        "host_remote", "status", "cancel", "search_match", "history_current",
    )
}
PAGER_VARS = {
    f"fish_pager_color_{n}" for n in (
        "progress", "background", "prefix", "completion", "description", "selected_background",
        "selected_prefix", "selected_completion", "selected_description", "secondary_background",
        "secondary_prefix", "secondary_completion", "secondary_description",
    )
}
EXPECTED = {
    "fish_color_normal": "'#D4D4D4'", "fish_color_command": "'#DCDCAA'", "fish_color_keyword": "'#569CD6'",
    "fish_color_quote": "'#CE9178'", "fish_color_redirection": "'#D4D4D4'", "fish_color_end": "'#D4D4D4'",
    "fish_color_error": "'#F44747'", "fish_color_param": "'#D4D4D4'", "fish_color_option": "'#9CDCFE'",
    "fish_color_valid_path": "--underline", "fish_color_comment": "'#7A86A8' --italics",
    "fish_color_selection": "--background='#264F78'", "fish_color_operator": "'#D7BA7D'",
    "fish_color_escape": "'#D7BA7D'", "fish_color_autosuggestion": "'#6E7899'",
    "fish_color_search_match": "--background='#264F78'",
    "fish_pager_color_selected_background": "--background='#264F78'",
    "fish_pager_color_description": "'#7A86A8'",
}


def entries():
    assert THEME.is_file(), "deepwick.theme missing"
    result = {}
    for line in THEME.read_text(encoding="utf-8").splitlines():
        if line and not line.startswith("#"):
            name, _, value = line.partition(" ")
            result[name] = value.strip()
    return result


def test_defines_every_variable():
    assert set(entries()) == COLOR_VARS | PAGER_VARS


def test_role_values():
    e = entries()
    for name, value in EXPECTED.items():
        assert e[name] == value, name


def fish_env(tmp_path):
    env = isolated_env(tmp_path)
    fish_dir = Path(env["XDG_CONFIG_HOME"]) / "fish"
    (fish_dir / "themes").mkdir(parents=True)
    shutil.copy(THEME, fish_dir / "themes" / "deepwick.theme")
    (fish_dir / "config.fish").write_text(
        "fish_config theme choose deepwick\n"
        "set -g fish_greeting\n"
        "function fish_prompt; echo -n 'fish> '; end\n"
    )
    return env


@requires_fish
def test_config_fish_loads_theme(tmp_path):
    out = subprocess.run(
        ["fish", "-c", "echo $fish_color_comment; echo $fish_pager_color_selected_background"],
        env={**fish_env(tmp_path), "PATH": "/usr/bin:/bin"}, capture_output=True, text=True, check=True,
    ).stdout.lower()
    assert "7a86a8" in out and "--italics" in out
    assert "264f78" in out


@pytest.mark.skipif(not (tmux_available() and shutil.which("fish")), reason="requires tmux and fish")
def test_fish_highlights_command_line(tmp_path):
    text = capture("fish", fish_env(tmp_path), wait_for="fish>", literal='echo "hi" --flag word # note')
    assert style_of(text, "echo")["fg"] == C["yellow"].lower()
    assert style_of(text, '"hi"')["fg"] == C["orange"].lower()
    assert style_of(text, "--flag")["fg"] == C["lightBlue"].lower()
    assert style_of(text, "word")["fg"] == C["foreground"].lower()
    comment = style_of(text, "# note")
    assert comment["fg"] == C["comment"].lower() and comment["italic"]


@pytest.mark.skipif(not (tmux_available() and shutil.which("fish")), reason="requires tmux and fish")
def test_fish_highlights_unknown_command(tmp_path):
    text = capture("fish", fish_env(tmp_path), wait_for="fish>", literal="nosuchcommand_deepwick")
    assert style_of(text, "nosuchcommand_deepwick")["fg"] == C["red"].lower()


def test_port_conventions():
    assert check_port(REPO, PALETTE.allowed_hex()) == []
