"""
Base Executor - Abstract base class for all execution strategies.
Implements the Strategy pattern for different execution modes.
"""
from abc import ABC, abstractmethod
from typing import Optional
import time
# Use absolute imports to avoid relative import issues when running as script
from core.config import Config, get_config
from core.types import ExecutionResult, SessionState, TokenUsage, CostBreakdown
class BaseExecutor(ABC):
    """
    Abstract base class for all executors.
    Defines the contract that all execution strategies must implement:
    - setup(): Initialize resources
    - execute(): Run the task
    - cleanup(): Release resources
    Provides common utilities for:
    - Configuration access
    - Session state management
    - Cost calculation
    - Token usage tracking
    """
    def __init__(self, config: Optional[Config] = None):
        """
        Initialize executor with configuration.
        Args:
            config: Configuration instance. Uses global config if not provided.
        """
        self.config = config or get_config()
        self._session: Optional[SessionState] = None
        self._start_time: float = 0.0
    @abstractmethod
    def setup(self) -> None:
        """
        Initialize resources before execution.
        Override to set up:
        - API clients
        - Session state
        - Caching structures
        - Event handlers
        """
        ...
    @abstractmethod
    def execute(self, task: str, system_prompt: str = "") -> ExecutionResult:
        """
        Execute the task and return result.
        Args:
            task: The task/prompt to execute
            system_prompt: Optional system prompt for context
        Returns:
            ExecutionResult with content, usage, cost, and metadata
        """
        ...
    @abstractmethod
    def cleanup(self) -> None:
        """
        Release resources after execution.
        Override to clean up:
        - Close connections
        - Save session state
        - Flush metrics
        """
        ...
    def _start_timer(self) -> None:
        """Start execution timer."""
        self._start_time = time.perf_counter()
    def _get_duration_ms(self) -> float:
        """Get elapsed time since timer start in milliseconds."""
        return (time.perf_counter() - self._start_time) * 1000
    def _calculate_cost(self, usage: TokenUsage, model: str) -> CostBreakdown:
        """
        Calculate cost breakdown from token usage.
        Args:
            usage: Token usage from API response
            model: Model identifier (alias or full ID)
        Returns:
            CostBreakdown with per-category costs
        """
        model_config = self.config.resolve_model(model)
        # Calculate costs (price is per million tokens)
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
        """
        Extract token usage from API response.
        Args:
            response: Claude API response object
        Returns:
            TokenUsage with all token counts
        """
        usage = response.usage
        return TokenUsage(
            input_tokens=getattr(usage, "input_tokens", 0),
            output_tokens=getattr(usage, "output_tokens", 0),
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0),
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0),
        )
    def _get_response_text(self, response) -> str:
        """
        Extract text content from API response.
        Args:
            response: Claude API response object
        Returns:
            Concatenated text from all text blocks
        """
        text_parts = []
        for block in response.content:
            if hasattr(block, "text"):
                text_parts.append(block.text)
        return "".join(text_parts)
    def _get_tool_uses(self, response) -> list:
        """
        Extract tool use blocks from API response.
        Args:
            response: Claude API response object
        Returns:
            List of tool use dictionaries
        """
        tool_uses = []
        for block in response.content:
            if hasattr(block, "type") and block.type == "tool_use":
                tool_uses.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })
        return tool_uses
    def get_session(self) -> Optional[SessionState]:
        """Get current session state if available."""
        return self._session
