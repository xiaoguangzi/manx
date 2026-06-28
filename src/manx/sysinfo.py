"""系统上下文采集：只读、零修改。用于减少幻觉、按发行版/包管理器给建议。"""

from __future__ import annotations

import os
import platform
import shutil
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Dict, List, Optional

PKG_MANAGERS = ["apt", "dnf", "yum", "pacman", "zypper", "brew", "apk"]


@dataclass
class SysInfo:
    system: str = ""              # Linux / Darwin
    machine: str = ""             # x86_64 / arm64
    distro: str = ""              # ubuntu / debian / fedora / arch / macos ...
    distro_pretty: str = ""
    shell: str = ""
    pkg_managers: List[str] = field(default_factory=list)

    @property
    def is_macos(self) -> bool:
        return self.system == "Darwin"

    @property
    def primary_pkg_manager(self) -> Optional[str]:
        return self.pkg_managers[0] if self.pkg_managers else None

    def as_prompt_context(self) -> str:
        lines = [
            f"操作系统: {self.system} ({self.machine})",
            f"发行版: {self.distro_pretty or self.distro or '未知'}",
            f"Shell: {self.shell or '未知'}",
            f"可用包管理器: {', '.join(self.pkg_managers) or '未检测到'}",
        ]
        return "\n".join(lines)


def _read_os_release() -> Dict[str, str]:
    data: Dict[str, str] = {}
    path = "/etc/os-release"
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" not in line or line.startswith("#"):
                    continue
                k, _, v = line.partition("=")
                data[k] = v.strip().strip('"')
    except OSError:
        pass
    return data


@lru_cache(maxsize=1)
def collect() -> SysInfo:
    info = SysInfo()
    info.system = platform.system()
    info.machine = platform.machine()
    info.shell = os.path.basename(os.environ.get("SHELL", "")) or ""

    if info.system == "Darwin":
        info.distro = "macos"
        ver = platform.mac_ver()[0]
        info.distro_pretty = f"macOS {ver}".strip()
    else:
        osr = _read_os_release()
        info.distro = (osr.get("ID") or "").lower()
        info.distro_pretty = osr.get("PRETTY_NAME") or osr.get("NAME") or ""

    info.pkg_managers = [p for p in PKG_MANAGERS if shutil.which(p)]
    return info
