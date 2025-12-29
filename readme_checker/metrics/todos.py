"""TODO analyzer with categorization.

Categorizes TODOs by priority and provides context.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import re

from readme_checker.filters.pathspec_filter import PathspecFilter


class TodoPriority(Enum):
    """TODO priority levels."""
    TODO = "TODO"      # Standard TODO
    FIXME = "FIXME"    # Bug or issue to fix
    HACK = "HACK"      # Temporary workaround
    XXX = "XXX"        # Attention needed
    NOTE = "NOTE"      # Informational note
    OPTIMIZE = "OPTIMIZE"  # Performance improvement needed


# Priority weights for scoring
PRIORITY_WEIGHTS: dict[TodoPriority, float] = {
    TodoPriority.FIXME: 1.0,      # Most critical
    TodoPriority.HACK: 0.8,       # Should be addressed
    TodoPriority.XXX: 0.7,        # Needs attention
    TodoPriority.TODO: 0.5,       # Standard
    TodoPriority.OPTIMIZE: 0.3,   # Nice to have
    TodoPriority.NOTE: 0.1,       # Informational
}


@dataclass
class TodoItem:
    """A TODO item with context."""
    text: str
    file_path: str
    line_number: int
    priority: TodoPriority
    context_before: str  # Line before
    context_after: str   # Line after
    full_line: str


@dataclass
class TodoSummary:
    """Summary of TODO analysis."""
    total_count: int = 0
    by_priority: dict[str, int] = field(default_factory=dict)
    items: list[TodoItem] = field(default_factory=list)
    weighted_score: float = 0.0  # Higher = more critical TODOs


# Pattern to match TODO-style comments
TODO_PATTERN = re.compile(
    r'\b(TODO|FIXME|HACK|XXX|NOTE|OPTIMIZE)\b[:\s]*(.{0,100})',
    re.IGNORECASE
)


class TodoAnalyzer:
    """Analyzer for TODO comments."""
    
    def __init__(self, repo_path: Path):
        self.repo_path = repo_path
        self._pathspec_filter = PathspecFilter(repo_path)
    
    def analyze(self, max_items: int = 50) -> TodoSummary:
        """
        Analyze TODOs in the repository.
        
        Args:
            max_items: Maximum number of TODO items to collect
        
        Returns:
            TodoSummary with categorized results
        """
        summary = TodoSummary()
        
        # Initialize priority counts
        for priority in TodoPriority:
            summary.by_priority[priority.value] = 0
        
        # Scan files
        for file_path in self.repo_path.rglob("*"):
            if not file_path.is_file():
                continue
            
            # Skip gitignored files
            if self._pathspec_filter.should_ignore(file_path):
                continue
            
            # Only scan source files
            if file_path.suffix.lower() not in {
                ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs",
                ".java", ".kt", ".c", ".cpp", ".h", ".rb", ".php",
            }:
                continue
            
            # Analyze file
            items = self._analyze_file(file_path)
            
            for item in items:
                summary.total_count += 1
                summary.by_priority[item.priority.value] += 1
                
                if len(summary.items) < max_items:
                    summary.items.append(item)
        
        # Calculate weighted score
        summary.weighted_score = self._calculate_weighted_score(summary)
        
        return summary
    
    def _analyze_file(self, file_path: Path) -> list[TodoItem]:
        """Analyze a single file for TODOs."""
        items = []
        
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")
        except Exception:
            return []
        
        relative_path = str(file_path.relative_to(self.repo_path))
        
        for i, line in enumerate(lines):
            match = TODO_PATTERN.search(line)
            if match:
                keyword = match.group(1).upper()
                text = match.group(2).strip() if match.group(2) else ""
                
                # Get priority
                try:
                    priority = TodoPriority[keyword]
                except KeyError:
                    priority = TodoPriority.TODO
                
                # Get context
                context_before = lines[i - 1].strip() if i > 0 else ""
                context_after = lines[i + 1].strip() if i < len(lines) - 1 else ""
                
                items.append(TodoItem(
                    text=text,
                    file_path=relative_path,
                    line_number=i + 1,
                    priority=priority,
                    context_before=context_before[:80],
                    context_after=context_after[:80],
                    full_line=line.strip()[:120],
                ))
        
        return items
    
    def _calculate_weighted_score(self, summary: TodoSummary) -> float:
        """Calculate weighted TODO score (higher = more critical)."""
        if summary.total_count == 0:
            return 0.0
        
        weighted_sum = 0.0
        for priority in TodoPriority:
            count = summary.by_priority.get(priority.value, 0)
            weight = PRIORITY_WEIGHTS.get(priority, 0.5)
            weighted_sum += count * weight
        
        # Normalize by total count
        return weighted_sum / summary.total_count
