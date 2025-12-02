"""Evaluation Framework - Quality enforcement and hallucination detection."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class EvaluationResult(Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class EvaluationReport:
    check_name: str
    result: EvaluationResult
    score: float
    details: str
    evidence: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


class EvaluationFramework:
    """Framework for evaluating SDK outputs against quality standards."""
    
    def __init__(self, strict_mode: bool = False):
        self.strict_mode = strict_mode
        self._checks = ["completeness", "accuracy", "consistency", "safety", "relevance", "formatting"]
        self._thresholds = {
            "completeness": 0.8, "accuracy": 0.9, "consistency": 0.85,
            "safety": 1.0, "relevance": 0.7, "formatting": 0.6,
        }
    
    def evaluate(self, content: str, context: Optional[Dict] = None, checks: Optional[List[str]] = None) -> List[EvaluationReport]:
        checks_to_run = checks or self._checks
        reports = []
        for check in checks_to_run:
            method = getattr(self, f"_check_{check}", None)
            if method:
                reports.append(method(content, context or {}))
            else:
                reports.append(EvaluationReport(check_name=check, result=EvaluationResult.SKIP, score=0.0, details=f"No implementation: {check}"))
        return reports
    
    def _check_completeness(self, content: str, context: Dict) -> EvaluationReport:
        indicators = {
            "has_content": bool(content.strip()),
            "not_truncated": not content.rstrip().endswith("..."),
            "proper_ending": content.rstrip()[-1] in ".!?`\"'" if content.strip() else False,
        }
        score = sum(indicators.values()) / len(indicators)
        return EvaluationReport("completeness", self._score_to_result(score, "completeness"), score, f"Indicators: {indicators}", [k for k, v in indicators.items() if not v])
    
    def _check_accuracy(self, content: str, context: Dict) -> EvaluationReport:
        if "expected" not in context:
            return EvaluationReport("accuracy", EvaluationResult.SKIP, 0.0, "No expected content provided")
        expected = context["expected"]
        content_words = set(content.lower().split())
        expected_words = set(expected.lower().split())
        overlap = len(content_words & expected_words) / max(len(expected_words), 1)
        return EvaluationReport("accuracy", self._score_to_result(overlap, "accuracy"), overlap, f"Word overlap: {overlap:.2%}")
    
    def _check_consistency(self, content: str, context: Dict) -> EvaluationReport:
        issues = []
        lines = content.split('\n')
        for i, line in enumerate(lines):
            if "not" in line.lower() and "is" in line.lower():
                for j, other in enumerate(lines):
                    if i != j and any(w in other.lower() for w in line.lower().split()[:3]):
                        issues.append(f"Potential contradiction: lines {i+1} and {j+1}")
        score = max(0, 1 - len(issues) * 0.1)
        return EvaluationReport("consistency", self._score_to_result(score, "consistency"), score, f"Found {len(issues)} inconsistencies", issues[:5])
    
    def _check_safety(self, content: str, context: Dict) -> EvaluationReport:
        patterns = [r'\b(password|secret|api[_-]?key)\s*[:=]', r'\b(exec|eval)\s*\(', r'rm\s+-rf\s+/']
        findings = [p for p in patterns if re.search(p, content, re.IGNORECASE)]
        score = 1.0 if not findings else 0.0
        return EvaluationReport("safety", self._score_to_result(score, "safety"), score, "Safety pattern check", findings)
    
    def _check_relevance(self, content: str, context: Dict) -> EvaluationReport:
        query = context.get("query", "")
        if not query:
            return EvaluationReport("relevance", EvaluationResult.SKIP, 0.0, "No query provided")
        query_words = set(query.lower().split())
        content_words = set(content.lower().split())
        relevance = len(query_words & content_words) / max(len(query_words), 1)
        return EvaluationReport("relevance", self._score_to_result(relevance, "relevance"), relevance, f"Query coverage: {relevance:.2%}")
    
    def _check_formatting(self, content: str, context: Dict) -> EvaluationReport:
        indicators = {
            "has_structure": bool(re.search(r'(^#+\s|\n-\s|\n\d+\.)', content, re.MULTILINE)),
            "balanced_quotes": content.count('"') % 2 == 0,
            "balanced_parens": content.count('(') == content.count(')'),
        }
        score = sum(indicators.values()) / len(indicators)
        return EvaluationReport("formatting", self._score_to_result(score, "formatting"), score, f"Formatting: {indicators}")
    
    def _score_to_result(self, score: float, check: str) -> EvaluationResult:
        threshold = self._thresholds.get(check, 0.7)
        if score >= threshold:
            return EvaluationResult.PASS
        elif score >= threshold * 0.7:
            return EvaluationResult.WARN
        return EvaluationResult.FAIL
    
    def passed(self, reports: List[EvaluationReport]) -> bool:
        return all(r.result in (EvaluationResult.PASS, EvaluationResult.SKIP) for r in reports)


class HallucinationGuard:
    """Guard against hallucinated content."""
    
    def __init__(self, sensitivity: float = 0.7):
        self.sensitivity = sensitivity
        self._known_facts: Dict[str, Any] = {}
    
    def register_facts(self, facts: Dict[str, Any]) -> None:
        self._known_facts.update(facts)
    
    def check(self, content: str, context: Optional[Dict] = None) -> Tuple[bool, List[str]]:
        flags = []
        patterns = [
            (r'studies show', 'Unsupported study reference'),
            (r'according to .+, ', 'Unverified attribution'),
            (r'\d+%\s+of\s+', 'Unverified statistic'),
            (r'always|never|all|none', 'Absolute claim'),
        ]
        for pattern, reason in patterns:
            if re.search(pattern, content, re.IGNORECASE):
                flags.append(reason)
        for fact_key, fact_value in self._known_facts.items():
            if fact_key in content.lower() and str(fact_value).lower() not in content.lower():
                flags.append(f"Possible factual error: {fact_key}")
        is_clean = len(flags) < (1 / self.sensitivity)
        return is_clean, flags
    
    def sanitize(self, content: str, flags: List[str]) -> str:
        sanitized = content
        for flag in flags:
            if "statistic" in flag.lower():
                sanitized = re.sub(r'(\d+%)', r'(approximately \1)', sanitized)
            if "study" in flag.lower():
                sanitized = re.sub(r'studies show', 'some sources suggest', sanitized, flags=re.IGNORECASE)
        return sanitized


class ConsistencyEnforcer:
    """Enforce consistency across multi-turn conversations."""
    
    def __init__(self):
        self._assertions: Dict[str, str] = {}
        self._history: List[Dict[str, Any]] = []
    
    def record(self, topic: str, assertion: str) -> None:
        self._assertions[topic] = assertion
        self._history.append({"topic": topic, "assertion": assertion, "timestamp": datetime.now().isoformat()})
    
    def check(self, topic: str, new_assertion: str) -> Tuple[bool, Optional[str]]:
        if topic not in self._assertions:
            return True, None
        previous = self._assertions[topic]
        prev_words = set(previous.lower().split())
        new_words = set(new_assertion.lower().split())
        negation_words = {"not", "no", "never", "isn't", "aren't", "doesn't"}
        if bool(prev_words & negation_words) != bool(new_words & negation_words):
            return False, previous
        return True, previous
    
    def enforce(self, content: str) -> str:
        words = content.lower().split()
        for topic in self._assertions:
            if topic.lower() in words:
                is_consistent, previous = self.check(topic, content)
                if not is_consistent:
                    logger.warning(f"Inconsistency for {topic}: previous='{previous}'")
        return content


__all__ = ['EvaluationResult', 'EvaluationReport', 'EvaluationFramework', 'HallucinationGuard', 'ConsistencyEnforcer']
