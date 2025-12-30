# README-Checker 🔍

<p align="center">
  <strong>Stop lies. Verify your docs.</strong>
</p>

<p align="center">
  <a href="#installation">Installation</a> •
  <a href="#usage">Usage</a> •
  <a href="#features">Features</a> •
  <a href="#options">Options</a> •
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
pip install git+https://github.com/user/readme-checker.git
```

Requirements: Python 3.10+

## Usage

```bash
checker [OPTIONS] [PATH]
```

**Examples:**

```bash
checker                      # Check current directory
checker ./my-project         # Check specific project
checker -v                   # Verbose output (shows scanned files)
checker -f json              # JSON output for CI/CD
checker -i env-vars          # Ignore environment variable checks
checker -i env-vars -i deps  # Ignore multiple checks
checker -V                   # Show version
checker --help               # Show help
```

## Features

### 🔐 Environment Variable Detection

Scans your codebase for environment variable usage and verifies they're documented in README or `.env.example`.

**Supported patterns:**
- Python: `os.getenv()`, `os.environ[]`, pydantic `BaseSettings`, python-decouple, django-environ
- JavaScript/TypeScript: `process.env.KEY`, NestJS ConfigService
- Go: `os.Getenv()`, `os.LookupEnv()`
- Rust: `std::env::var()`
- Java: `System.getenv()`
- C/C++: `getenv()`

### 🔗 Link Validation

- Relative file links exist
- Anchor links point to valid headers
- Warns about absolute URLs to your own repo

### 💻 Command Verification

Verifies commands in README code blocks actually work:
- `pip install <pkg>` - checks if package is declared in requirements.txt/pyproject.toml
- `npm install <pkg>` - checks if package is in package.json
- `npm run <script>` - checks if script exists in package.json
- `python <script.py>` - checks if script file exists
- `go run`, `cargo build` - checks if targets exist

### 📊 Metadata Consistency

- Version number matches project config
- License matches LICENSE file

### 🔧 System Dependency Detection

Detects system tool calls in code (subprocess, exec, etc.) and warns if undocumented:
- `ffmpeg`, `docker`, `kubectl`, `git`, `curl`, etc.

## Options

| Option | Description |
|--------|-------------|
| `PATH` | Project directory to check (default: `.`) |
| `-v, --verbose` | Show detailed output (scanned files, parsed elements) |
| `-f, --format` | Output format: `rich` (default) or `json` |
| `-i, --ignore` | Ignore specific checks (can be used multiple times) |
| `--repo-url` | Repository URL pattern for absolute URL detection |
| `-V, --version` | Show version and exit |
| `--help` | Show help |

### Ignore Options

| Value | Description |
|-------|-------------|
| `links` | Skip link validation |
| `code-blocks` | Skip code block validation |
| `env-vars` | Skip environment variable checks |
| `deps` | Skip system dependency checks |
| `version` | Skip version consistency |
| `license` | Skip license consistency |
| `commands` | Skip command verification |

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

```yaml
# GitHub Actions
- name: Check README
  run: |
    pip install git+https://github.com/user/readme-checker.git
    checker -f json
```

Exit codes: `0` = passed, `1` = errors found

## Supported Languages

| Language | Env Var Detection | AST Parsing | Command Verification |
|----------|-------------------|-------------|---------------------|
| Python | ✅ Full | ✅ AST | ✅ pip, poetry |
| JavaScript/TypeScript | ✅ Full | ✅ esprima | ✅ npm, yarn, pnpm |
| Go | ✅ Regex | ❌ | ✅ go commands |
| Rust | ✅ Regex | ❌ | ✅ cargo, rustc |
| Java | ✅ Regex | ❌ | ✅ mvn, gradle |
| C/C++ | ✅ Regex | ❌ | ✅ cmake, make |

## License

MIT
