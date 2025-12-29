"""Intent classification for README instructions.

This module provides rule-based intent classification to understand
whether README instructions are affirmative, negative, or conditional.
"""

from dataclasses import dataclass
from enum import Enum
import re


class Intent(Enum):
    """Instruction intent types."""
    AFFIRMATIVE = "affirmative"      # Positive instruction: "Run this command"
    NEGATIVE = "negative"            # Negative instruction: "Do not run this"
    CONDITIONAL = "conditional"      # Conditional instruction: "If you want to..."
    INFORMATIONAL = "informational"  # Informational: "This will output..."


@dataclass
class ClassifiedInstruction:
    """A classified instruction from README."""
    text: str
    intent: Intent
    confidence: float  # 0.0 - 1.0
    command: str | None
    context_before: str  # Text context before the command
    line_number: int


# Intent patterns supporting English and Chinese
INTENT_PATTERNS: dict[Intent, list[re.Pattern]] = {
    Intent.NEGATIVE: [
        re.compile(r"(?:do\s+)?not\s+(?:run|execute|use)", re.IGNORECASE),
        re.compile(r"never\s+(?:run|execute|use)", re.IGNORECASE),
        re.compile(r"avoid\s+(?:running|executing|using)", re.IGNORECASE),
        re.compile(r"don'?t\s+(?:run|execute|use)", re.IGNORECASE),
        re.compile(r"切记[不别]要"),
        re.compile(r"不要[运执]行"),
        re.compile(r"禁止[运执]行"),
        re.compile(r"请勿"),
    ],
    Intent.CONDITIONAL: [
        re.compile(r"if\s+you\s+(?:want|need|prefer)", re.IGNORECASE),
        re.compile(r"optionally", re.IGNORECASE),
        re.compile(r"alternatively", re.IGNORECASE),
        re.compile(r"you\s+(?:can|may|might)\s+(?:also\s+)?(?:run|execute|use)", re.IGNORECASE),
        re.compile(r"如果[你您]?(?:想要?|需要)"),
        re.compile(r"可选[地的]?"),
        re.compile(r"或者[你您]?可以"),
    ],
    Intent.AFFIRMATIVE: [
        re.compile(r"^run\s+", re.IGNORECASE | re.MULTILINE),
        re.compile(r"^execute\s+", re.IGNORECASE | re.MULTILINE),
        re.compile(r"first,?\s+(?:run|execute)", re.IGNORECASE),
        re.compile(r"then,?\s+(?:run|execute)", re.IGNORECASE),
        re.compile(r"运行"),
        re.compile(r"执行"),
        re.compile(r"首先"),
        re.compile(r"然后"),
    ],
}


def classify_intent(
    text: str,
    command: str,
    line_number: int = 0
) -> ClassifiedInstruction:
    """
    Classify the intent of a command based on surrounding text.
    
    Args:
        text: The paragraph text containing the command
        command: The extracted command
        line_number: Line number in the original document
    
    Returns:
        ClassifiedInstruction with intent classification
    """
    # Find context before the command
    cmd_pos = text.find(command)
    context_before = text[:cmd_pos] if cmd_pos > 0 else ""
    
    # Check for each intent type, starting with most specific
    best_intent = Intent.INFORMATIONAL
    best_confidence = 0.0
    
    # Check negative patterns first (highest priority)
    for pattern in INTENT_PATTERNS[Intent.NEGATIVE]:
        if pattern.search(context_before) or pattern.search(text[:100]):
            return ClassifiedInstruction(
                text=text,
                intent=Intent.NEGATIVE,
                confidence=0.9,
                command=command,
                context_before=context_before,
                line_number=line_number,
            )
    
    # Check conditional patterns
    for pattern in INTENT_PATTERNS[Intent.CONDITIONAL]:
        if pattern.search(context_before) or pattern.search(text[:150]):
            return ClassifiedInstruction(
                text=text,
                intent=Intent.CONDITIONAL,
                confidence=0.8,
                command=command,
                context_before=context_before,
                line_number=line_number,
            )
    
    # Check affirmative patterns
    for pattern in INTENT_PATTERNS[Intent.AFFIRMATIVE]:
        if pattern.search(context_before) or pattern.search(text[:100]):
            return ClassifiedInstruction(
                text=text,
                intent=Intent.AFFIRMATIVE,
                confidence=0.85,
                command=command,
                context_before=context_before,
                line_number=line_number,
            )
    
    # Default to informational
    return ClassifiedInstruction(
        text=text,
        intent=Intent.INFORMATIONAL,
        confidence=0.5,
        command=command,
        context_before=context_before,
        line_number=line_number,
    )
