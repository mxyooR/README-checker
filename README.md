# README-Checker 🔍

**Stop lies. Verify your docs.** (拒绝画饼，实事求是。)

A CLI tool to detect "truthfulness" and "consistency" in GitHub project README files.

## Installation

```bash
pip install readme-checker
```

## Usage

```bash
# Check a local project
checker check ./my-project

# Check a GitHub repository
checker check https://github.com/user/repo
```

## Features

- 🔍 **Ecosystem Check**: Verify build tool configs exist (npm, pip, docker, etc.)
- 🔗 **Path Verification**: Check that referenced files actually exist
- 💻 **Command Validation**: Verify scripts in code blocks are real
- 📊 **Trust Score**: Get a 0-100 score for documentation truthfulness
- 🎭 **Hype Detection**: Catch over-hyped project descriptions
- ✅ **TODO Trap**: Find "complete" projects full of TODOs

## License

MIT
