"""NLP-based intent classification.

This module uses spaCy dependency parsing to understand
the intent of commands in README files.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any
import re

# Try to import spaCy, fall back to regex if not available
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    spacy = None
    SPACY_AVAILABLE = False


class IntentType(Enum):
    """Command intent types."""
    REQUIRED = "required"           # Must execute
    OPTIONAL = "optional"           # Can skip
    DEPRECATED = "deprecated"       # Should not use
    CONDITIONAL = "conditional"     # Depends on context
    ALTERNATIVE = "alternative"     # Alternative to another command
    INFORMATIONAL = "informational" # Just information


@dataclass
class ClassifiedCommand:
    """A command with classified intent."""
    command: str
    intent: IntentType
    confidence: float               # 0.0 - 1.0
    original_sentence: str
    grammatical_role: str           # Grammatical role in sentence
    related_commands: list[str] = field(default_factory=list)
    needs_review: bool = False      # Flag for manual review
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "command": self.command,
            "intent": self.intent.value,
            "confidence": self.confidence,
            "original_sentence": self.original_sentence,
            "grammatical_role": self.grammatical_role,
            "related_commands": self.related_commands,
            "needs_review": self.needs_review,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ClassifiedCommand":
        """Deserialize from dictionary."""
        return cls(
            command=data["command"],
            intent=IntentType(data["intent"]),
            confidence=data["confidence"],
            original_sentence=data["original_sentence"],
            grammatical_role=data["grammatical_role"],
            related_commands=data.get("related_commands", []),
            needs_review=data.get("needs_review", False),
        )


@dataclass
class CommandRelationship:
    """Relationship between commands."""
    primary_command: str
    related_command: str
    relationship: str  # "alternative", "sequential", "conditional"
    context: str       # Original sentence
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "primary_command": self.primary_command,
            "related_command": self.related_command,
            "relationship": self.relationship,
            "context": self.context,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CommandRelationship":
        """Deserialize from dictionary."""
        return cls(
            primary_command=data["primary_command"],
            related_command=data["related_command"],
            relationship=data["relationship"],
            context=data["context"],
        )


# Regex patterns for fallback classification
CONDITIONAL_PATTERNS = [
    re.compile(r"if\s+you\s+(?:want|need|prefer|would\s+like)", re.IGNORECASE),
    re.compile(r"optionally", re.IGNORECASE),
    re.compile(r"alternatively", re.IGNORECASE),
    re.compile(r"you\s+(?:can|may|might|could)\s+(?:also\s+)?(?:run|execute|use)", re.IGNORECASE),
    re.compile(r"(?:for|when)\s+.*?(?:you\s+)?(?:can|may|might)", re.IGNORECASE),
]

NEGATION_PATTERNS = [
    re.compile(r"(?:do\s+)?not\s+(?:run|execute|use)", re.IGNORECASE),
    re.compile(r"never\s+(?:run|execute|use)", re.IGNORECASE),
    re.compile(r"avoid\s+(?:running|executing|using)", re.IGNORECASE),
    re.compile(r"don'?t\s+(?:run|execute|use)", re.IGNORECASE),
    re.compile(r"deprecated", re.IGNORECASE),
    re.compile(r"no\s+longer\s+(?:supported|recommended)", re.IGNORECASE),
]

CONTRAST_PATTERNS = [
    re.compile(r"but\s+(?:in\s+this\s+case|instead|rather)", re.IGNORECASE),
    re.compile(r"instead\s+(?:of|use)", re.IGNORECASE),
    re.compile(r"rather\s+than", re.IGNORECASE),
    re.compile(r"(?:use|run)\s+.*?\s+instead", re.IGNORECASE),
]

SEQUENTIAL_PATTERNS = [
    re.compile(r"first,?\s+(?:run|execute)", re.IGNORECASE),
    re.compile(r"then,?\s+(?:run|execute)", re.IGNORECASE),
    re.compile(r"after\s+(?:that|this),?\s+(?:run|execute)", re.IGNORECASE),
    re.compile(r"next,?\s+(?:run|execute)", re.IGNORECASE),
]


class NLPIntentClassifier:
    """NLP-based intent classifier using spaCy."""
    
    def __init__(self, model: str = "en_core_web_sm"):
        """
        Initialize classifier.
        
        Args:
            model: spaCy model name to use
        """
        self.model_name = model
        self._nlp = None
        self._spacy_available = SPACY_AVAILABLE
    
    def _load_model(self):
        """Lazy load spaCy model."""
        if self._nlp is None and self._spacy_available:
            try:
                self._nlp = spacy.load(self.model_name)
            except OSError:
                # Model not installed, fall back to regex
                self._spacy_available = False
    
    def classify(self, sentence: str, command: str) -> ClassifiedCommand:
        """
        Classify the intent of a command in a sentence.
        
        Args:
            sentence: The sentence containing the command
            command: The command to classify
        
        Returns:
            ClassifiedCommand with intent classification
        """
        self._load_model()
        
        # Try spaCy-based classification first
        if self._spacy_available and self._nlp is not None:
            return self._classify_with_spacy(sentence, command)
        
        # Fall back to regex-based classification
        return self._classify_with_regex(sentence, command)
    
    def _classify_with_spacy(self, sentence: str, command: str) -> ClassifiedCommand:
        """Classify using spaCy dependency parsing."""
        doc = self._nlp(sentence)
        
        # Find the command in the sentence
        cmd_start = sentence.find(command)
        grammatical_role = "unknown"
        
        # Analyze dependency structure
        has_conditional = False
        has_negation = False
        has_contrast = False
        
        for token in doc:
            # Check for conditional markers
            if token.dep_ in ("mark", "advmod") and token.text.lower() in ("if", "optionally", "alternatively"):
                has_conditional = True
            
            # Check for negation
            if token.dep_ == "neg" or token.text.lower() in ("not", "never", "avoid"):
                has_negation = True
            
            # Check for contrast markers
            if token.text.lower() in ("but", "instead", "rather", "however"):
                has_contrast = True
            
            # Try to find grammatical role of command
            if cmd_start <= token.idx < cmd_start + len(command):
                grammatical_role = token.dep_
        
        # Determine intent based on analysis
        if has_negation:
            return ClassifiedCommand(
                command=command,
                intent=IntentType.DEPRECATED,
                confidence=0.85,
                original_sentence=sentence,
                grammatical_role=grammatical_role,
                needs_review=False,
            )
        
        if has_conditional:
            return ClassifiedCommand(
                command=command,
                intent=IntentType.OPTIONAL,
                confidence=0.8,
                original_sentence=sentence,
                grammatical_role=grammatical_role,
                needs_review=False,
            )
        
        if has_contrast:
            return ClassifiedCommand(
                command=command,
                intent=IntentType.CONDITIONAL,
                confidence=0.75,
                original_sentence=sentence,
                grammatical_role=grammatical_role,
                needs_review=False,
            )
        
        # Default to required with moderate confidence
        return ClassifiedCommand(
            command=command,
            intent=IntentType.REQUIRED,
            confidence=0.7,
            original_sentence=sentence,
            grammatical_role=grammatical_role,
            needs_review=False,
        )
    
    def _classify_with_regex(self, sentence: str, command: str) -> ClassifiedCommand:
        """Classify using regex patterns (fallback)."""
        # Check negation patterns first (highest priority)
        for pattern in NEGATION_PATTERNS:
            if pattern.search(sentence):
                return ClassifiedCommand(
                    command=command,
                    intent=IntentType.DEPRECATED,
                    confidence=0.8,
                    original_sentence=sentence,
                    grammatical_role="regex_match",
                    needs_review=False,
                )
        
        # Check conditional patterns
        for pattern in CONDITIONAL_PATTERNS:
            if pattern.search(sentence):
                return ClassifiedCommand(
                    command=command,
                    intent=IntentType.OPTIONAL,
                    confidence=0.75,
                    original_sentence=sentence,
                    grammatical_role="regex_match",
                    needs_review=False,
                )
        
        # Check contrast patterns
        for pattern in CONTRAST_PATTERNS:
            if pattern.search(sentence):
                return ClassifiedCommand(
                    command=command,
                    intent=IntentType.CONDITIONAL,
                    confidence=0.7,
                    original_sentence=sentence,
                    grammatical_role="regex_match",
                    needs_review=False,
                )
        
        # Default to informational with low confidence (needs review)
        confidence = 0.5
        return ClassifiedCommand(
            command=command,
            intent=IntentType.INFORMATIONAL,
            confidence=confidence,
            original_sentence=sentence,
            grammatical_role="unknown",
            needs_review=confidence < 0.7,
        )
    
    def find_command_relationships(self, text: str, commands: list[str]) -> list[CommandRelationship]:
        """
        Find relationships between multiple commands in text.
        
        Args:
            text: Text containing commands
            commands: List of commands to analyze
        
        Returns:
            List of CommandRelationship objects
        """
        relationships = []
        
        if len(commands) < 2:
            return relationships
        
        # Check for sequential patterns
        for pattern in SEQUENTIAL_PATTERNS:
            if pattern.search(text):
                for i in range(len(commands) - 1):
                    relationships.append(CommandRelationship(
                        primary_command=commands[i],
                        related_command=commands[i + 1],
                        relationship="sequential",
                        context=text,
                    ))
                break
        
        # Check for alternative patterns
        if re.search(r"\bor\b", text, re.IGNORECASE):
            for i in range(len(commands) - 1):
                relationships.append(CommandRelationship(
                    primary_command=commands[i],
                    related_command=commands[i + 1],
                    relationship="alternative",
                    context=text,
                ))
        
        return relationships
