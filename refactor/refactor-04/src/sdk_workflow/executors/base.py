"""
Base Executor - Abstract base class for all execution strategies.
Implements the Strategy pattern for different execution modes.
"""
from abc import ABC, abstractmethod
from typing import Optional
import time

from ..core.config import Config, get_config
from ..core.types import ExecutionResult, SessionState, TokenUsage, CostBreakdown


class BaseExecutor(ABC):
    """
    Abstract base class for all executors.
    
    Provides common utilities for:
    - Configuration access
    - Session state management
    - Cost calculation
    - Token usage tracking
    """
    
    def __init__(self, config: Optional[Config] = None):
        self.config = config or get_config()
        self._session: Optional[SessionState] = None
        self._start_time: float = 0.0
    
    @abstractmethod
    def setup(self) -> None:
        """Initialize resources before execution."""
        ...
    
    @abstractmethod
    def execute(self, task: str, system_prompt: str = "") -> ExecutionResult:
        """Execute the task and return result."""
        ...
    
    @abstractmethod
    def cleanup(self) -> None:
        """Release resources after execution."""
        ...
    
    def _start_timer(self) -> None:
        self._start_time = time.perf_counter()
    
    def _get_duration_ms(self) -> float:
        return (time.perf_counter() - self._start_time) * 1000
    
    def _calculate_cost(self, usage: TokenUsage, model: str) -> CostBreakdown:
        model_config = self.config.resolve_model(model)
        input_cost = (usage.input_tokens / 1_000_000) * model_config.input_price_per_mtok
        output_cost = (usage.output_tokens / 1_000_000) * model_config.output_price_per_mtok
        cache_read_cost = (usage.cache_read_tokens / 1_000_000) * model_config.cache_read_price
        cache_write_cost = (usage.cache_write_tokens / 1_000_000) * model_config.cache_write_price
        return CostBreakdown(
            input_cost=input_cost,
            output_cost=output_cost,
            cache_read_cost=cache_read_cost,
            cache_write_cost=cache_write_cost,
        )
    
    def _extract_usage(self, response) -> TokenUsage:
        usage = response.usage
        return TokenUsage(
            input_tokens=getattr(usage, "input_tokens", 0),
            output_tokens=getattr(usage, "output_tokens", 0),
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0),
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0),
        )
    
    def _get_response_text(self, response) -> str:
        return "".join(block.text for block in response.content if hasattr(block, "text"))
    
    def _get_tool_uses(self, response) -> list:
        return [
            {"id": block.id, "name": block.name, "input": block.input}
            for block in response.content
            if hasattr(block, "type") and block.type == "tool_use"
        ]
    
    def get_session(self) -> Optional[SessionState]:
        return self._session
