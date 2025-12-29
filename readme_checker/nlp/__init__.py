"""NLP-based intent classification module.

This module provides natural language processing capabilities
for understanding command intent in README files.
"""

from readme_checker.nlp.intent_classifier import (
    NLPIntentClassifier,
    IntentType,
    ClassifiedCommand,
    CommandRelationship,
)

__all__ = [
    "NLPIntentClassifier",
    "IntentType",
    "ClassifiedCommand",
    "CommandRelationship",
]
