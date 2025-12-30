# Release v0.1.1

## 🎉 What's New

### ✨ Beautiful Report Output
- New quality score system (0-100 points)
- Rating system from "🏆 Doc Master" to "💀 Disaster"
- Progress bars for each check category
- Detailed metrics breakdown with icons
- Improvement tips based on detected issues

### 🔧 Improved Code Scanning
- **Comment Filtering**: Now correctly ignores code in comments
  - Handles inline comments (`# comment`, `// comment`)
  - Handles block comments (`/* ... */`)
  - Preserves strings containing comment characters (e.g., `"http://example.com/#hash"`)
- **Reduced False Positives**: Removed language runtimes from system dependency detection
  - No longer reports `python`, `node`, `java`, `cargo` as system dependencies
  - Only reports truly external tools: `ffmpeg`, `docker`, `kubectl`, `git`, `curl`, etc.
- **Deduplication**: Same tool on same line is only reported once

### 💻 Real Command Verification
- **pip install**: Now checks if packages are declared in `requirements.txt` or `pyproject.toml`
- **npm install**: Now checks if packages are in `package.json` dependencies
- No more false "verified" status for undeclared packages

### 🚀 Simplified CLI
- Direct usage: `checker [PATH]` instead of `checker check [PATH]`
- Cleaner help output
- All options work as expected

## 📦 Downloads

| Platform | File | Size |
|----------|------|------|
| Windows x64 | `checker.exe` | ~9.7 MB |

## 📖 Usage

```bash
# Check current directory
checker

# Check specific project
checker ./my-project

# Verbose output
checker -v

# JSON output for CI/CD
checker -f json

# Ignore specific checks
checker -i env-vars -i deps

# Show version
checker -V
```

## 📊 Sample Output

```
────────────────────────────────────────────────────────────────────────────────
                    📋 README-Checker Documentation Quality Report 📋
────────────────────────────────────────────────────────────────────────────────
╭──────────────────────────── 📊 Documentation Quality Score ────────────────────────────╮
│ Score: 77.2 / 100                                                                      │
│ [███████████████████████░░░░░░░]                                                       │
│                                                                                        │
│ Rating: ✅ Good                                                                        │
│ Not bad, but there's room for improvement                                              │
╰────────────────────────────────────────────────────────────────────────────────────────╯

◆ Check Details

 Check                        Score  Progress                   Status
 🔗 Links                    80 pts  ████████████████░░░░       ✓✓ 1 error(s)
 📝 Code Blocks             100 pts  ████████████████████       ✓✓ Passed
 🔐 Env Vars                 25 pts  █████░░░░░░░░░░░░░░░       ⚠ 5 error(s)
 🔧 System Deps             100 pts  ████████████████████       ✓✓ Passed
 💻 Commands                100 pts  ████████████████████       ✓✓ Passed
 📊 Metadata                100 pts  ████████████████████       ✓✓ Passed
```

## 🐛 Bug Fixes
- Fixed comment characters in strings being incorrectly stripped
- Fixed duplicate system dependency reports
- Fixed CLI entry point issues
- Fixed `tomllib` import error on Python 3.11+

## 📋 Full Changelog
- `ceece58` - fix: comment filtering and command verification
- `c78af03` - docs: update README with simplified CLI usage
- `89057e0` - refactor: simplify CLI to single command entry point
- `d6db7c3` - feat: beautify report output with scores and ratings
- `dd32f7f` - fix: change report output to English
