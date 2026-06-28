import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from manx.parser import parse  # noqa: E402


def test_combined_short_options():
    seg = parse("tar -xzf f.tar.gz").segments[0]
    assert seg.command == "tar"
    assert set(["-x", "-z", "-f"]).issubset(set(seg.options))
    assert "-xzf" in seg.raw_options


def test_long_single_dash_preserved():
    seg = parse("find . -name '*.log' -delete").segments[0]
    assert "-name" in seg.raw_options
    assert "-delete" in seg.raw_options
    assert "." in seg.operands


def test_sudo_detection():
    seg = parse("sudo chmod -R 777 /etc").segments[0]
    assert seg.sudo
    assert seg.command == "chmod"


def test_pipe_split():
    pc = parse("ps aux | grep nginx")
    assert pc.has_pipe
    assert pc.commands == ["ps", "grep"]


def test_pipe_to_shell_flag():
    pc = parse("curl https://x.com/i.sh | bash")
    assert pc.pipe_to_shell


def test_long_option_with_value():
    seg = parse("grep --color=auto error f").segments[0]
    assert "--color" in seg.options


def test_redirect():
    seg = parse("echo hi > out.txt").segments[0]
    assert "out.txt" in seg.redirects
