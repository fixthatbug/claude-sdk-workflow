"""Streaming Handler - Unified streaming response processing."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class StreamingMode(Enum):
    FULL = "full"
    MINIMAL = "minimal"
    PROGRESSIVE = "progressive"
    BUFFERED = "buffered"


@dataclass
class StreamingConfig:
    mode: StreamingMode = StreamingMode.PROGRESSIVE
    buffer_size: int = 1024
    flush_interval: float = 0.1
    show_thinking: bool = False
    show_tool_calls: bool = True
    emit_partial: bool = True


@dataclass
class StreamChunk:
    content_type: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    is_final: bool = False


class StreamingHandler:
    """Unified streaming response handler."""
    
    def __init__(self, config: Optional[StreamingConfig] = None):
        self.config = config or StreamingConfig()
        self._buffer: List[str] = []
        self._buffer_size = 0
        self._callbacks: Dict[str, List[Callable]] = {}
        self._is_streaming = False
        self._chunks_emitted = 0
        self._start_time: Optional[datetime] = None
    
    def on(self, event: str, callback: Callable) -> "StreamingHandler":
        self._callbacks.setdefault(event, []).append(callback)
        return self
    
    def _emit(self, event: str, data: Any) -> None:
        for cb in self._callbacks.get(event, []):
            try:
                cb(data)
            except Exception as e:
                logger.warning(f"Callback error for {event}: {e}")
    
    async def start(self) -> None:
        self._is_streaming = True
        self._start_time = datetime.now()
        self._buffer.clear()
        self._buffer_size = 0
        self._chunks_emitted = 0
        self._emit("start", {"timestamp": self._start_time})
    
    async def process_chunk(self, chunk: StreamChunk) -> None:
        if not self._is_streaming:
            await self.start()
        
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
        self._chunks_emitted += 1
        self._emit("chunk", chunk)
        if chunk.content_type == "text":
            self._emit("text", chunk.content)
        elif chunk.content_type == "tool_use" and self.config.show_tool_calls:
            self._emit("tool", chunk)
        elif chunk.content_type == "thinking" and self.config.show_thinking:
            self._emit("thinking", chunk.content)
    
    async def _buffer_chunk(self, chunk: StreamChunk) -> None:
        self._buffer.append(chunk.content)
        self._buffer_size += len(chunk.content)
        if self._buffer_size >= self.config.buffer_size or chunk.is_final:
            await self._flush_buffer(chunk.is_final)
    
    async def _flush_buffer(self, is_final: bool = False) -> None:
        if self._buffer:
            content = "".join(self._buffer)
            await self._emit_chunk(StreamChunk(content_type="text", content=content, is_final=is_final))
            self._buffer.clear()
            self._buffer_size = 0
    
    async def _progressive_emit(self, chunk: StreamChunk) -> None:
        await self._emit_chunk(chunk)
        if self._chunks_emitted % 10 == 0:
            self._emit("progress", {"chunks": self._chunks_emitted, "elapsed": (datetime.now() - self._start_time).total_seconds()})
    
    async def finish(self) -> Dict[str, Any]:
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
    """Decision engine for streaming behavior."""
    
    def __init__(self):
        self._thresholds = {"short_response": 500, "medium_response": 2000, "long_response": 5000}
    
    def should_stream(self, expected_length: Optional[int] = None, task_type: str = "general", user_preference: Optional[bool] = None) -> StreamingConfig:
        if user_preference is not None:
            mode = StreamingMode.PROGRESSIVE if user_preference else StreamingMode.MINIMAL
            return StreamingConfig(mode=mode)
        
        task_configs = {
            "code_generation": StreamingConfig(mode=StreamingMode.PROGRESSIVE, show_thinking=True),
            "quick_answer": StreamingConfig(mode=StreamingMode.MINIMAL),
            "analysis": StreamingConfig(mode=StreamingMode.BUFFERED, buffer_size=2048),
            "conversation": StreamingConfig(mode=StreamingMode.FULL),
        }
        if task_type in task_configs:
            return task_configs[task_type]
        
        if expected_length:
            if expected_length < self._thresholds["short_response"]:
                return StreamingConfig(mode=StreamingMode.MINIMAL)
            elif expected_length > self._thresholds["long_response"]:
                return StreamingConfig(mode=StreamingMode.PROGRESSIVE)
        
        return StreamingConfig(mode=StreamingMode.PROGRESSIVE)


def create_streaming_handler(mode: str = "progressive", **kwargs) -> StreamingHandler:
    mode_enum = StreamingMode(mode.lower())
    config = StreamingConfig(mode=mode_enum, **kwargs)
    return StreamingHandler(config)


__all__ = ['StreamingMode', 'StreamingConfig', 'StreamChunk', 'StreamingHandler', 'StreamingDecisionEngine', 'create_streaming_handler']
