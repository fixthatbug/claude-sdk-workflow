"""Streaming Handler - Unified streaming response processing.

Consolidates duplicate StreamingHandler and StreamingDecisionEngine from
streaming_handler.py, executor.py, and sdk_workflow_enhancements.py
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class StreamingMode(Enum):
    """Streaming output modes."""
    FULL = "full"           # Stream all content
    MINIMAL = "minimal"     # Stream only final results
    PROGRESSIVE = "progressive"  # Stream with progress updates
    BUFFERED = "buffered"   # Buffer then emit


@dataclass
class StreamingConfig:
    """Configuration for streaming behavior."""
    mode: StreamingMode = StreamingMode.PROGRESSIVE
    buffer_size: int = 1024
    flush_interval: float = 0.1  # seconds
    show_thinking: bool = False
    show_tool_calls: bool = True
    emit_partial: bool = True


@dataclass
class StreamChunk:
    """A chunk of streamed content."""
    content_type: str  # text, tool_use, thinking, result
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    is_final: bool = False


class StreamingHandler:
    """Unified streaming response handler.
    
    Consolidates duplicate implementations for consistent streaming behavior.
    """
    
    def __init__(self, config: Optional[StreamingConfig] = None):
        self.config = config or StreamingConfig()
        self._buffer: List[str] = []
        self._buffer_size = 0
        self._callbacks: Dict[str, List[Callable]] = {}
        self._is_streaming = False
        self._chunks_emitted = 0
        self._start_time: Optional[datetime] = None
    
    def on(self, event: str, callback: Callable) -> "StreamingHandler":
        """Register event callback. Returns self for chaining."""
        self._callbacks.setdefault(event, []).append(callback)
        return self
    
    def _emit(self, event: str, data: Any) -> None:
        """Emit event to all registered callbacks."""
        for cb in self._callbacks.get(event, []):
            try:
                cb(data)
            except Exception as e:
                logger.warning(f"Callback error for {event}: {e}")
    
    async def start(self) -> None:
        """Start streaming session."""
        self._is_streaming = True
        self._start_time = datetime.now()
        self._buffer.clear()
        self._buffer_size = 0
        self._chunks_emitted = 0
        self._emit("start", {"timestamp": self._start_time})
    
    async def process_chunk(self, chunk: StreamChunk) -> None:
        """Process an incoming stream chunk."""
        if not self._is_streaming:
            await self.start()
        
        # Apply mode-specific processing
        if self.config.mode == StreamingMode.FULL:
            await self._emit_chunk(chunk)
        elif self.config.mode == StreamingMode.BUFFERED:
            await self._buffer_chunk(chunk)
        elif self.config.mode == StreamingMode.PROGRESSIVE:
            await self._progressive_emit(chunk)
        elif self.config.mode == StreamingMode.MINIMAL:
            if chunk.is_final:
                await self._emit_chunk(chunk)
    
    async def _emit_chunk(self, chunk: StreamChunk) -> None:
        """Emit a single chunk."""
        self._chunks_emitted += 1
        self._emit("chunk", chunk)
        
        # Type-specific events
        if chunk.content_type == "text":
            self._emit("text", chunk.content)
        elif chunk.content_type == "tool_use" and self.config.show_tool_calls:
            self._emit("tool", chunk)
        elif chunk.content_type == "thinking" and self.config.show_thinking:
            self._emit("thinking", chunk.content)
    
    async def _buffer_chunk(self, chunk: StreamChunk) -> None:
        """Buffer chunk for later emission."""
        self._buffer.append(chunk.content)
        self._buffer_size += len(chunk.content)
        
        if self._buffer_size >= self.config.buffer_size or chunk.is_final:
            await self._flush_buffer(chunk.is_final)
    
    async def _flush_buffer(self, is_final: bool = False) -> None:
        """Flush buffered content."""
        if self._buffer:
            content = "".join(self._buffer)
            chunk = StreamChunk(
                content_type="text",
                content=content,
                is_final=is_final
            )
            await self._emit_chunk(chunk)
            self._buffer.clear()
            self._buffer_size = 0
    
    async def _progressive_emit(self, chunk: StreamChunk) -> None:
        """Emit with progress tracking."""
        await self._emit_chunk(chunk)
        if self._chunks_emitted % 10 == 0:
            self._emit("progress", {
                "chunks": self._chunks_emitted,
                "elapsed": (datetime.now() - self._start_time).total_seconds()
            })
    
    async def finish(self) -> Dict[str, Any]:
        """Finish streaming session."""
        if self.config.mode == StreamingMode.BUFFERED:
            await self._flush_buffer(is_final=True)
        
        self._is_streaming = False
        end_time = datetime.now()
        
        stats = {
            "chunks_emitted": self._chunks_emitted,
            "duration_seconds": (end_time - self._start_time).total_seconds() if self._start_time else 0,
            "start_time": self._start_time,
            "end_time": end_time,
        }
        
        self._emit("finish", stats)
        return stats
    
    @property
    def is_streaming(self) -> bool:
        return self._is_streaming


class StreamingDecisionEngine:
    """Decision engine for streaming behavior.
    
    Consolidates duplicate implementations from streaming_handler.py and executor.py
    """
    
    def __init__(self):
        self._thresholds = {
            "short_response": 500,      # chars
            "medium_response": 2000,
            "long_response": 5000,
        }
    
    def should_stream(
        self,
        expected_length: Optional[int] = None,
        task_type: str = "general",
        user_preference: Optional[bool] = None,
    ) -> StreamingConfig:
        """Determine optimal streaming configuration."""
        # User preference takes priority
        if user_preference is not None:
            mode = StreamingMode.PROGRESSIVE if user_preference else StreamingMode.MINIMAL
            return StreamingConfig(mode=mode)
        
        # Task-specific defaults
        task_configs = {
            "code_generation": StreamingConfig(mode=StreamingMode.PROGRESSIVE, show_thinking=True),
            "quick_answer": StreamingConfig(mode=StreamingMode.MINIMAL),
            "analysis": StreamingConfig(mode=StreamingMode.BUFFERED, buffer_size=2048),
            "conversation": StreamingConfig(mode=StreamingMode.FULL),
        }
        
        if task_type in task_configs:
            return task_configs[task_type]
        
        # Length-based decision
        if expected_length:
            if expected_length < self._thresholds["short_response"]:
                return StreamingConfig(mode=StreamingMode.MINIMAL)
            elif expected_length > self._thresholds["long_response"]:
                return StreamingConfig(mode=StreamingMode.PROGRESSIVE)
        
        # Default
        return StreamingConfig(mode=StreamingMode.PROGRESSIVE)


# Factory function
def create_streaming_handler(
    mode: str = "progressive",
    **kwargs
) -> StreamingHandler:
    """Create configured streaming handler."""
    mode_enum = StreamingMode(mode.lower())
    config = StreamingConfig(mode=mode_enum, **kwargs)
    return StreamingHandler(config)


__all__ = [
    'StreamingMode',
    'StreamingConfig',
    'StreamChunk',
    'StreamingHandler',
    'StreamingDecisionEngine',
    'create_streaming_handler',
]
