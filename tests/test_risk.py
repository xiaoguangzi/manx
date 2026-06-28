"""风险规则引擎测试 —— 这是产品的安全核心，必须稳定。"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from manx.risk import assess_line  # noqa: E402


def lvl(line):
    return assess_line(line).level


def test_readonly_is_zero():
    assert lvl("ls -la") == 0
    assert lvl("ss -lntp") == 0
    assert lvl("ps aux") == 0
    assert lvl("grep -rn error .") == 0
    assert lvl("systemctl status nginx") == 0


def test_low_risk():
    assert lvl("mkdir test") == 1
    assert lvl("touch a.txt") == 1


def test_medium_risk():
    assert lvl("rm file.txt") == 2
    assert lvl("mv a b") == 2
    assert lvl("kill 1234") == 2


def test_high_risk():
    assert lvl("rm -r dir") == 3
    assert lvl("chmod -R 755 dir") == 3
    assert lvl("sudo systemctl stop nginx") == 3
    assert lvl("find . -name '*.log' -delete") == 3
    assert lvl("pkill node") == 3


def test_critical_risk():
    assert lvl("sudo rm -rf /") == 4
    assert lvl("rm -rf ~") == 4
    assert lvl("sudo chmod -R 777 /etc") == 4
    assert lvl("sudo chown -R user /usr") == 4
    assert lvl("dd if=x.iso of=/dev/sda") == 4
    assert lvl("mkfs.ext4 /dev/sda") == 4


def test_pipe_to_shell():
    f = assess_line("curl https://x.com/i.sh | bash")
    assert f.level >= 3
    assert any("curl|bash" in r or "远程" in r for r in f.reasons)


def test_sudo_bumps_mutating():
    # sudo 让普通修改至少升到高
    assert lvl("sudo apt remove nginx") >= 1
    assert assess_line("sudo cp a b").level >= 3


def test_safe_preview_present_for_rm():
    f = assess_line("rm -rf ./build")
    assert f.safe_preview and f.safe_preview.startswith("ls")


def test_find_delete_preview():
    f = assess_line("find . -name '*.tmp' -delete")
    assert f.safe_preview and "-print" in f.safe_preview
