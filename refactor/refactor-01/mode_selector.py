#!/usr/bin/env python3
"""
Mode selection for Claude Agent SDK.

Intelligent execution mode selection based on prompt analysis.
"""

from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Optional


class ExecutionMode(Enum):
    """Execution modes for SDK operations."""
    STANDARD = "standard"
    STREAMING = "streaming"
    BATCH = "batch"
    INTERACTIVE = "interactive"
    ULTRATHINK = "ultrathink"
    CONTINUOUS = "continuous"
    RESEARCH_TEAM = "research_team"
    DISCUSSION_PANEL = "discussion_panel"
    CICD_TEAM = "cicd_team"


class ComplexityLevel(Enum):
    """Task complexity levels."""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"
    ULTRA_COMPLEX = "ultra_complex"


class ModeSelector:
    """Intelligent mode selection based on prompt analysis."""

    ULTRATHINK_PATTERNS = [
        r'\bultrathink\b', r'\borchestrate\b', r'\bdelegate\b', r'\bsubagent\b',
        r'\banalyze\s+all\b', r'\bcomprehensive\b', r'\bdeployment\s+quality\b',
        r'\bmulti[-\s]?step\b', r'\bcomplex\s+workflow\b', r'\bend[-\s]?to[-\s]?end\b',
    ]

    BATCH_PATTERNS = [
        r'\bbulk\b', r'\bbatch\b', r'\bmany\s+files\b', r'\bprocess\s+all\b',
        r'\bevaluation\s+suite\b', r'\bmass\s+processing\b', r'\bbatch\s+api\b',
        r'\b\d+\+?\s+files\b',
    ]

    RESEARCH_PATTERNS = [
        r'\bresearch\b', r'\binvestigate\b', r'\banalyze\s+market\b',
        r'\bcompare\s+options\b', r'\bmulti[-\s]?source\b', r'\bsynthesis\b',
        r'\banalysis\b', r'\bexplore\s+alternatives\b',
    ]

    DISCUSSION_PATTERNS = [
        r'\bdiscuss\b', r'\bdebate\b', r'\bpanel\b', r'\bperspectives\b',
        r'\bdecide\s+between\b', r'\barchitecture\s+decision\b', r'\bconsensus\b',
        r'\bcollaborate\b', r'\bbrainstorm\b',
    ]

    CICD_PATTERNS = [
        r'\bci/cd\b', r'\bpipeline\b', r'\bdeploy\b', r'\bkubernetes\b',
        r'\bgithub\s+actions\b', r'\bworkflow\s+automation\b', r'\bdevops\b',
        r'\bjenkins\b', r'\bgitlab\s+ci\b',
    ]

    CONTINUOUS_PATTERNS = [
        r'\buntil\s+done\b', r'\bkeep\s+going\b', r'\bcomplete\s+all\b',
        r"\bdon't\s+stop\b", r'\bfull\s+context\b', r'\bmulti[-\s]?turn\b',
        r'\biterative\b', r'\bcontinue\s+until\b',
    ]

    COMPLEXITY_INDICATORS = {
        ComplexityLevel.ULTRA_COMPLEX: [
            r'\bdeployment[-\s]?quality\b', r'\bproduction[-\s]?ready\b',
            r'\bend[-\s]?to[-\s]?end\b', r'\bfull\s+system\b',
            r'\bcomprehensive\b', r'\ball\s+aspects\b',
        ],
        ComplexityLevel.COMPLEX: [
            r'\bmulti[-\s]?step\b', r'\bintegration\b', r'\barchitecture\b',
            r'\brefactor\b', r'\boptimize\b', r'\bmigrate\b',
        ],
        ComplexityLevel.MODERATE: [
            r'\bimplement\b', r'\bcreate\b', r'\badd\s+feature\b',
            r'\bupdate\b', r'\benhance\b',
        ],
        ComplexityLevel.SIMPLE: [
            r'\bfix\b', r'\bshow\b', r'\blist\b', r'\bget\b', r'\bfind\b',
        ],
    }

    MODE_CONFIGS = {
        ExecutionMode.STANDARD.value: {
            'model': 'claude-sonnet-4-5-20250929',
            'thinking_budget': 5000,
            'max_turns': 5,
            'enable_caching': True,
            'enable_streaming': True,
            'timeout_ms': 120000,
        },
        ExecutionMode.CONTINUOUS.value: {
            'model': 'claude-sonnet-4-5-20250929',
            'thinking_budget': 10000,
            'max_turns': 20,
            'enable_caching': True,
            'enable_streaming': True,
            'persistence': True,
            'timeout_ms': 300000,
        },
        ExecutionMode.ULTRATHINK.value: {
            'model': 'claude-sonnet-4-5-20250929',
            'thinking_budget': 32000,
            'max_turns': 50,
            'enable_caching': True,
            'enable_streaming': True,
            'enable_subagents': True,
            'max_subagents': 10,
            'timeout_ms': 600000,
        },
        ExecutionMode.BATCH.value: {
            'model': 'claude-sonnet-4-5-20250929',
            'thinking_budget': 5000,
            'max_turns': 5,
            'enable_caching': True,
            'enable_streaming': False,
            'use_batch_api': True,
            'cost_savings': 0.5,
            'timeout_ms': 86400000,
        },
        ExecutionMode.RESEARCH_TEAM.value: {
            'model': 'claude-sonnet-4-5-20250929',
            'thinking_budget': 20000,
            'max_turns': 30,
            'enable_caching': True,
            'enable_streaming': True,
            'enable_subagents': True,
            'required_agents': ['research-specialist', 'data-analyst'],
            'timeout_ms': 600000,
        },
        ExecutionMode.DISCUSSION_PANEL.value: {
            'model': 'claude-sonnet-4-5-20250929',
            'thinking_budget': 15000,
            'max_turns': 25,
            'enable_caching': True,
            'enable_streaming': True,
            'enable_subagents': True,
            'required_agents': ['architect', 'project-manager'],
            'consensus_required': True,
            'timeout_ms': 600000,
        },
        ExecutionMode.CICD_TEAM.value: {
            'model': 'claude-sonnet-4-5-20250929',
            'thinking_budget': 15000,
            'max_turns': 30,
            'enable_caching': True,
            'enable_streaming': True,
            'enable_subagents': True,
            'required_agents': ['devops-specialist', 'test-specialist'],
            'enable_hooks': True,
            'timeout_ms': 600000,
        },
    }

    AGENT_RECOMMENDATIONS = {
        ExecutionMode.ULTRATHINK.value: ['project-manager', 'architect', 'code-specialist'],
        ExecutionMode.BATCH.value: ['data-analyst', 'optimization-specialist'],
        ExecutionMode.RESEARCH_TEAM.value: ['research-specialist', 'data-analyst', 'documentation-specialist'],
        ExecutionMode.DISCUSSION_PANEL.value: ['architect', 'project-manager', 'code-specialist'],
        ExecutionMode.CICD_TEAM.value: ['devops-specialist', 'test-specialist', 'security-specialist'],
        ExecutionMode.CONTINUOUS.value: ['code-specialist', 'verification-specialist'],
        ExecutionMode.STANDARD.value: ['code-specialist'],
    }

    THINKING_BUDGETS = {
        ComplexityLevel.SIMPLE.value: 3000,
        ComplexityLevel.MODERATE.value: 8000,
        ComplexityLevel.COMPLEX.value: 16000,
        ComplexityLevel.ULTRA_COMPLEX.value: 32000,
    }

    def __init__(self):
        self._compiled_patterns = {
            ExecutionMode.ULTRATHINK: [re.compile(p, re.IGNORECASE) for p in self.ULTRATHINK_PATTERNS],
            ExecutionMode.BATCH: [re.compile(p, re.IGNORECASE) for p in self.BATCH_PATTERNS],
            ExecutionMode.RESEARCH_TEAM: [re.compile(p, re.IGNORECASE) for p in self.RESEARCH_PATTERNS],
            ExecutionMode.DISCUSSION_PANEL: [re.compile(p, re.IGNORECASE) for p in self.DISCUSSION_PATTERNS],
            ExecutionMode.CICD_TEAM: [re.compile(p, re.IGNORECASE) for p in self.CICD_PATTERNS],
            ExecutionMode.CONTINUOUS: [re.compile(p, re.IGNORECASE) for p in self.CONTINUOUS_PATTERNS],
        }

        self._complexity_patterns = {
            level: [re.compile(p, re.IGNORECASE) for p in patterns]
            for level, patterns in self.COMPLEXITY_INDICATORS.items()
        }

    def select_mode(self, prompt: str, context: Optional[Dict] = None) -> str:
        if not prompt:
            return ExecutionMode.STANDARD.value

        scores = self._calculate_mode_scores(prompt, context)
        if not scores:
            return ExecutionMode.STANDARD.value

        max_mode = max(scores.items(), key=lambda x: x[1])
        return max_mode[0].value if max_mode[1] > 0 else ExecutionMode.STANDARD.value

    def _calculate_mode_scores(self, prompt: str, context: Optional[Dict]) -> Dict[ExecutionMode, int]:
        scores = {}
        for mode, patterns in self._compiled_patterns.items():
            score = sum(1 for pattern in patterns if pattern.search(prompt))
            if score > 0:
                scores[mode] = score

        if context:
            self._apply_context_adjustments(scores, context)
        return scores

    def _apply_context_adjustments(self, scores: Dict[ExecutionMode, int], context: Dict):
        if context.get('file_count', 0) > 10:
            scores[ExecutionMode.BATCH] = scores.get(ExecutionMode.BATCH, 0) + 2
        if context.get('requires_persistence'):
            scores[ExecutionMode.CONTINUOUS] = scores.get(ExecutionMode.CONTINUOUS, 0) + 2
        if context.get('agent_count', 0) > 2:
            scores[ExecutionMode.ULTRATHINK] = scores.get(ExecutionMode.ULTRATHINK, 0) + 2
        if context.get('requires_discussion'):
            scores[ExecutionMode.DISCUSSION_PANEL] = scores.get(ExecutionMode.DISCUSSION_PANEL, 0) + 2

    def analyze_prompt_complexity(self, prompt: str) -> str:
        if not prompt:
            return ComplexityLevel.SIMPLE.value

        for level in [ComplexityLevel.ULTRA_COMPLEX, ComplexityLevel.COMPLEX,
                      ComplexityLevel.MODERATE, ComplexityLevel.SIMPLE]:
            patterns = self._complexity_patterns.get(level, [])
            if any(pattern.search(prompt) for pattern in patterns):
                return level.value

        prompt_length = len(prompt.split())
        if prompt_length > 100:
            return ComplexityLevel.ULTRA_COMPLEX.value
        elif prompt_length > 50:
            return ComplexityLevel.COMPLEX.value
        elif prompt_length > 20:
            return ComplexityLevel.MODERATE.value
        return ComplexityLevel.SIMPLE.value

    def get_mode_config(self, mode: str) -> Dict[str, Any]:
        return self.MODE_CONFIGS.get(mode, self.MODE_CONFIGS[ExecutionMode.STANDARD.value])

    def get_recommended_agents(self, mode: str, complexity: str) -> List[str]:
        agents = list(self.AGENT_RECOMMENDATIONS.get(mode, ['code-specialist']))
        if complexity in [ComplexityLevel.COMPLEX.value, ComplexityLevel.ULTRA_COMPLEX.value]:
            if 'architect' not in agents:
                agents.append('architect')
        return agents

    def get_thinking_budget(self, complexity: str) -> int:
        return self.THINKING_BUDGETS.get(complexity, 8000)
