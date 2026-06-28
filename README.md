# manx — 把 Linux 命令讲成人话

> **面向 Linux 新手的本地命令理解层。** 不是替代 `man`，而是 *explained man*：
> 把本机 `man` / `--help` / shell builtin help 解释成人话，带**风险提示**、**示例**、**报错解释**。

manx 解决的不是“让 AI 替你操作 Linux”，而是：

```
你不知道命令怎么用 → 它把 man 讲成人话
你不懂参数含义     → 它逐项解释
你不敢执行命令     → 它告诉你风险（规则引擎硬判定，不靠 LLM 猜）
你遇到报错         → 它告诉你下一步查什么
你想完成任务       → 它推荐本机可用的安全命令
```

## 特点

- **本机优先**：解释基于本机 `man` / `--help` / `type` / `whatis` 与系统上下文，减少幻觉、贴合你的发行版与命令版本。
- **安全规则硬编码**：危险命令（`rm -rf`、`chmod -R 777 /`、`dd of=/dev/*`、`curl | bash` 等）由规则引擎判定风险等级（0~4），**不交给 LLM**。
- **离线可用**：核心零依赖，内置高频命令知识卡片、报错库、场景库，没有 API key 也能用。
- **LLM 可选增强**：配置 `ANTHROPIC_API_KEY`（默认，Claude 原生）或 `OPENAI_API_KEY` 后，能结合本机文档自由解释更多命令；支持**第三方中转 / 自建网关**。发送前自动**脱敏**（key/token/密码/私钥）。
- **终端友好**：输出短、准、可复制，默认限制行数，适配窄终端。

---

## 快速开始

```bash
# 1. 安装（在项目根目录）
pip install -e .

# 2. 立刻试一条（无需 API key，走内置卡片）
manx tar

# 3. 看一条命令安不安全
manx explain "sudo rm -rf /var/log"

# 4. 不知道用啥命令，直接问
manx ask "怎么查 8080 端口被谁占用"
```

> 不想安装也行，直接从源码跑：
> ```bash
> PYTHONPATH=src python3 -m manx tar
> ```

装完后 `manx` 命令即可用。**没有 API key 一样能跑**，核心功能（解释 / 风险判定 / 报错 / 速查）全部离线可用；配了 key 只是解释更自由、能覆盖更多命令。

---

## 安装

```bash
pip install -e .          # 从源码安装，提供 manx 命令
```

可选 LLM 依赖（**不装也能跑**，会走内置 `urllib` HTTP 调用）：

```bash
pip install -e ".[anthropic]"   # 用官方 anthropic SDK
pip install -e ".[openai]"      # 用 OpenAI
```

---

## 用法

manx 有「直接给命令名」和「子命令」两种入口：

```bash
manx <命令>                    # 新手解释一个命令，如 manx tar
manx explain "<整条命令>"       # 解释整条命令并标注风险
manx ask "<想做什么>"           # 根据自然语言推荐本机可用命令
manx fix "<报错信息>"           # 解释报错并给安全排查步骤
manx option <命令> <参数>        # 解释某个参数，如 manx option tar -z
manx cheat <命令>               # 只看常用示例（速查）
manx compare <命令1> <命令2>     # 对比两个命令
manx help                       # 或 manx -h，查看用法
```

### 五个典型场景

| 你想干嘛 | 敲这个 |
|----------|--------|
| 这命令是啥、怎么用 | `manx grep` |
| 这条命令执行了会怎样、安不安全 | `manx explain "find . -name '*.log' -delete"` |
| 我想完成某件事，但不知道用啥命令 | `manx ask "怎么打包整个目录成 tar.gz"` |
| 跑出来一个报错看不懂 | `manx fix "Address already in use"` |
| 某个参数到底啥意思 | `manx option find -mtime` |

### 模式与开关

开关可以放在任意位置，例如 `manx tar --short` 或 `manx --json explain "rm -rf x"`。

| 开关 | 作用 |
|------|------|
| `--beginner`（默认） / `--short` / `--pro` | 新手 / 精简 / 老手 输出 |
| `--json` | 结构化输出，便于集成（自动关闭 LLM 增强） |
| `--full` | 不截断输出（解除行数限制） |
| `--no-llm`（= `--offline`） | 强制纯离线（只用卡片 + 规则） |
| `--color=auto\|always\|never` | 颜色控制 |
| `--version` / `-h`、`--help` | 版本 / 帮助 |

---

## 启用 LLM 增强（可选）

manx 默认离线就能用。配了 key 之后，遇到没有内置卡片的命令也能结合本机 man/help 自由解释。

### 1. 设置 API key —— **只认环境变量**（不能写进配置文件）

```bash
# 默认：Anthropic（Claude）
export ANTHROPIC_API_KEY="sk-ant-..."

# 或者：OpenAI
export OPENAI_API_KEY="sk-..."
```

写进 `~/.zshrc` / `~/.bashrc` 即可长期生效。`MANX_API_KEY` 是通用兜底（设了它默认按 Anthropic 试）。

### 2. 选 provider / 模型（配置文件或环境变量）

```toml
# ~/.config/manx/config.toml
llm_provider = "auto"     # auto（优先 Claude）| anthropic | openai | none
# llm_model  = ""         # 留空用默认；Anthropic 默认 claude-haiku-4-5
```

### 3. 用第三方中转 / 自建网关（自定义 base）

不想用官方 endpoint 时，填一个 base_url 即可，对 anthropic / openai 两种协议都生效：

```toml
# ~/.config/manx/config.toml
llm_base_url = "https://relay.example.com/v1"
```

或用环境变量（优先级更高）：

```bash
export MANX_BASE_URL="https://relay.example.com/v1"
# 也兼容标准变量：
export OPENAI_BASE_URL="https://relay.example.com/v1"
export ANTHROPIC_BASE_URL="https://relay.example.com"
```

base_url 填 `https://host`、`https://host/`、`https://host/v1` 三种写法都行，不会出现 `/v1/v1` 重复。
优先级：`llm_base_url` / `MANX_BASE_URL` > `OPENAI_BASE_URL` / `ANTHROPIC_BASE_URL` > 官方默认。

### 4. 验证是否接上

```bash
manx ls            # 有 key 时带 LLM 增强解释
manx ls --no-llm   # 强制纯离线，对比一下两者输出
```

两条输出不一样就说明 LLM 生效了。调用失败 / 无 key 会**自动降级**到离线卡片，不报错。

---

## 风险分级

| 等级 | 含义 | 例子 |
|------|------|------|
| 0 无风险 | 只读查询 | `ls`、`ss -lntp`、`ps aux` |
| 1 低 | 普通用户可控 | `mkdir`、`touch`、`tar -xzf` |
| 2 中 | 可能覆盖/删除/移动 | `rm file`、`mv a b` |
| 3 高 | 递归删除/改权限、sudo 改系统、停服务 | `rm -r dir`、`sudo systemctl stop nginx`、`curl\|bash` |
| 4 极高 | 可能破坏系统/磁盘/安全边界 | `sudo rm -rf /`、`chmod -R 777 /etc`、`dd of=/dev/sda` |

风险等级由规则引擎给出；启用 LLM 时，LLM 只负责把原因讲清楚，**不能改写等级**。

---

## 配置参考

`~/.config/manx/config.toml`（完整示例见 `config.example.toml`）。配置文件**可选**，不创建就用内置默认值。

```toml
language = "zh-CN"        # 输出语言
mode = "beginner"        # beginner | short | pro
llm_provider = "auto"    # auto | anthropic | openai | none
# llm_model = ""         # 留空按 provider 取默认
# llm_base_url = ""      # 第三方中转/自建网关；留空用官方 base
offline_first = true     # 优先离线，有 key 再增强
risk_guard = true        # 启用危险命令规则
max_output_lines = 80    # 终端最大输出行数（--full 解除）
color = "auto"           # auto | always | never
```

环境变量（优先级高于配置文件）：

| 变量 | 对应 | 说明 |
|------|------|------|
| `MANX_LANG` | language | 输出语言 |
| `MANX_MODE` | mode | beginner / short / pro |
| `MANX_LLM_PROVIDER` | llm_provider | auto / anthropic / openai / none |
| `MANX_LLM_MODEL` | llm_model | 指定模型 |
| `MANX_BASE_URL` | llm_base_url | 自定义 API base |
| `MANX_API_KEY` | — | 通用 API key 兜底 |
| `MANX_COLOR` | color | 颜色 |
| `MANX_OFFLINE` | offline_first | `1`/`true` 强制离线 |

> 配置目录遵循 XDG 规范，可用 `XDG_CONFIG_HOME` 整体重定向。

---

## 架构

```
CLI 层 (cli.py)
  → 意图分发 (commands/*)
  → 本机资料采集 (collectors.py：man/--help/type/whatis)
  → 命令解析   (parser.py：管道/重定向/sudo/短参组合/长参)
  → 风险规则   (risk.py：硬编码，安全核心)
  → 知识卡片   (cards.py + data/cards/*.json)
  → LLM 解释   (llm.py：可选，带防幻觉约束与脱敏)
  → 输出渲染   (render.py：颜色/风险色/行数控制)
```

## 隐私

默认只把必要文本发给 LLM（用户输入、命令名、man/help 片段、发行版信息）。**不上传** 环境变量、shell history、SSH key、token、`.env`、私有文件内容。发送前对 key/token/密码/私钥自动脱敏。

## 测试

```bash
python3 -m pytest tests/     # 若无 pytest，见 tests/ 顶部说明可直接 import 运行
```

## 当前覆盖

内置卡片：`grep find tar rm chmod chown ls ps ss curl kill systemctl journalctl`（持续扩充）。
报错库 16 条高频错误；场景库 12 类常见任务。
