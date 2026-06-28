"""manx CLI 入口。

用法：
  manx <cmd>                    命令新手解释
  manx explain "<command line>" 解释整条命令 + 风险
  manx ask "<自然语言>"          根据描述推荐命令
  manx fix "<报错信息>"          解释报错 + 排查步骤
  manx option <cmd> <option>    解释某个参数
  manx cheat <cmd>              只看常用示例（速查）
  manx compare <cmd1> <cmd2>    对比两个命令

全局开关：
  --short        精简模式      --pro     老手模式      --beginner 新手模式(默认)
  --json         JSON 输出     --full    不截断输出
  --no-llm       禁用 LLM（纯离线卡片/规则）
  --color=auto|always|never    --version    -h/--help
"""

from __future__ import annotations

import sys
from typing import List, Tuple

from manx import __version__
from manx.commands import ask as ask_cmd
from manx.commands import cmd as cmd_cmd
from manx.commands import explain as explain_cmd
from manx.commands import fix as fix_cmd
from manx.commands import option as option_cmd
from manx.commands.base import Context
from manx.config import load_config
from manx.render import Renderer
from manx.sysinfo import collect as collect_sysinfo

SUBCOMMANDS = {"explain", "ask", "fix", "option", "cheat", "compare", "help"}

USAGE = """manx — 把 Linux 命令讲成人话（带风险提示、报错解释）

用法：
  manx <命令>                    新手解释一个命令，如 manx tar
  manx explain "<整条命令>"       解释整条命令并标注风险
  manx ask "<想做什么>"           根据自然语言推荐命令
  manx fix "<报错信息>"           解释报错并给排查步骤
  manx option <命令> <参数>        解释某个参数，如 manx option tar -z
  manx cheat <命令>               只看常用示例
  manx compare <命令1> <命令2>     对比两个命令

模式：  --beginner(默认) --short --pro
输出：  --json  --full  --no-llm  --color=auto|always|never
其他：  --version   -h/--help

示例：
  manx grep
  manx tar --short
  manx explain "sudo chmod -R 777 /usr"
  manx ask "怎么查 8080 端口被谁占用"
  manx fix "Address already in use"
  manx option find -mtime
"""


def _split_flags(argv: List[str]) -> Tuple[List[str], dict]:
    """从任意位置抽出全局开关，返回 (位置参数, 选项字典)。"""
    positional: List[str] = []
    opts = {
        "mode": None, "json": False, "full": False, "no_llm": False,
        "color": None, "help": False, "version": False,
    }
    for a in argv:
        if a == "--short":
            opts["mode"] = "short"
        elif a == "--pro":
            opts["mode"] = "pro"
        elif a == "--beginner":
            opts["mode"] = "beginner"
        elif a == "--json":
            opts["json"] = True
        elif a == "--full":
            opts["full"] = True
        elif a in ("--no-llm", "--offline"):
            opts["no_llm"] = True
        elif a.startswith("--color="):
            opts["color"] = a.split("=", 1)[1]
        elif a == "--color":
            opts["color"] = "always"
        elif a in ("-h", "--help"):
            opts["help"] = True
        elif a in ("-V", "--version"):
            opts["version"] = True
        else:
            positional.append(a)
    return positional, opts


def _build_context(opts: dict) -> Context:
    cfg = load_config()
    if opts["mode"]:
        cfg.mode = opts["mode"]
    if opts["color"]:
        cfg.color = opts["color"]
    if opts["full"]:
        cfg.max_output_lines = 0

    renderer = Renderer(color=cfg.color, max_lines=cfg.max_output_lines)
    return Context(
        config=cfg,
        sysinfo=collect_sysinfo(),
        renderer=renderer,
        mode=cfg.mode,
        as_json=opts["json"],
        full=opts["full"],
        no_llm=opts["no_llm"],
    )


def _cheat(ctx: Context, name: str) -> int:
    from manx import cards
    r = ctx.renderer
    card = cards.get_card(name)
    if not card:
        # 退化为普通解释
        return cmd_cmd.run(ctx, name)
    lines = [f"{r.cmd(name)} 速查："]
    for e in card.common_tasks:
        lines.append("  " + r.cmd(e.cmd) + (("  " + r.c(e.desc, "\033[2m")) if e.desc else ""))
    r.emit(lines)
    return 0


def _compare(ctx: Context, a: str, b: str) -> int:
    from manx import cards
    r = ctx.renderer
    if ctx.llm_enabled():
        prompt = (f"对比 Linux 命令 {a} 和 {b}：各自用途、典型场景、何时用哪个。"
                  f"面向新手，简洁，给少量例子。系统：{ctx.sysinfo.distro_pretty}")
        text = ctx.ask_llm(prompt)
        if text:
            r.emit(text.splitlines())
            return 0
    # 离线：并排展示两张卡片要点
    lines = []
    for name in (a, b):
        card = cards.get_card(name)
        lines.append(r.heading(f"== {name} =="))
        if card:
            lines.append("  " + card.purpose)
            for e in card.common_tasks[:3]:
                lines.append("  " + r.cmd(e.cmd))
        else:
            lines.append(r.c("  （没有内置卡片，启用 LLM 可获得对比）", "\033[2m"))
        lines.append("")
    r.emit(lines)
    return 0


def main(argv: List[str] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    positional, opts = _split_flags(argv)

    if opts["version"]:
        print(f"manx {__version__}")
        return 0
    if opts["help"] or not positional or positional[0] == "help":
        sys.stdout.write(USAGE)
        return 0

    ctx = _build_context(opts)
    head = positional[0]
    rest = positional[1:]

    try:
        if head == "explain":
            if not rest:
                print('用法：manx explain "<整条命令>"'); return 2
            return explain_cmd.run(ctx, " ".join(rest))
        if head == "ask":
            if not rest:
                print('用法：manx ask "<想做什么>"'); return 2
            return ask_cmd.run(ctx, " ".join(rest))
        if head == "fix":
            if not rest:
                print('用法：manx fix "<报错信息>"'); return 2
            return fix_cmd.run(ctx, " ".join(rest))
        if head == "option":
            if len(rest) < 2:
                print("用法：manx option <命令> <参数>，如 manx option tar -z"); return 2
            return option_cmd.run(ctx, rest[0], rest[1])
        if head == "cheat":
            if not rest:
                print("用法：manx cheat <命令>"); return 2
            return _cheat(ctx, rest[0])
        if head == "compare":
            if len(rest) < 2:
                print("用法：manx compare <命令1> <命令2>"); return 2
            return _compare(ctx, rest[0], rest[1])

        # 默认：manx <cmd>
        return cmd_cmd.run(ctx, head)
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
