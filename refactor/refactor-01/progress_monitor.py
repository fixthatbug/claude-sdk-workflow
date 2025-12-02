#!/usr/bin/env python3
"""Progress monitoring for Claude Agent SDK."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


class ProgressMonitor:
    """Real-time progress monitoring for SDK executions."""

    def __init__(
        self,
        on_tool_use: Optional[Callable[[str, Dict], None]] = None,
        on_text: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[int, int], None]] = None,
        verbose: bool = False,
    ):
        self.on_tool_use = on_tool_use
        self.on_text = on_text
        self.on_progress = on_progress
        self.verbose = verbose

        self.current_turn = 0
        self.tools_used: List[Dict[str, Any]] = []
        self.text_parts: List[str] = []
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None

    def start(self) -> None:
        self.started_at = datetime.now()
        self.current_turn = 0
        self.tools_used = []
        self.text_parts = []

    def process_text(self, text: str) -> None:
        self.text_parts.append(text)
        if self.on_text:
            self.on_text(text)
        if self.verbose:
            print(f"📝 {text[:100]}...")

    def process_tool_use(self, name: str, input_data: Dict[str, Any]) -> None:
        tool_info = {
            "name": name,
            "input": input_data,
            "turn": self.current_turn,
            "timestamp": datetime.now().isoformat(),
        }
        self.tools_used.append(tool_info)

        if self.on_tool_use:
            self.on_tool_use(name, input_data)
        if self.verbose:
            print(f"🔧 Tool: {name}")

    def increment_turn(self) -> None:
        self.current_turn += 1
        if self.on_progress:
            self.on_progress(self.current_turn, len(self.tools_used))
        if not self.verbose:
            print(f"\r  Turn {self.current_turn} | Tools: {len(self.tools_used)}", end="", flush=True)

    def complete(self) -> None:
        self.completed_at = datetime.now()

    def get_output(self) -> str:
        return "".join(self.text_parts)

    def get_duration_ms(self) -> int:
        if self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() * 1000)
        return 0

    def get_summary(self) -> Dict[str, Any]:
        return {
            "turns": self.current_turn,
            "tools_used": len(self.tools_used),
            "duration_ms": self.get_duration_ms(),
            "output_length": len(self.get_output()),
        }
