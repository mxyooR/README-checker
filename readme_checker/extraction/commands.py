"""Robust command extraction using shlex.

This module provides shell command extraction that handles:
- Multi-line commands with backslash continuation
- Pipeline commands
- Environment variables
- Commands with flags and arguments
"""

from dataclasses import dataclass
import re
import shlex


@dataclass
class ExtractedCommand:
    """An extracted shell command."""
    raw_text: str           # Original text
    executable: str         # Executable/command name
    arguments: list[str]    # Argument list
    has_pipe: bool          # Contains pipe
    has_redirect: bool      # Contains redirection
    env_vars: list[str]     # Referenced environment variables
    is_multiline: bool      # Multi-line command
    line_number: int


def extract_commands(code_block: str, language: str = "bash") -> list[ExtractedCommand]:
    """
    Extract commands from a code block.
    
    Supports:
    - Multi-line commands (backslash continuation)
    - Pipeline commands
    - Environment variables
    - Commands with arguments
    
    Args:
        code_block: Code block content
        language: Code block language tag (bash, shell, sh, etc.)
    
    Returns:
        List of extracted commands
    """
    # Only process shell-like code blocks
    shell_languages = {"bash", "shell", "sh", "zsh", "console", ""}
    if language.lower() not in shell_languages:
        return []
    
    commands = []
    
    # Join continuation lines first
    joined = _join_continuation_lines(code_block)
    
    # Split into individual commands (by newline, semicolon)
    lines = joined.strip().split("\n")
    
    for line_num, line in enumerate(lines):
        line = line.strip()
        
        # Skip empty lines and comments
        if not line or line.startswith("#"):
            continue
        
        # Remove shell prompt if present
        line = _remove_prompt(line)
        if not line:
            continue
        
        # Check for pipes and redirections
        has_pipe = "|" in line
        has_redirect = any(op in line for op in [">", ">>", "<", "2>"])
        
        # Extract environment variables
        env_vars = _extract_env_vars(line)
        
        # Parse the command
        try:
            tokens = shlex.split(line)
            if not tokens:
                continue
            
            executable = tokens[0]
            arguments = tokens[1:] if len(tokens) > 1 else []
            
            commands.append(ExtractedCommand(
                raw_text=line,
                executable=executable,
                arguments=arguments,
                has_pipe=has_pipe,
                has_redirect=has_redirect,
                env_vars=env_vars,
                is_multiline="\\" in code_block,
                line_number=line_num,
            ))
        except ValueError:
            # shlex parsing failed, try basic split
            parts = line.split()
            if parts:
                commands.append(ExtractedCommand(
                    raw_text=line,
                    executable=parts[0],
                    arguments=parts[1:],
                    has_pipe=has_pipe,
                    has_redirect=has_redirect,
                    env_vars=env_vars,
                    is_multiline="\\" in code_block,
                    line_number=line_num,
                ))
    
    return commands


def _join_continuation_lines(text: str) -> str:
    """Join lines with backslash continuation."""
    lines = text.split("\n")
    result = []
    current = ""
    
    for line in lines:
        if line.rstrip().endswith("\\"):
            current += line.rstrip()[:-1] + " "
        else:
            current += line
            result.append(current)
            current = ""
    
    if current:
        result.append(current)
    
    return "\n".join(result)


def _remove_prompt(line: str) -> str:
    """Remove common shell prompts from line."""
    # Common prompt patterns: $, >, %, #
    prompts = [
        r"^\$\s+",
        r"^>\s+",
        r"^%\s+",
        r"^#\s+(?!.*#)",  # # but not comments
        r"^[a-zA-Z0-9_-]+@[a-zA-Z0-9_-]+[:\$#%]\s*",  # user@host:
    ]
    
    for pattern in prompts:
        line = re.sub(pattern, "", line)
    
    return line.strip()


def _split_pipeline(command: str) -> list[str]:
    """Split a pipeline command into individual commands."""
    # Simple split by pipe, not handling quoted pipes
    parts = []
    current = ""
    in_quotes = False
    quote_char = None
    
    for char in command:
        if char in "\"'" and not in_quotes:
            in_quotes = True
            quote_char = char
            current += char
        elif char == quote_char and in_quotes:
            in_quotes = False
            quote_char = None
            current += char
        elif char == "|" and not in_quotes:
            parts.append(current.strip())
            current = ""
        else:
            current += char
    
    if current.strip():
        parts.append(current.strip())
    
    return parts


def _extract_env_vars(command: str) -> list[str]:
    """Extract environment variable references from command."""
    # Match $VAR and ${VAR} patterns
    pattern = r"\$\{?([A-Za-z_][A-Za-z0-9_]*)\}?"
    matches = re.findall(pattern, command)
    return list(set(matches))
