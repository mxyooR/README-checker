# README-Checker 🔍

<p align="center">
  <strong>拒绝画饼，实事求是。</strong>
</p>

<p align="center">
  <a href="#安装">安装</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#功能特性">功能特性</a> •
  <a href="#工作原理">工作原理</a> •
  <a href="#命令参考">命令参考</a> •
  <a href="./README.md">English</a>
</p>

---

README-Checker 是一个 CLI 工具，用于分析 GitHub 项目 README 文件的**真实性**和**一致性**。它能检测虚假命令、失效链接、缺失的配置文件，以及与实际代码库不符的夸大描述。

## 为什么需要它？

你是否遇到过这些情况：

- 📦 `pip install` 失败，因为根本没有 `pyproject.toml`
- 🔗 `./docs/guide.md` 链接指向不存在的文件
- 🎭 号称"企业级解决方案"，实际只有 50 行代码
- ✅ 声称"已完成"的项目，源码里有 200 个 TODO

README-Checker 帮你在浪费时间之前识破这些谎言。

## 安装

```bash
# 从源码安装
git clone https://github.com/user/readme-checker.git
cd readme-checker
pip install -e .
```

### 环境要求

- Python 3.10+
- 依赖：`typer`, `rich`, `markdown-it-py`, `gitpython`, `pathspec`

## 快速开始

```bash
# 检查当前目录
checker check .

# 检查 GitHub 仓库
checker check https://github.com/user/repo

# 详细输出
checker check . -v

# 显示版本
checker version
```

## 功能特性

### 🔍 生态系统验证

检测构建工具引用并验证配置文件是否存在。支持 Python、Node.js、Rust、Go、Java 和 Docker 生态系统。

### 🔗 路径验证

验证 README 中所有文件/文件夹引用：

- Markdown 链接：`[指南](./docs/guide.md)`
- 图片：`![Logo](./assets/logo.png)`
- 代码引用：提到的 `src/main.py`

### 💻 命令验证

检查代码块中的命令是否可执行：

- 验证构建配置中的脚本是否存在
- 验证 Makefile 目标是否存在
- 检查 `pyproject.toml` 中的 Python 入口点

### 📊 信任评分 (0-100)

基于以下因素计算真实性评分：

- 生态系统声明准确性
- 路径有效性
- 命令存在性
- 夸大程度与代码量比例
- TODO 密度

### 🎭 夸大检测

标记与代码库规模不符的夸大描述：

- 代码量小但声明宏大
- TODO 数量多但声称已完成

### ✅ TODO 陷阱检测

捕获声称"完成"但充满未完成工作的项目：

- 统计源码中的 `TODO`, `FIXME`, `HACK`, `XXX`
- 与项目完成度声明进行对比

## 工作原理

```
README.md → 解析 → 提取声明 → 对比代码库验证 → 评分
```

1. **解析**：使用 `markdown-it-py` 从 README 提取代码块、链接和文本
2. **提取**：识别生态系统声明、路径、命令、夸大词汇
3. **验证**：将每个声明与实际仓库进行对比
4. **评分**：基于验证结果计算信任评分

## 命令参考

### `checker check <target>`

检查项目 README 的真实性。

| 选项 | 说明 |
|------|------|
| `<target>` | 本地项目路径或 GitHub URL |
| `-r, --root` | 用于 Monorepo 分析的子目录 |
| `-t, --timeout` | 克隆超时秒数（默认：60） |
| `-v, --verbose` | 显示详细输出 |
| `-d, --dynamic` | 启用动态命令验证 |
| `--dry-run` | 仅语法验证（需配合 --dynamic） |
| `--cmd-timeout` | 命令执行超时（默认：300秒） |
| `--allow-network` | 允许执行期间访问网络 |

### `checker version`

显示版本信息。

## 信任评分等级

| 分数 | 等级 | 含义 |
|------|------|------|
| 90-100 | ✅ 可信赖 | 所见即所得 |
| 70-89 | ⚠️ 可疑 | 部分声明与现实不符 |
| 0-69 | ❌ 骗子 | 发现重大差异 |

## 项目结构

```
readme_checker/
├── cli/          # CLI 接口（Typer + Rich）
├── parsing/      # Markdown 解析和声明提取
├── verification/ # 声明验证和评分
├── repo/         # 仓库加载和 gitignore 处理
├── nlp/          # 命令意图分类
├── dynamic/      # 动态命令验证
├── build/        # 构建系统检测
├── metrics/      # 代码行数和 TODO 统计
├── plugins/      # 语言特定插件（Python, Node, Go, Java）
└── sandbox/      # 沙箱命令执行
```

## 开发

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行测试
pytest tests/ -v
```

## 状态

🚧 **开发中** - 本项目正在积极开发中。

## 贡献

欢迎贡献！请：

1. Fork 本仓库
2. 创建功能分支
3. 提交 Pull Request

## 许可证

MIT 许可证 - 详见 LICENSE 文件。

---

<p align="center">
  <em>用 ❤️ 构建，打击 README 谎言</em>
</p>
