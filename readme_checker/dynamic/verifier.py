"""Dynamic command verification.

This module provides dynamic verification of README commands
by actually executing them in a sandboxed environment.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class ExecutionStatus(Enum):
    """Command execution status."""
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    SECURITY_BLOCKED = "security_blocked"
    NETWORK_ERROR = "network_error"
    SYNTAX_ERROR = "syntax_error"


@dataclass
class DynamicVerificationConfig:
    """Configuration for dynamic verification."""
    timeout: int = 300              # Command timeout in seconds
    dry_run: bool = False           # Syntax validation only
    allow_network: bool = False     # Allow network access
    max_memory_mb: int = 512        # Memory limit in MB
    max_cpu_percent: int = 50       # CPU usage limit


@dataclass
class ExecutionResult:
    """Result of command execution."""
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: int
    status: ExecutionStatus
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ExecutionResult":
        """Deserialize from dictionary."""
        return cls(
            command=data["command"],
            exit_code=data["exit_code"],
            stdout=data["stdout"],
            stderr=data["stderr"],
            duration_ms=data["duration_ms"],
            status=ExecutionStatus(data["status"]),
        )


class DynamicVerifier:
    """Dynamic command verifier."""
    
    def __init__(self, config: DynamicVerificationConfig | None = None):
        """Initialize verifier with configuration."""
        self.config = config or DynamicVerificationConfig()
        self._sandbox = None  # Lazy initialization
    
    def verify_command(self, command: str, working_dir: Path) -> ExecutionResult:
        """
        Verify a command by executing it.
        
        Args:
            command: The command to execute
            working_dir: Working directory for execution
        
        Returns:
            ExecutionResult with execution details
        """
        # Import here to avoid circular imports
        from readme_checker.sandbox.executor import SandboxExecutor, SandboxConfig
        
        if self._sandbox is None:
            sandbox_config = SandboxConfig(
                allowed_paths=[working_dir],
                allow_network=self.config.allow_network,
                max_memory_mb=self.config.max_memory_mb,
                max_cpu_percent=self.config.max_cpu_percent,
                timeout=self.config.timeout,
            )
            self._sandbox = SandboxExecutor(sandbox_config)
        
        # Check if dry-run mode
        if self.config.dry_run:
            return ExecutionResult(
                command=command,
                exit_code=0,
                stdout="[dry-run] Syntax validation only",
                stderr="",
                duration_ms=0,
                status=ExecutionStatus.SUCCESS,
            )
        
        return self._sandbox.execute(command, working_dir)
    
    def verify_dependency_file(self, file_path: Path) -> list[dict]:
        """
        Validate a dependency file for syntax errors.
        
        Args:
            file_path: Path to dependency file (pom.xml, package.json, etc.)
        
        Returns:
            List of syntax errors found
        """
        from readme_checker.build.config_parser import get_parser_for_file
        
        parser = get_parser_for_file(file_path)
        if parser is None:
            return []
        
        result = parser.parse_output_path(file_path)
        return [e.__dict__ for e in result.parse_errors]
    
    def classify_failure(self, result: ExecutionResult) -> str:
        """
        Classify the type of failure from execution result.
        
        Args:
            result: Execution result to classify
        
        Returns:
            Failure category string
        """
        if result.status == ExecutionStatus.SUCCESS:
            return "none"
        
        # Check for network errors in stderr
        network_patterns = [
            "could not resolve host",
            "network is unreachable",
            "connection refused",
            "connection timed out",
            "no route to host",
            "name or service not known",
            "temporary failure in name resolution",
        ]
        
        stderr_lower = result.stderr.lower()
        for pattern in network_patterns:
            if pattern in stderr_lower:
                return "network_failure"
        
        return result.status.value
