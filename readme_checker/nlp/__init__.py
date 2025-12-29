"""NLP-based intent classification module.

This module provides natural language processing capabilities
for understanding command intent in README files.

Merged from semantic/ module.
"""

from readme_checker.nlp.intent_classifier import (
    NLPIntentClassifier,
    IntentType,
    ClassifiedCommand,
    CommandRelationship,
)
from readme_checker.nlp.intent import (
    classify_intent,
    Intent,
    ClassifiedInstruction,
    INTENT_PATTERNS,
)

__all__ = [
    # intent_classifier
    "NLPIntentClassifier",
    "IntentType",
    "ClassifiedCommand",
    "CommandRelationship",
    # intent (from semantic/)
    "classify_intent",
    "Intent",
    "ClassifiedInstruction",
    "INTENT_PATTERNS",
]
