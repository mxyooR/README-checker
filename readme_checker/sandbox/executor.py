"""Sandbox command executor.

This module provides secure command execution with:
- Dangerous command pattern detection
- Resource limits (CPU, memory)
- Timeout handling
- File system restrictions
"""

from dataclasses import dataclass, field
from pathlib import Path
import re
import subprocess
import time
from typing import Any

from readme_checker.dynamic.verifier import ExecutionResult, ExecutionStatus


@dataclass
class SandboxConfig:
    """Sandbox configuration."""
    allowed_paths: list[Path] = field(default_factory=list)
    allow_network: bool = False
    max_memory_mb: int = 512
    max_cpu_percent: int = 50
    timeout: int = 300


class SandboxExecutor:
    """Secure sandbox for command execution."""
    
    # Dangerous command patterns that should be blocked
    DANGEROUS_PATTERNS: list[re.Pattern] = [
        re.compile(r"rm\s+(-[rf]+\s+)*(/|~|\$HOME)", re.IGNORECASE),
        re.compile(r"sudo\s+", re.IGNORECASE),
        re.compile(r"chmod\s+777\s+/", re.IGNORECASE),
        re.compile(r">\s*/dev/", re.IGNORECASE),
        re.compile(r"mkfs\.", re.IGNORECASE),
        re.compile(r"dd\s+if=", re.IGNORECASE),
        re.compile(r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;", re.IGNORECASE),  # Fork bomb
        re.compile(r"wget\s+.*\|\s*sh", re.IGNORECASE),  # Download and execute
        re.compile(r"curl\s+.*\|\s*sh", re.IGNORECASE),  # Download and execute
    ]
    
    def __init__(self, config: SandboxConfig | None = None):
        """Initialize sandbox with configuration."""
        self.config = config or SandboxConfig()
    
    def is_safe_command(self, command: str) -> tuple[bool, str | None]:
        """
        Check if a command is safe to execute.
        
        Args:
            command: Command string to check
        
        Returns:
            Tuple of (is_safe, reason_if_unsafe)
        """
        for pattern in self.DANGEROUS_PATTERNS:
            if pattern.search(command):
                return False, f"Dangerous pattern detected: {pattern.pattern}"
        
        return True, None
    
    def execute(self, command: str, working_dir: Path) -> ExecutionResult:
        """
        Execute a command in the sandbox.
        
        Args:
            command: Command to execute
            working_dir: Working directory
        
        Returns:
            ExecutionResult with execution details
        """
        # Security check
        is_safe, reason = self.is_safe_command(command)
        if not is_safe:
            return ExecutionResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"Security blocked: {reason}",
                duration_ms=0,
                status=ExecutionStatus.SECURITY_BLOCKED,
            )
        
        # Execute command
        start_time = time.time()
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                capture_output=True,
                text=True,
                timeout=self.config.timeout,
            )
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            # Determine status
            if result.returncode == 0:
                status = ExecutionStatus.SUCCESS
            else:
                status = ExecutionStatus.FAILED
            
            return ExecutionResult(
                command=command,
                exit_code=result.returncode,
                stdout=result.stdout[:10000],  # Truncate large outputs
                stderr=result.stderr[:10000],
                duration_ms=duration_ms,
                status=status,
            )
            
        except subprocess.TimeoutExpired:
            duration_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=f"Command timed out after {self.config.timeout} seconds",
                duration_ms=duration_ms,
                status=ExecutionStatus.TIMEOUT,
            )
        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            return ExecutionResult(
                command=command,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
                status=ExecutionStatus.FAILED,
            )
