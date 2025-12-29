"""Dynamic verification report generation.

This module provides report generation for dynamic verification results,
including failure categorization and JSON serialization.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import json

from readme_checker.dynamic.verifier import ExecutionResult, ExecutionStatus
from readme_checker.nlp.intent_classifier import ClassifiedCommand
from readme_checker.build.config_parser import ParsedBuildConfig


class FailureCategory(Enum):
    """Failure category types."""
    NONE = "none"
    STATIC_FAILURE = "static_failure"       # File missing
    DYNAMIC_FAILURE = "dynamic_failure"     # Execution failed
    TIMEOUT_FAILURE = "timeout_failure"     # Command timed out
    SECURITY_BLOCKED = "security_blocked"   # Security violation
    NETWORK_FAILURE = "network_failure"     # Network error
    SYNTAX_ERROR = "syntax_error"           # Config syntax error


MAX_OUTPUT_LENGTH = 1000  # Truncate stdout/stderr to this length


def _truncate(text: str, max_length: int = MAX_OUTPUT_LENGTH) -> str:
    """Truncate text to max length with indicator."""
    if len(text) <= max_length:
        return text
    return text[:max_length] + f"\n... [truncated, {len(text) - max_length} more chars]"


@dataclass
class DynamicVerificationReport:
    """Report for a single dynamic verification."""
    command: str
    category: FailureCategory
    exit_code: int | None
    stdout: str
    stderr: str
    duration_ms: int
    
    def __post_init__(self):
        """Truncate outputs after initialization."""
        self.stdout = _truncate(self.stdout)
        self.stderr = _truncate(self.stderr)
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "command": self.command,
            "category": self.category.value,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "duration_ms": self.duration_ms,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DynamicVerificationReport":
        """Deserialize from dictionary."""
        return cls(
            command=data["command"],
            category=FailureCategory(data["category"]),
            exit_code=data.get("exit_code"),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            duration_ms=data.get("duration_ms", 0),
        )
    
    @classmethod
    def from_execution_result(cls, result: ExecutionResult) -> "DynamicVerificationReport":
        """Create report from execution result."""
        # Map execution status to failure category
        status_to_category = {
            ExecutionStatus.SUCCESS: FailureCategory.NONE,
            ExecutionStatus.FAILED: FailureCategory.DYNAMIC_FAILURE,
            ExecutionStatus.TIMEOUT: FailureCategory.TIMEOUT_FAILURE,
            ExecutionStatus.SECURITY_BLOCKED: FailureCategory.SECURITY_BLOCKED,
            ExecutionStatus.NETWORK_ERROR: FailureCategory.NETWORK_FAILURE,
            ExecutionStatus.SYNTAX_ERROR: FailureCategory.SYNTAX_ERROR,
        }
        
        return cls(
            command=result.command,
            category=status_to_category.get(result.status, FailureCategory.DYNAMIC_FAILURE),
            exit_code=result.exit_code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=result.duration_ms,
        )


@dataclass
class IntentClassificationReport:
    """Report for intent classification."""
    original_sentence: str
    command: str
    intent: str
    confidence: float
    needs_review: bool
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "original_sentence": self.original_sentence,
            "command": self.command,
            "intent": self.intent,
            "confidence": self.confidence,
            "needs_review": self.needs_review,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "IntentClassificationReport":
        """Deserialize from dictionary."""
        return cls(
            original_sentence=data["original_sentence"],
            command=data["command"],
            intent=data["intent"],
            confidence=data["confidence"],
            needs_review=data.get("needs_review", False),
        )
    
    @classmethod
    def from_classified_command(cls, cmd: ClassifiedCommand) -> "IntentClassificationReport":
        """Create report from classified command."""
        return cls(
            original_sentence=cmd.original_sentence,
            command=cmd.command,
            intent=cmd.intent.value,
            confidence=cmd.confidence,
            needs_review=cmd.needs_review,
        )


@dataclass
class BuildArtifactReport:
    """Report for build artifact detection."""
    config_file: str
    output_paths: list[str]
    is_default: bool
    has_errors: bool
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "config_file": self.config_file,
            "output_paths": self.output_paths,
            "is_default": self.is_default,
            "has_errors": self.has_errors,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BuildArtifactReport":
        """Deserialize from dictionary."""
        return cls(
            config_file=data["config_file"],
            output_paths=data["output_paths"],
            is_default=data["is_default"],
            has_errors=data.get("has_errors", False),
        )
    
    @classmethod
    def from_parsed_config(cls, config: ParsedBuildConfig) -> "BuildArtifactReport":
        """Create report from parsed build config."""
        return cls(
            config_file=config.config_file,
            output_paths=config.output_paths,
            is_default=config.is_default,
            has_errors=len(config.parse_errors) > 0,
        )


@dataclass
class FullVerificationReport:
    """Complete verification report."""
    dynamic_results: list[DynamicVerificationReport] = field(default_factory=list)
    intent_results: list[IntentClassificationReport] = field(default_factory=list)
    artifact_results: list[BuildArtifactReport] = field(default_factory=list)
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "dynamic_results": [r.to_dict() for r in self.dynamic_results],
            "intent_results": [r.to_dict() for r in self.intent_results],
            "artifact_results": [r.to_dict() for r in self.artifact_results],
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FullVerificationReport":
        """Deserialize from dictionary."""
        return cls(
            dynamic_results=[DynamicVerificationReport.from_dict(r) for r in data.get("dynamic_results", [])],
            intent_results=[IntentClassificationReport.from_dict(r) for r in data.get("intent_results", [])],
            artifact_results=[BuildArtifactReport.from_dict(r) for r in data.get("artifact_results", [])],
        )
    
    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)
    
    @classmethod
    def from_json(cls, json_str: str) -> "FullVerificationReport":
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))
    
    @property
    def has_failures(self) -> bool:
        """Check if any verification failed."""
        return any(r.category != FailureCategory.NONE for r in self.dynamic_results)
    
    @property
    def failure_count(self) -> int:
        """Count number of failures."""
        return sum(1 for r in self.dynamic_results if r.category != FailureCategory.NONE)
    
    @property
    def needs_review_count(self) -> int:
        """Count commands needing manual review."""
        return sum(1 for r in self.intent_results if r.needs_review)
