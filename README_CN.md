# README-Checker 🔍

<p align="center">
  <strong>拒绝画饼，实事求是。</strong>
</p>

<p align="center">
  <a href="#安装">安装</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#功能特性">功能特性</a> •
  <a href="#支持的语言">支持的语言</a> •
  <a href="#命令参考">命令参考</a> •
  <a href="./README.md">English</a>
</p>

---

README-Checker 是一个静态文档检查工具，用于验证 README 与实际代码库的一致性。它能检测未文档化的环境变量、失效链接、无效命令和不一致的元数据。

## 为什么需要它？

你是否遇到过这些情况：

- � 代码中使用了环境变量l，但 README 里从未提及
- 🔗 `./docs/guide.md` 链接指向不存在的文件
- 📦 `npm run build` 失败，因为 `package.json` 里根本没有 `build` 脚本
- 📋 README 中的版本号与 `package.json` 不一致

README-Checker 帮你在用户发现之前捕获这些问题。

## 安装

```bash
pip install readme-checker
```

或从源码安装：

```bash
git clone https://github.com/user/readme-checker.git
cd readme-checker
pip install -e .
```

### 环境要求

- Python 3.10+

## 快速开始

```bash
# 检查当前目录
checker

# 检查指定项目
checker check ./my-project

# 详细输出（显示扫描的文件）
checker check -v

# JSON 输出（适用于 CI/CD）
checker check --format json

# 显示版本
checker -V
```

## 功能特性

### 🔐 环境变量检测

扫描代码库中的环境变量使用，验证它们是否在 README 或 `.env.example` 中有文档记录。

**支持的模式：**
- Python: `os.getenv()`, `os.environ[]`, pydantic `BaseSettings`, python-decouple, django-environ
- JavaScript/TypeScript: `process.env.KEY`, `process.env["KEY"]`, NestJS ConfigService
- Go: `os.Getenv()`, `os.LookupEnv()`
- C/C++: `getenv()`, `std::getenv()`
- Java: `System.getenv()`, `System.getProperty()`
- Rust: `std::env::var()`, `env::var()`

### 🔗 链接验证

验证 README 中的所有链接：
- ✅ 相对文件链接是否存在
- ✅ 锚点链接是否指向有效的标题
- ⚠️ 警告指向自己仓库的绝对 URL

### 📝 代码块验证

- 检查缺失的语言标识符
- 验证代码块中的 JSON 语法
- 验证代码块中的 YAML 语法
- 智能检测：跳过目录树和纯文本

### 💻 命令验证

验证 README 代码块中的命令是否真正可用：
- **Python**: 检查 `pip install`、`poetry run`、脚本是否存在
- **Node.js**: 验证 `npm run` 脚本是否在 `package.json` 中存在
- **Go**: 验证 `go run`、`go build` 目标
- **Java**: 检查 Maven/Gradle 命令和包装器

### 📊 元数据一致性

从项目配置文件提取元数据并与 README 对比：
- 版本号一致性
- 许可证一致性

### 🔧 系统依赖检测

检测代码中的系统工具调用（subprocess、exec 等），如果未文档化则发出警告：
- `ffmpeg`、`docker`、`kubectl`、`git` 等

## 支持的语言

| 语言 | 环境变量检测 | AST 解析 | 命令验证 |
|------|-------------|---------|---------|
| Python | ✅ 完整 | ✅ AST | ✅ pip, poetry |
| JavaScript/TypeScript | ✅ 完整 | ✅ esprima | ✅ npm, yarn |
| Go | ✅ 正则 | ❌ | ✅ go 命令 |
| Rust | ✅ 正则 | ❌ | ✅ cargo, rustc |
| Java | ✅ 正则 | ❌ | ✅ mvn, gradle |
| C/C++ | ✅ 正则 | ❌ | ✅ cmake, make |

## 命令参考

### `checker` / `checker check [PATH]`

检查项目 README 与代码库的一致性。

```bash
checker                          # 检查当前目录
checker check .                  # 同上
checker check ./my-project       # 检查指定路径
checker check -v                 # 详细输出
checker check -f json            # JSON 输出
checker check --repo-url "github.com/user/repo"  # 检测绝对 URL
```

| 选项 | 说明 |
|------|------|
| `PATH` | 项目路径（默认：`.`） |
| `-v, --verbose` | 显示详细输出，包括扫描的文件 |
| `-f, --format` | 输出格式：`rich`（默认）或 `json` |
| `--repo-url` | 用于检测绝对 URL 的仓库 URL 模式 |

### `checker version`

显示版本信息。

### `checker -V` / `checker --version`

显示版本并退出。

### `checker -h` / `checker --help`

显示帮助信息。

## 输出示例

```
╭─────────────────────────────────────────────────────────────────╮
│ 🔍 README-Checker Report                                        │
│ Target: ./my-project                                            │
╰─────────────────────────────────────────────────────────────────╯
┏━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ Check       ┃ Status ┃ Details              ┃
┡━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ Links       │ ✅     │ All valid            │
│ Code Blocks │ ✅     │ All valid            │
│ Env Vars    │ ❌     │ 2 undocumented       │
│ System Deps │ ✅     │ All documented       │
│ Metadata    │ ✅     │ Consistent           │
└─────────────┴────────┴──────────────────────┘

Issues Found:
  • [ERROR] Environment variable 'API_KEY' used in code but not documented
    src/config.py:15
    → Add 'API_KEY' to README or .env.example
```

## CI/CD 集成

### GitHub Actions

```yaml
- name: Check README
  run: |
    pip install readme-checker
    checker check --format json > report.json
```

### 退出码

- `0`: 所有检查通过（警告不影响）
- `1`: 发现错误

## 项目结构

```
readme_checker/
├── cli/           # CLI 接口（Typer）
│   └── app.py     # 主要 CLI 命令
├── core/          # 核心功能
│   ├── parser.py  # Markdown 解析
│   ├── scanner.py # 代码扫描（AST + 正则）
│   └── validator.py # 验证逻辑
├── plugins/       # 语言插件
│   ├── python.py  # Python 生态
│   ├── nodejs.py  # Node.js 生态
│   ├── golang.py  # Go 生态
│   └── java.py    # Java 生态
└── reporters/     # 输出格式化
    ├── rich_reporter.py  # Rich 终端输出
    └── json_reporter.py  # JSON 输出
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/ -v

# 运行覆盖率测试
pytest tests/ --cov=readme_checker
```

## 许可证

MIT 许可证 - 详见 [LICENSE](LICENSE) 文件。

---

<p align="center">
  <em>用 ❤️ 构建，让文档保持诚实</em>
</p>
