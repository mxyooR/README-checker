# README-Checker 🔍

<p align="center">
  <strong>Stop lies. Verify your docs.</strong>
</p>

<p align="center">
  <a href="#installation">Installation</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#features">Features</a> •
  <a href="#how-it-works">How It Works</a> •
  <a href="#cli-reference">CLI Reference</a> •
  <a href="./README_CN.md">中文文档</a>
</p>

---

README-Checker is a CLI tool that analyzes GitHub project README files for **truthfulness** and **consistency**. It detects phantom commands, broken links, missing config files, and over-hyped descriptions that don't match the actual codebase.

## Why?

Ever cloned a repo only to find:

- 📦 `pip install` fails because there's no `pyproject.toml`
- 🔗 Links to `./docs/guide.md` that don't exist
- 🎭 "Enterprise solution" with 50 lines of code
- ✅ "Complete" project with 200 TODOs in the source

README-Checker catches these lies before you waste time.

## Installation

```bash
# From source
git clone https://github.com/user/readme-checker.git
cd readme-checker
pip install -e .
```

### Requirements

- Python 3.10+
- Dependencies: `typer`, `rich`, `markdown-it-py`, `gitpython`, `pathspec`

## Quick Start

```bash
# Check current directory
checker check .

# Check a GitHub repository
checker check https://github.com/user/repo

# Verbose output
checker check . -v

# Show version
checker version
```

## Features

### 🔍 Ecosystem Verification

Detects build tool references and verifies config files exist. Supports Python, Node.js, Rust, Go, Java, and Docker ecosystems.

### 🔗 Path Verification

Validates all file/folder references in the README:

- Markdown links: `[Guide](./docs/guide.md)`
- Images: `![Logo](./assets/logo.png)`
- Code references: mentions of `src/main.py`

### 💻 Command Validation

Checks that commands in code blocks are executable:

- Verifies scripts exist in build configs
- Validates Makefile targets
- Checks Python entry points in `pyproject.toml`

### 📊 Trust Score (0-100)

Calculates a truthfulness score based on:

- Ecosystem claim accuracy
- Path validity
- Command existence
- Hype-to-code ratio
- TODO density

### 🎭 Hype Detection

Flags over-hyped descriptions that don't match codebase scale:

- Big claims with small codebases
- High TODO count with completion claims

### ✅ TODO Trap Detection

Catches "complete" projects full of unfinished work:

- Counts `TODO`, `FIXME`, `HACK`, `XXX` in source
- Compares against project completion claims

## How It Works

```
README.md → Parse → Extract Claims → Verify Against Codebase → Score
```

1. **Parse**: Extract code blocks, links, and text from README using `markdown-it-py`
2. **Extract**: Identify ecosystem claims, paths, commands, hype words
3. **Verify**: Check each claim against the actual repository
4. **Score**: Calculate trust score based on verification results

## CLI Reference

### `checker check <target>`

Check a project's README for truthfulness.

| Option | Description |
|--------|-------------|
| `<target>` | Path to local project or GitHub URL |
| `-r, --root` | Subdirectory for monorepo analysis |
| `-t, --timeout` | Clone timeout in seconds (default: 60) |
| `-v, --verbose` | Show detailed output |
| `-d, --dynamic` | Enable dynamic command verification |
| `--dry-run` | Syntax validation only (with --dynamic) |
| `--cmd-timeout` | Command execution timeout (default: 300s) |
| `--allow-network` | Allow network access during execution |

### `checker version`

Show version information.

## Trust Score Ratings

| Score | Rating | Meaning |
|-------|--------|---------|
| 90-100 | ✅ Trustworthy | What you see is what you get |
| 70-89 | ⚠️ Suspicious | Some claims don't match reality |
| 0-69 | ❌ Liar | Significant discrepancies found |

## Project Structure

```
readme_checker/
├── cli/          # CLI interface (Typer + Rich)
├── parsing/      # Markdown parsing & claim extraction
├── verification/ # Claim verification & scoring
├── repo/         # Repository loading & gitignore handling
├── nlp/          # Intent classification for commands
├── dynamic/      # Dynamic command verification
├── build/        # Build system detection
├── metrics/      # LOC & TODO counting
├── plugins/      # Language-specific plugins (Python, Node, Go, Java)
└── sandbox/      # Sandboxed command execution
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v
```

## Status

🚧 **Work in Progress** - This project is under active development.

## Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License - see LICENSE file for details.

---

<p align="center">
  <em>Built with ❤️ to fight README lies</em>
</p>
