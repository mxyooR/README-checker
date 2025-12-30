# README-Checker 🔍

<p align="center">
  <strong>Stop lies. Verify your docs.</strong>
</p>

<p align="center">
  <a href="#installation">Installation</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#features">Features</a> •
  <a href="#supported-languages">Supported Languages</a> •
  <a href="#cli-reference">CLI Reference</a> •
  <a href="./README_CN.md">中文文档</a>
</p>

---

README-Checker is a static documentation linter that validates your README against your actual codebase. It detects undocumented environment variables, broken links, invalid commands, and inconsistent metadata.

## Why?

Ever cloned a repo only to find:

- 🔐 Environment variables used in code but never documented
- 🔗 Links to `./docs/guide.md` that don't exist
- 📦 `npm run build` fails because there's no `build` script
- 📋 Version in README doesn't match `package.json`

README-Checker catches these issues before your users do.

## Installation

```bash
pip install readme-checker
```

Or install from source:

```bash
git clone https://github.com/user/readme-checker.git
cd readme-checker
pip install -e .
```

### Requirements

- Python 3.10+

## Quick Start

```bash
# Check current directory
checker

# Check a specific project
checker check ./my-project

# Verbose output (shows scanned files)
checker check -v

# JSON output for CI/CD
checker check --format json

# Show version
checker -V
```

## Features

### 🔐 Environment Variable Detection

Scans your codebase for environment variable usage and verifies they're documented in README or `.env.example`.

**Supported patterns:**
- Python: `os.getenv()`, `os.environ[]`, pydantic `BaseSettings`, python-decouple, django-environ
- JavaScript/TypeScript: `process.env.KEY`, `process.env["KEY"]`, NestJS ConfigService
- Go: `os.Getenv()`, `os.LookupEnv()`
- C/C++: `getenv()`, `std::getenv()`
- Java: `System.getenv()`, `System.getProperty()`
- Rust: `std::env::var()`, `env::var()`

### 🔗 Link Validation

Validates all links in your README:
- ✅ Relative file links exist
- ✅ Anchor links point to valid headers
- ⚠️ Warns about absolute URLs to your own repo

### 📝 Code Block Validation

- Checks for missing language identifiers
- Validates JSON syntax in code blocks
- Validates YAML syntax in code blocks
- Smart detection: skips directory trees and plain text

### 💻 Command Verification

Verifies commands in README code blocks actually work:
- **Python**: Checks `pip install`, `poetry run`, script existence
- **Node.js**: Validates `npm run` scripts exist in `package.json`
- **Go**: Verifies `go run`, `go build` targets
- **Java**: Checks Maven/Gradle commands and wrappers

### 📊 Metadata Consistency

Extracts metadata from your project config and compares with README:
- Version number consistency
- License consistency

### 🔧 System Dependency Detection

Detects system tool calls in code (subprocess, exec, etc.) and warns if not documented:
- `ffmpeg`, `docker`, `kubectl`, `git`, etc.

## Supported Languages

| Language | Env Var Detection | AST Parsing | Command Verification |
|----------|-------------------|-------------|---------------------|
| Python | ✅ Full | ✅ AST | ✅ pip, poetry |
| JavaScript/TypeScript | ✅ Full | ✅ esprima | ✅ npm, yarn |
| Go | ✅ Regex | ❌ | ✅ go commands |
| Rust | ✅ Regex | ❌ | ✅ cargo, rustc |
| Java | ✅ Regex | ❌ | ✅ mvn, gradle |
| C/C++ | ✅ Regex | ❌ | ✅ cmake, make |

## CLI Reference

### `checker` / `checker check [PATH]`

Check a project's README for consistency with codebase.

```bash
checker                          # Check current directory
checker check .                  # Same as above
checker check ./my-project       # Check specific path
checker check -v                 # Verbose output
checker check -f json            # JSON output
checker check --repo-url "github.com/user/repo"  # Detect absolute URLs
```

| Option | Description |
|--------|-------------|
| `PATH` | Path to project (default: `.`) |
| `-v, --verbose` | Show detailed output including scanned files |
| `-f, --format` | Output format: `rich` (default) or `json` |
| `--repo-url` | Repository URL pattern for absolute URL detection |

### `checker version`

Show version information.

### `checker -V` / `checker --version`

Show version and exit.

### `checker -h` / `checker --help`

Show help message.

## Output Example

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

## CI/CD Integration

### GitHub Actions

```yaml
- name: Check README
  run: |
    pip install readme-checker
    checker check --format json > report.json
```

### Exit Codes

- `0`: All checks passed (warnings are OK)
- `1`: Errors found

## Project Structure

```
readme_checker/
├── cli/           # CLI interface (Typer)
│   └── app.py     # Main CLI commands
├── core/          # Core functionality
│   ├── parser.py  # Markdown parsing
│   ├── scanner.py # Code scanning (AST + regex)
│   └── validator.py # Validation logic
├── plugins/       # Language plugins
│   ├── python.py  # Python ecosystem
│   ├── nodejs.py  # Node.js ecosystem
│   ├── golang.py  # Go ecosystem
│   └── java.py    # Java ecosystem
└── reporters/     # Output formatters
    ├── rich_reporter.py  # Rich terminal output
    └── json_reporter.py  # JSON output
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=readme_checker
```

## License

MIT License - see [LICENSE](LICENSE) file for details.

---

<p align="center">
  <em>Built with ❤️ to keep documentation honest</em>
</p>
