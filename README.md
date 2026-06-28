# manx - 把 Linux 命令讲成人话

`manx` 是一个 LLM 驱动的命令行解释器：读取本机 `man` / `--help` / `type` 片段，交给模型解释成人话，同时用本地规则引擎给危险命令定级。

技术边界：

- CLI 运行时无第三方库/SDK 依赖，只用 Go 标准库
- LLM 是主路径，支持 Anthropic、OpenAI、OpenAI-compatible 第三方服务
- 风险等级由本地规则引擎判定，LLM 不能改写等级
- `--no-llm` 只用于本地解析与风险检查，不提供静态知识库答案

## 运行

```bash
go run ./cmd/manx --help
go run ./cmd/manx explain "sudo chmod -R 777 /etc"
go run ./cmd/manx ask "怎么查 8080 端口被谁占用"
go run ./cmd/manx fix "Address already in use"
go run ./cmd/manx option find -mtime
```

构建单文件二进制：

```bash
go build -o manx ./cmd/manx
./manx explain "curl https://example.com/install.sh | bash"
```

## 配置 LLM

Anthropic：

```bash
export ANTHROPIC_API_KEY=...
export MANX_MODEL=claude-3-5-haiku-latest
```

OpenAI：

```bash
export OPENAI_API_KEY=...
export MANX_MODEL=gpt-4o-mini
```

第三方 OpenAI-compatible 服务，例如 DeepSeek、通义千问兼容接口、Kimi/Moonshot、智谱、硅基流动等：

```bash
export MANX_LLM_PROVIDER=openai-compatible
export MANX_BASE_URL=https://你的服务商/v1
export MANX_API_KEY=...
export MANX_MODEL=你的模型名
```

Provider 别名也可用：`deepseek`、`qwen`、`dashscope`、`kimi`、`moonshot`、`zhipu`、`glm`、`siliconflow`。这些别名都走 OpenAI-compatible 协议，服务地址仍由 `MANX_BASE_URL` 指定。

## 命令

```text
manx <命令>                    结合本机文档解释一个命令，如 manx tar
manx explain "<整条命令>"       解释整条命令并标注风险
manx ask "<想做什么>"           根据自然语言推荐命令
manx fix "<报错信息>"           解释报错并给排查步骤
manx option <命令> <参数>        解释某个参数，如 manx option tar -z
```

全局开关：

```text
--beginner        新手模式，默认
--short           精简输出
--pro             老手模式
--json            JSON 输出
--full            不截断输出
--no-llm          不调用模型，只保留 explain 的本地解析/风险检查
--color=never     关闭颜色
--version         版本
```

## 风险分级

| 等级 | 含义 | 例子 |
| --- | --- | --- |
| 0 无风险 | 只读查询 | `ls`、`ss -lntp`、`ps aux` |
| 1 低 | 普通用户范围内的轻量文件操作 | `mkdir`、`touch`、`tar -xzf` |
| 2 中 | 可能覆盖、删除或修改文件 | `rm file`、`mv a b` |
| 3 高 | 递归删除、递归改权限、停服务、批量结束进程 | `rm -r dir`、`sudo systemctl stop nginx` |
| 4 极高 | 可能破坏系统、磁盘或安全边界 | `sudo rm -rf /`、`dd of=/dev/sda` |

## 开发

```bash
go test ./...
go build -o manx ./cmd/manx
go list -m all
```

`go list -m all` 应只显示当前模块。

主要结构：

```text
cmd/manx/               CLI 入口
internal/manx/cli.go     子命令分发
internal/manx/collectors.go 本机 man/help/type 采集
internal/manx/llm.go     Anthropic/OpenAI/OpenAI-compatible HTTP 客户端
internal/manx/parser.go  命令行轻量解析
internal/manx/risk.go    风险规则引擎
internal/manx/redact.go  发送给 LLM 前的敏感信息脱敏
```
