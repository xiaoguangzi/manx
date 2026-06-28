下面是一版可以直接放进仓库的 PRD。定位我先定成：**不做 UI、不做桌宠、不做自动运维，先做一个面向 Linux 新手的 CLI man 智能解释器**。

# PRD：ManCoach — 面向 Linux 新手的 CLI 命令理解助手

## 1. 产品概述

### 1.1 产品名称

暂定名：**ManCoach**

也可选：

* `manx`
* `cmdcoach`
* `shellsense`
* `manguide`
* `howman`

本文统一使用 `manx` 作为 CLI 命令名。

### 1.2 产品一句话定位

**把 Linux 的 man page、--help、shell builtin help 解释成人话，帮助新手理解命令、参数、报错和风险。**

### 1.3 产品核心价值

Linux 文档并不缺，真正的问题是：

* 新手不知道该查哪个命令。
* 新手看不懂 man page 的组织方式。
* man page 很多是参考手册，不是教程。
* 新手不知道参数怎么组合。
* 新手不知道命令执行后会影响什么。
* 网上教程经常直接给危险命令，新手无法判断风险。
* ChatGPT 容易给出本机不存在的参数、错误发行版命令或危险操作。

`manx` 的目标不是取代 man，而是把 man 变成：

> **按任务组织、带风险提示、带示例、能解释报错的 Linux 新手教练。**

---

## 2. 背景与问题

### 2.1 Linux 新手的典型痛点

#### 痛点 1：man page 太像字典，不像教程

例如 `man tar`、`man find`、`man grep` 内容很长，新手不知道最常用的是哪几个场景。

新手真正想问的是：

* 怎么解压 `.tar.gz`？
* 怎么找大文件？
* 怎么查端口占用？
* 怎么递归搜索文本？
* 怎么安全删除旧日志？

而不是完整阅读几十页 man page。

#### 痛点 2：参数语义难理解

例如：

```bash
tar -xzf file.tar.gz
```

新手看到的是一串缩写：

```text
-x -z -f
```

但他需要知道：

* `-x` 是 extract，表示解包。
* `-z` 是 gzip。
* `-f` 后面必须跟文件名。
* 参数顺序一般不重要，但 `-f` 后面的文件名位置很重要。

#### 痛点 3：命令风险不可见

新手无法判断这些命令的危险程度：

```bash
rm -rf *
chmod -R 777 .
sudo chown -R $USER /usr
dd if=xxx.iso of=/dev/sda
curl https://example.com/install.sh | bash
find . -name "*.log" -delete
```

尤其是网上教程喜欢直接给：

```bash
sudo rm -rf /var/lib/dpkg/lock
chmod -R 777 project
curl xxx | sh
```

新手不知道后果。

#### 痛点 4：报错信息难理解

例如：

```text
Permission denied
command not found
No such file or directory
Address already in use
Could not get lock /var/lib/dpkg/lock-frontend
tar: Cowardly refusing to create an empty archive
```

这些错误并不复杂，但新手不知道下一步该查什么。

#### 痛点 5：普通 AI 容易脱离本机环境

普通 AI 经常：

* 推荐用户没有安装的命令。
* 给错发行版包管理器。
* 编造不存在的参数。
* 忽略 shell builtin 与外部命令区别。
* 对危险命令没有强约束。
* 输出太长，不适合终端阅读。

`manx` 应该利用本机上下文解决这些问题。

---

## 3. 产品目标

### 3.1 MVP 目标

第一版只解决一个核心问题：

> **让 Linux 新手能看懂、敢用、少踩坑地使用常见命令。**

MVP 不做自动修复，不做复杂 Agent，不做桌面 UI，不做长期后台进程。

### 3.2 核心目标

1. **解释命令用途**

   * 用户输入 `manx tar`，输出 tar 的新手用法，而不是完整 man。

2. **解释完整命令行**

   * 用户输入 `manx explain "find . -name '*.log' -delete"`，解释每个部分的含义和风险。

3. **根据自然语言找命令**

   * 用户输入 `manx ask "怎么查看 8080 端口被谁占用"`，输出推荐命令和解释。

4. **解释报错**

   * 用户输入 `manx fix "Permission denied"`，输出可能原因和安全排查步骤。

5. **识别危险命令**

   * 对删除、权限、磁盘、sudo、管道执行脚本等操作做硬规则提示。

6. **基于本机信息回答**

   * 优先读取本机 `man`、`--help`、`help`、`type`、`which`、`/etc/os-release`，减少幻觉。

---

## 4. 目标用户

### 4.1 主要用户

#### Linux 新手

特征：

* 刚开始使用 Ubuntu / Debian / Fedora / Arch。
* 会复制命令，但不理解命令。
* 遇到报错只会搜索。
* 对 `sudo`、权限、路径、包管理器不熟。
* 看 man page 会放弃。

典型需求：

```bash
manx tar
manx explain "sudo apt install nginx"
manx ask "怎么查端口占用"
manx fix "Permission denied"
```

#### 编程入门用户

特征：

* 会写一点代码。
* 经常需要用终端安装依赖、跑服务、查端口、解压文件、改权限。
* 不想系统性学 Linux，但需要够用。

典型需求：

```bash
manx ask "怎么查 node 服务是不是启动了"
manx ask "怎么把当前目录打包成 tar.gz"
manx explain "chmod +x ./install.sh"
```

#### 运维学习者

特征：

* 正在学习 Linux 基础、云服务器、Docker、Kubernetes。
* 需要理解 `systemctl`、`journalctl`、`ss`、`ps`、`top` 等命令。

典型需求：

```bash
manx systemctl
manx journalctl
manx ask "怎么查看 nginx 为什么启动失败"
```

---

## 5. 非目标用户

MVP 阶段不主要服务：

* 高级 Linux 内核开发者。
* 资深 SRE 的复杂生产故障排查。
* 红队/渗透测试自动化。
* 自动改系统配置的运维 Agent。
* 图形化桌面助手用户。
* 需要中文外包教程式长篇解释的人。

产品要避免变成“终端里的 ChatGPT 大杂烩”。

---

## 6. 产品原则

### 6.1 本机优先

所有解释优先基于本机：

```bash
man <cmd>
<cmd> --help
help <builtin>
type <cmd>
which <cmd>
whatis <cmd>
apropos <keyword>
/etc/os-release
```

原因：

* 不同发行版命令不同。
* GNU / BSD 命令参数不同。
* shell builtin 和外部命令不同。
* 用户机器上不一定安装某个工具。

### 6.2 解释优先，不自动执行

MVP 默认不执行修改性命令。

允许自动执行的只读命令：

```bash
type <cmd>
which <cmd>
man <cmd>
<cmd> --help
help <cmd>
whatis <cmd>
apropos <keyword>
uname -a
cat /etc/os-release
```

不自动执行：

```bash
rm
mv
cp
chmod
chown
dd
mkfs
fdisk
apt install
systemctl restart
curl | bash
```

### 6.3 安全规则硬编码

风险判断不能完全交给 LLM。

LLM 可以解释风险，但风险识别必须由规则引擎完成。

### 6.4 输出短、准、可复制

终端输出不能像聊天机器人一样废话。

默认输出结构：

```text
作用：
常用：
参数：
例子：
风险：
常见坑：
下一步：
```

### 6.5 不编造参数

当本机 man / help 中找不到某个参数时，必须明确说：

```text
我没有在本机文档中找到这个参数。
可能是版本差异，建议运行：<cmd> --help
```

不能硬编。

---

## 7. 产品范围

### 7.1 MVP 范围

MVP 支持 5 个核心入口：

```bash
manx <cmd>
manx explain "<command line>"
manx ask "<natural language>"
manx fix "<error message>"
manx option <cmd> <option>
```

### 7.2 MVP 首批重点命令

第一批建议支持 25 个命令：

#### 文件与目录

```text
ls
cd
pwd
cp
mv
rm
mkdir
touch
cat
less
head
tail
```

#### 文本处理

```text
grep
find
sed
awk
xargs
sort
uniq
wc
```

#### 压缩解压

```text
tar
gzip
gunzip
zip
unzip
```

#### 权限

```text
chmod
chown
sudo
su
```

#### 进程与端口

```text
ps
top
kill
ss
lsof
```

#### 系统服务

```text
systemctl
journalctl
```

#### 网络

```text
curl
wget
ping
ip
ssh
scp
```

#### 包管理

MVP 可先支持 Debian/Ubuntu：

```text
apt
dpkg
```

后续支持：

```text
dnf
yum
pacman
zypper
brew
```

---

## 8. 核心功能需求

## 8.1 `manx <cmd>`：命令新手解释

### 功能描述

用户输入一个命令名，`manx` 输出该命令的用途、常见任务、常用参数、例子、风险和坑。

### 示例

输入：

```bash
manx tar
```

输出：

```text
tar：打包和解包文件。

最常用场景：

1. 解压 .tar.gz
   tar -xzf file.tar.gz

2. 创建 .tar.gz 压缩包
   tar -czf backup.tar.gz ./dir

3. 查看压缩包内容
   tar -tzf file.tar.gz

4. 解压到指定目录
   tar -xzf file.tar.gz -C /tmp

常用参数：
-x  解包，extract
-c  创建压缩包，create
-z  使用 gzip
-f  后面跟文件名
-v  显示过程
-C  指定解压目录

新手坑：
- -f 后面一般要紧跟文件名。
- -x 是解包，-c 是创建，不要混用。
- .tar.gz 常用 -z，.tar.xz 常用 -J。
```

### 需求细节

* 优先读取 `man tar` 和 `tar --help`。
* 如果命令不存在，提示安装建议，但不自动安装。
* 如果命令是 shell builtin，使用 `help <cmd>`。
* 输出不超过 80 行。
* 默认新手模式。
* 支持 `--pro` 输出精简老手版。

---

## 8.2 `manx explain "<command line>"`：解释完整命令

### 功能描述

解释一整条命令的结构、参数、执行效果、风险和安全替代方案。

### 示例

输入：

```bash
manx explain "find . -name '*.log' -mtime +7 -delete"
```

输出：

```text
这条命令会在当前目录下查找并删除旧日志文件。

结构解释：
find .              从当前目录开始查找
-name '*.log'       匹配文件名以 .log 结尾的文件
-mtime +7           修改时间超过 7 天
-delete             删除找到的文件

风险：中高

原因：
- 包含 -delete，会真实删除文件。
- 搜索范围是当前目录及其子目录。
- 如果当前目录选错，可能误删文件。

建议先预览：

find . -name '*.log' -mtime +7 -print

确认结果无误后，再执行带 -delete 的版本。
```

### 需求细节

需要解析：

* 命令名
* 参数
* 短参数组合，例如 `tar -xzf`
* 长参数，例如 `--recursive`
* 管道，例如 `ps aux | grep nginx`
* 重定向，例如 `> file`
* sudo
* 通配符
* 引号
* shell 变量
* 命令替换，例如 `$(...)`
* 危险操作

MVP 可以先不支持复杂 Bash AST，但要支持常见解析。

### 风险识别要求

以下命令必须提示风险：

```text
rm
chmod
chown
dd
mkfs
fdisk
parted
mount
umount
systemctl restart/stop/disable
kill
pkill
iptables
ufw
curl | bash
wget | sh
sudo tee /etc/*
```

---

## 8.3 `manx ask "<natural language>"`：自然语言找命令

### 功能描述

用户用中文或英文描述想做什么，`manx` 推荐合适命令，并解释参数。

### 示例 1

输入：

```bash
manx ask "怎么查看 8080 端口被谁占用"
```

输出：

```text
推荐命令：

ss -lntp | grep ':8080'

含义：
ss        查看 socket/网络连接
-l        只看监听中的端口
-n        显示数字端口，不解析域名
-t        只看 TCP
-p        显示进程信息

如果没有权限看到进程名，可以尝试：

sudo ss -lntp | grep ':8080'

风险：低
这是只读查询命令，不会修改系统。
```

### 示例 2

输入：

```bash
manx ask "怎么找当前目录下大于 100M 的文件"
```

输出：

```text
推荐命令：

find . -type f -size +100M

含义：
find .        从当前目录开始查找
-type f       只查普通文件
-size +100M   文件大小大于 100MB

如果想显示详细大小：

find . -type f -size +100M -exec ls -lh {} \;
```

### 需求细节

* 需要根据本机命令是否存在选择方案。
* 优先选择新手可理解、安全、通用的命令。
* 不优先推荐复杂 one-liner。
* 不推荐危险命令作为第一答案。
* 如果任务涉及删除、覆盖、格式化、权限修改，必须先给只读预览命令。

---

## 8.4 `manx fix "<error message>"`：解释报错

### 功能描述

用户粘贴报错信息，`manx` 解释可能原因，并给出安全排查步骤。

### 示例 1

输入：

```bash
manx fix "Permission denied"
```

输出：

```text
Permission denied 表示权限不足。

常见原因：
1. 当前用户没有读取/写入/执行目标文件的权限。
2. 目标目录属于 root 或其他用户。
3. 脚本没有执行权限。
4. 你正在访问系统目录，例如 /etc、/usr、/var。

安全排查：

1. 查看文件权限：
   ls -l <file>

2. 查看当前用户：
   whoami

3. 如果是脚本不能执行：
   chmod +x <script.sh>

4. 如果是系统目录，不要直接 chmod -R 777。
   请先确认你真正想修改哪个文件。
```

### 示例 2

输入：

```bash
manx fix "Address already in use"
```

输出：

```text
Address already in use 表示端口已经被占用。

排查端口 8080：

ss -lntp | grep ':8080'

如果看到某个进程正在监听，说明端口被它占用了。

常见解决方式：
1. 改你的服务端口。
2. 停掉占用端口的服务。
3. 确认不是同一个服务重复启动。

不要直接 kill 进程，先确认它是什么。
```

### MVP 内置高频错误

```text
Permission denied
command not found
No such file or directory
Address already in use
Connection refused
Connection timed out
Could not resolve host
Temporary failure in name resolution
No space left on device
Read-only file system
Device or resource busy
Operation not permitted
Too many open files
Broken pipe
Segmentation fault
Could not get lock /var/lib/dpkg/lock-frontend
dpkg was interrupted
tar: Cowardly refusing to create an empty archive
```

---

## 8.5 `manx option <cmd> <option>`：参数解释

### 功能描述

解释某个命令的某个参数。

### 示例

输入：

```bash
manx option tar -z
```

输出：

```text
tar -z：使用 gzip 压缩或解压。

常见组合：

创建 .tar.gz：
tar -czf backup.tar.gz ./dir

解压 .tar.gz：
tar -xzf backup.tar.gz

注意：
- -z 适合 .gz / .tar.gz。
- .tar.xz 通常用 -J。
- .tar.bz2 通常用 -j。
```

### 需求细节

* 必须从本机 man/help 中确认参数存在。
* 如果参数不存在，要提示可能是版本差异。
* 支持短参数和长参数：

  * `-r`
  * `-R`
  * `--recursive`
  * `--exclude`

---

## 9. 输出模式

### 9.1 默认模式：新手解释

适合初学者。

```bash
manx grep
```

输出结构：

```text
作用：
最常用：
参数：
例子：
常见坑：
```

### 9.2 精简模式

```bash
manx grep --short
```

输出：

```text
grep：搜索文本。

常用：
grep "error" app.log
grep -r "error" .
grep -in "error" app.log

参数：
-r 递归
-i 忽略大小写
-n 行号
-v 反向匹配
```

### 9.3 老手模式

```bash
manx find --pro
```

输出：

```text
find 常用组合：

find . -type f -name "*.log"
find . -type f -mtime +7
find . -type f -size +100M
find . -type f -print0 | xargs -0 grep -H "error"
find . -type f -exec grep -H "error" {} \;

危险：
-delete
-exec rm
```

### 9.4 JSON 模式

给后续集成用。

```bash
manx explain "rm -rf ./tmp" --json
```

输出：

```json
{
  "command": "rm",
  "summary": "删除 ./tmp 目录及其内容",
  "risk": "high",
  "dangerous_parts": ["-r", "-f"],
  "safe_preview": "ls -la ./tmp",
  "recommendation": "确认路径后再删除"
}
```

---

## 10. 风险分级

### 10.1 风险等级

#### Level 0：无风险

只读查询，不修改系统。

例子：

```bash
ls
pwd
cat file
grep "x" file
ss -lntp
ps aux
df -h
```

#### Level 1：低风险

普通用户范围内操作，可控。

例子：

```bash
mkdir test
touch a.txt
cp a.txt b.txt
tar -xzf file.tar.gz
```

#### Level 2：中风险

可能覆盖、删除、移动文件。

例子：

```bash
rm file
mv a b
cp file existing_file
find . -delete
```

#### Level 3：高风险

递归删除、递归改权限、sudo 修改系统、停止服务。

例子：

```bash
rm -rf dir
chmod -R 777 .
sudo apt remove xxx
sudo systemctl stop nginx
```

#### Level 4：极高风险

可能破坏系统、磁盘、启动项、安全边界。

例子：

```bash
sudo rm -rf /
sudo chmod -R 777 /etc
sudo chown -R $USER /usr
dd if=xxx of=/dev/sda
mkfs.ext4 /dev/sda
curl xxx | bash
wget xxx -O- | sh
```

### 10.2 风险输出格式

```text
风险：高

原因：
- 使用 sudo，会以管理员权限执行。
- 使用 -R，会递归影响子目录。
- 目标路径 /usr 是系统目录。

建议：
不要直接执行。
请说明你真正想解决的问题。
```

---

## 11. 数据来源

### 11.1 本机文档来源

优先级：

1. `type <cmd>`
2. shell builtin：`help <cmd>`
3. 外部命令：`man <cmd>`
4. `<cmd> --help`
5. `whatis <cmd>`
6. `apropos <keyword>`
7. `/usr/share/doc`
8. 内置命令知识库

### 11.2 系统上下文

MVP 启动时可收集只读信息：

```bash
uname -s
uname -m
cat /etc/os-release
echo $SHELL
type apt/dnf/pacman/brew
```

用于判断：

* 操作系统
* 发行版
* 包管理器
* shell 类型
* 命令是否存在

### 11.3 内置知识库

对于高频命令，维护结构化卡片。

示例：

```yaml
command: grep
purpose: 搜索文本内容
common_tasks:
  - 在文件中搜索关键词
  - 递归搜索目录
  - 忽略大小写
  - 显示行号
common_options:
  - option: -r
    meaning: 递归搜索目录
  - option: -i
    meaning: 忽略大小写
  - option: -n
    meaning: 显示行号
risks:
  - grep 本身通常是只读低风险
common_mistakes:
  - 忘记给目录搜索加 -r
  - 正则特殊字符没有转义
```

---

## 12. LLM 使用策略

### 12.1 LLM 角色

LLM 负责：

* 把 man/help 内容解释成人话。
* 把参数组合转换成任务说明。
* 根据用户自然语言匹配命令。
* 把报错转换成排查路径。
* 生成简洁示例。

LLM 不负责：

* 最终风险等级判断。
* 是否允许执行命令。
* 是否确认参数存在。
* 是否判断系统路径危险。
* 是否自动修改系统。

### 12.2 防幻觉策略

必须给 LLM 提供约束：

```text
只能基于以下资料回答：
1. 本机 man/help 输出
2. 内置命令卡片
3. 系统上下文
4. 用户输入

如果资料不足，明确说不知道，不要编造。
```

### 12.3 参数存在性校验

如果 LLM 输出了命令参数，系统需要校验：

* 该参数是否出现在 man/help 中。
* 是否属于内置知识库。
* 是否为常见 POSIX/GNU 参数。

校验失败时，输出：

```text
注意：我没有在本机文档中确认该参数，可能存在版本差异。
```

---

## 13. CLI 设计

### 13.1 命令结构

```bash
manx <cmd>
manx explain "<command line>"
manx ask "<question>"
manx fix "<error>"
manx option <cmd> <option>
manx compare <cmd1> <cmd2>
manx cheat <cmd>
```

### 13.2 示例

```bash
manx grep
manx tar --short
manx find --pro
manx explain "chmod -R 777 /usr"
manx ask "怎么查 8080 端口"
manx fix "No space left on device"
manx option find -mtime
manx compare curl wget
manx cheat systemctl
```

### 13.3 配置文件

路径：

```bash
~/.config/manx/config.toml
```

示例：

```toml
language = "zh-CN"
mode = "beginner"
llm_provider = "openai"
offline_first = true
risk_guard = true
max_output_lines = 80
```

### 13.4 环境变量

```bash
MANX_LANG=zh-CN
MANX_MODE=beginner
MANX_LLM_PROVIDER=openai
MANX_API_KEY=...
```

---

## 14. 典型用户流程

### 14.1 查询命令用法

```text
用户输入：manx grep
系统读取：type grep、man grep、grep --help
系统解析：提取用途、参数、示例
系统输出：新手可读说明
```

### 14.2 解释危险命令

```text
用户输入：manx explain "sudo chmod -R 777 /etc"
系统解析：sudo、chmod、-R、777、/etc
规则引擎：命中极高风险
LLM：解释每个部分含义
系统输出：禁止建议 + 替代排查方式
```

### 14.3 自然语言找命令

```text
用户输入：manx ask "怎么查看端口被谁占用"
系统判断：网络/端口任务
系统检查：ss 是否存在，lsof 是否存在
系统选择：优先推荐 ss
系统输出：命令 + 参数解释 + 风险低
```

### 14.4 解释报错

```text
用户输入：manx fix "command not found: ifconfig"
系统识别：命令不存在
系统判断：现代 Linux 推荐 ip 命令
系统输出：使用 ip addr 替代 ifconfig
```

---

## 15. 关键场景库

### 15.1 文件查找

用户问题：

```text
怎么找文件
怎么找大文件
怎么找最近修改的文件
怎么找所有 .log 文件
```

推荐命令：

```bash
find . -name "*.log"
find . -type f -size +100M
find . -type f -mtime -1
```

### 15.2 文本搜索

用户问题：

```text
怎么在日志里找 error
怎么递归搜索目录
怎么忽略大小写
```

推荐命令：

```bash
grep "error" app.log
grep -r "error" .
grep -in "error" app.log
```

### 15.3 端口占用

用户问题：

```text
怎么查 8080 被谁占用
怎么看监听端口
```

推荐命令：

```bash
ss -lntp
ss -lntp | grep ':8080'
```

### 15.4 服务状态

用户问题：

```text
怎么看 nginx 是否启动
怎么查看服务失败原因
```

推荐命令：

```bash
systemctl status nginx
journalctl -u nginx --no-pager
journalctl -u nginx -n 100
```

### 15.5 磁盘空间

用户问题：

```text
磁盘满了怎么办
怎么查哪个目录最大
```

推荐命令：

```bash
df -h
du -sh * 2>/dev/null
du -h --max-depth=1 /var 2>/dev/null
```

危险提醒：

```text
不要直接 rm -rf /var/*
先确认大文件来源。
```

### 15.6 权限问题

用户问题：

```text
Permission denied 怎么办
怎么给脚本执行权限
```

推荐命令：

```bash
ls -l file
chmod +x script.sh
```

危险提醒：

```text
不要 chmod -R 777。
不要 chown -R 当前用户到 /usr、/etc、/bin。
```

---

## 16. 安全规则库

### 16.1 删除类

高危模式：

```text
rm -rf /
rm -rf /*
rm -rf ~
rm -rf $HOME
rm -rf .
rm -rf *
find . -delete
find / -delete
```

提示：

```text
先使用 ls/find -print 预览。
```

### 16.2 权限类

高危模式：

```text
chmod -R 777 /
chmod -R 777 /etc
chmod -R 777 /usr
chmod -R 777 /bin
chmod -R 777 /lib
chmod -R 777 /boot
chown -R * /usr
chown -R * /etc
```

提示：

```text
不要递归修改系统目录权限。
请先说明具体 Permission denied 场景。
```

### 16.3 磁盘类

极高危模式：

```text
dd of=/dev/*
mkfs.*
fdisk /dev/*
parted /dev/*
```

提示：

```text
该命令可能清空磁盘或破坏分区。
```

### 16.4 管道执行脚本

高危模式：

```text
curl ... | bash
curl ... | sh
wget ... -O- | bash
wget ... -O- | sh
```

提示：

```text
这会直接执行远程脚本。
建议先下载并查看内容。
```

安全替代：

```bash
curl -O URL
less script.sh
bash script.sh
```

---

## 17. 成功指标

### 17.1 MVP 指标

#### 使用指标

* 日活命令调用次数。
* 单用户平均查询次数。
* `manx explain` 使用占比。
* `manx ask` 使用占比。
* `manx fix` 使用占比。

#### 质量指标

* 用户是否认为解释清楚。
* 用户是否复制推荐命令。
* 推荐命令是否在本机存在。
* 参数是否被本机 man/help 确认。
* 高危命令识别准确率。

#### 安全指标

* 高危命令漏报率。
* 错误推荐修改系统命令次数。
* 用户反馈“命令不可用”的次数。
* 用户反馈“解释错误”的次数。

### 17.2 北极星指标

> 用户通过 `manx` 成功理解并完成一次 Linux 命令任务的次数。

---

## 18. 技术架构

### 18.1 模块划分

```text
CLI 层
  ↓
意图识别层
  ↓
本机资料采集层
  ↓
命令解析层
  ↓
风险规则层
  ↓
知识卡片层
  ↓
LLM 解释层
  ↓
输出渲染层
```

### 18.2 CLI 层

负责：

* 解析用户输入。
* 区分子命令。
* 控制输出格式。
* 处理 `--short`、`--pro`、`--json`。

可选技术：

* Rust：`clap`
* Go：`cobra`
* Python：`typer` / `click`

### 18.3 本机资料采集层

负责执行只读命令：

```bash
type <cmd>
which <cmd>
man <cmd>
<cmd> --help
help <cmd>
```

需要：

* 超时控制。
* 输出长度限制。
* 错误处理。
* 缓存。

### 18.4 命令解析层

MVP 可以先做轻量解析：

* 按 shell token 拆分。
* 识别管道。
* 识别重定向。
* 识别 sudo。
* 识别短参数组合。
* 识别长参数。
* 识别路径。
* 识别通配符。

后续可以接入 Bash parser。

### 18.5 风险规则层

输入：

```json
{
  "command": "chmod",
  "args": ["-R", "777", "/etc"],
  "has_sudo": true
}
```

输出：

```json
{
  "risk": "critical",
  "reasons": [
    "recursive chmod",
    "permission 777",
    "system directory /etc"
  ]
}
```

### 18.6 知识卡片层

存储高频命令的结构化解释。

格式可用 YAML / JSON。

### 18.7 LLM 解释层

输入：

* 用户问题
* 本机 man/help 片段
* 命令卡片
* 风险分析结果
* 系统上下文

输出：

* 终端友好的解释文本
* 可选 JSON

### 18.8 输出渲染层

负责：

* 彩色高亮。
* 风险等级颜色。
* 代码块格式。
* 控制最大行数。
* 适配窄终端。

---

## 19. 隐私与安全

### 19.1 本地优先

默认情况下，只上传必要文本给 LLM：

* 用户输入
* 命令名称
* man/help 片段
* 系统发行版信息

不上传：

* 环境变量
* shell history
* SSH key
* token
* `.env`
* 私有文件内容
* 当前目录完整文件列表

### 19.2 敏感信息过滤

发送给 LLM 前过滤：

```text
API_KEY=
TOKEN=
PASSWORD=
SECRET=
PRIVATE KEY
BEGIN OPENSSH PRIVATE KEY
```

### 19.3 执行边界

MVP 不自动执行修改性命令。

未来即使加入执行，也必须分级确认：

```text
只读：可自动
普通用户修改：确认
sudo：二次确认
高危：默认拒绝
```

---

## 20. 竞品与差异

### 20.1 传统 man

优势：

* 权威。
* 本机自带。
* 离线可用。

问题：

* 难读。
* 不按新手任务组织。
* 不解释风险。
* 不解释报错。

### 20.2 tldr

优势：

* 简洁。
* 示例友好。

问题：

* 覆盖有限。
* 不基于本机版本。
* 不解释完整命令。
* 不做风险分析。
* 不做报错反推。

### 20.3 ChatGPT / Claude

优势：

* 泛化强。
* 自然语言理解好。

问题：

* 容易脱离本机。
* 可能编造参数。
* 风险不稳定。
* 输出不适合 CLI。
* 不知道用户当前系统命令版本。

### 20.4 ManCoach 的差异

```text
本机 man/help 作为依据
+
高频命令场景库
+
危险命令规则
+
新手友好解释
+
CLI 原生体验
```

---

## 21. 版本规划

### V0.1：离线原型

目标：

* 支持 `manx <cmd>`
* 支持 10 个高频命令
* 只使用内置知识卡片
* 不接 LLM

命令：

```text
ls
cp
mv
rm
grep
find
tar
chmod
ps
systemctl
```

### V0.2：本机 man/help 解析

目标：

* 读取本机 `man` 和 `--help`
* 支持 `manx option`
* 支持命令不存在提示
* 支持 shell builtin 检测

### V0.3：LLM 解释

目标：

* 支持 LLM 生成新手解释
* 加入防幻觉约束
* 支持中文输出
* 支持 `--short` 和 `--pro`

### V0.4：命令解释与风险规则

目标：

* 支持 `manx explain`
* 加入危险命令规则库
* 支持风险等级
* 支持安全替代命令

### V0.5：自然语言问答

目标：

* 支持 `manx ask`
* 支持常见场景映射
* 支持系统上下文判断发行版

### V0.6：报错解释

目标：

* 支持 `manx fix`
* 内置高频错误库
* 输出排查步骤

### V1.0：稳定版

目标：

* 支持 50 个高频命令
* 支持 Ubuntu / Debian / Fedora / Arch 基础差异
* 支持本地缓存
* 支持 JSON 输出
* 支持插件式命令卡片
* 风险识别稳定

---

## 22. MVP 开发优先级

### P0 必须做

* `manx <cmd>`
* `manx explain "<cmdline>"`
* 本机命令检测
* man/help 读取
* shell builtin 识别
* 风险规则库
* 20 个高频命令卡片
* 中文新手输出
* 不自动执行修改性命令

### P1 应该做

* `manx ask`
* `manx fix`
* `manx option`
* `--short`
* `--pro`
* JSON 输出
* 本地缓存

### P2 后续做

* 多语言
* 发行版差异解释
* 插件系统
* 用户自定义知识卡片
* 终端补全
* 命令历史辅助分析
* 与 shell 集成，在用户执行前提示风险

---

## 23. 不做什么

MVP 明确不做：

* 不做桌面 UI。
* 不做桌宠。
* 不做自动修复系统。
* 不做后台常驻监控。
* 不读取用户 shell history。
* 不扫描用户项目文件。
* 不自动执行 sudo。
* 不做生产环境 SRE Agent。
* 不做复杂 Bash 脚本审计。
* 不做渗透测试自动化。
* 不做全量 Linux 教程站。

---

## 24. 示例体验

### 示例 1：用户不知道 grep 怎么用

输入：

```bash
manx grep
```

输出：

```text
grep：从文本里搜索匹配内容。

最常用：

grep "error" app.log
在 app.log 里找 error

grep -r "error" .
递归搜索当前目录

grep -i "error" app.log
忽略大小写

grep -n "error" app.log
显示行号

grep -v "debug" app.log
排除 debug 行

常用参数：
-r  递归
-i  忽略大小写
-n  显示行号
-v  反向匹配
-E  使用扩展正则

新手坑：
grep 默认不会递归目录。
搜索目录要加 -r。
```

### 示例 2：用户解释危险命令

输入：

```bash
manx explain "sudo chmod -R 777 /usr"
```

输出：

```text
风险：极高

这条命令会递归修改 /usr 目录下所有文件权限。

结构：
sudo        使用管理员权限
chmod       修改文件权限
-R          递归处理所有子目录和文件
777         所有人都可读、可写、可执行
/usr        系统程序目录

为什么危险：
- /usr 是系统目录。
- 777 会让普通用户也能修改系统程序。
- 可能导致系统损坏或安全风险。
- 很难完整恢复原权限。

结论：
不要执行。

你可能真正想解决的是 Permission denied。
建议先运行：

ls -l <具体文件>
whoami
```

### 示例 3：用户问端口占用

输入：

```bash
manx ask "怎么查 8080 端口被谁占用"
```

输出：

```text
推荐命令：

ss -lntp | grep ':8080'

解释：
ss        查看网络连接
-l        只看监听端口
-n        显示数字端口
-t        只看 TCP
-p        显示进程

风险：低
这是只读命令，不会修改系统。

如果看不到进程名，可以用：

sudo ss -lntp | grep ':8080'
```

---

## 25. 最终产品定义

ManCoach / manx 不是普通 AI CLI，也不是自动运维 Agent。

它的准确定位是：

> **面向 Linux 新手的本地命令理解层。**

它解决的问题不是“让 AI 替你操作 Linux”，而是：

```text
你不知道命令怎么用 → 它把 man 讲成人话
你不懂参数含义 → 它逐项解释
你不敢执行命令 → 它告诉你风险
你遇到报错 → 它告诉你下一步查什么
你想完成任务 → 它推荐本机可用的安全命令
```

第一阶段只做“解释与指导”，不要急着做“执行与修复”。

这个产品真正的壁垒是：

```text
Linux 高频任务场景库
+
本机文档解析
+
危险命令规则库
+
足够克制的终端输出
```

只要把这四件事做好，它就会比普通 man、tldr 和聊天机器人更适合 Linux 新手。

我建议 MVP 名字直接用 `manx`，因为它和 `man` 的关系很清楚：不是替代 man，而是 **extended man / explained man**。第一版先别做太多 Agent 感，核心就打磨 `manx grep`、`manx find`、`manx tar`、`manx explain` 这几个入口。

