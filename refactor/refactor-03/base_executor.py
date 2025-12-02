"""Base Executor Abstract Class.

Provides standardized lifecycle management for all SDK executors.
Reduces code duplication through inheritance pattern.

@version 2.0.0 - Integrated with project streaming module
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .execution_result import ExecutionResult

__all__ = ['BaseExecutor', 'ExecutorConfig']


# =============================================================================
# Constants
# =============================================================================

CONTEXT_WINDOW_LIMITS: Dict[str, int] = {
    "standard": 200_000,
    "haiku": 200_000,
    "sonnet": 200_000,
    "opus": 200_000,
}

SDK_AVAILABLE: bool = False
try:
    import anthropic
    SDK_AVAILABLE = True
except ImportError:
    pass


# =============================================================================
# Configuration
# =============================================================================

class ExecutorConfig:
    """Configuration container for executor initialization.

    Uses __slots__ for memory efficiency.
    
    Attributes:
        cwd: Working directory for execution
        model: Model identifier (opus/sonnet/haiku)
        max_turns: Maximum conversation turns (None = unlimited)
        context_limit: Context window limit in tokens
        context_threshold: Stop threshold (0.0-1.0)
        output_dir: Directory for artifacts
        verbose: Enable verbose logging
        cost_budget: Optional cost budget in USD
    """

    __slots__ = (
        'cwd', 'model', 'max_turns', 'context_limit',
        'context_threshold', 'output_dir', 'verbose', 'cost_budget'
    )

    def __init__(
        self,
        cwd: Optional[str] = None,
        model: str = "sonnet",
        max_turns: Optional[int] = None,
        context_limit: int = 200_000,
        context_threshold: float = 0.85,
        output_dir: Optional[str] = None,
        verbose: bool = False,
        cost_budget: Optional[float] = None,
    ):
        self.cwd = cwd or str(Path.cwd())
        self.model = model
        self.max_turns = max_turns
        self.context_limit = context_limit
        self.context_threshold = context_threshold
        self.output_dir = output_dir
        self.verbose = verbose
        self.cost_budget = cost_budget

    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {slot: getattr(self, slot) for slot in self.__slots__}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutorConfig':
        """Create config from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__slots__})


# =============================================================================
# Base Executor
# =============================================================================

class BaseExecutor(ABC):
    """Abstract base class for all SDK executors.

    Provides standardized lifecycle management:
    1. setup() - Initialize resources
    2. _execute() - Core execution (abstract)
    3. cleanup() - Release resources

    Example:
        class ContinuousExecutor(BaseExecutor):
            async def _execute(self, task: str, **kwargs) -> ExecutionResult:
                # Implementation
                return result

        executor = ContinuousExecutor(cwd="/project")
        result = await executor.execute("Analyze code")
    """

    CONTEXT_LIMITS: Dict[str, int] = CONTEXT_WINDOW_LIMITS

    def __init__(
        self,
        config: Optional[ExecutorConfig] = None,
        cwd: Optional[str] = None,
        model: str = "sonnet",
        max_turns: Optional[int] = None,
        context_limit: int = 200_000,
        context_threshold: float = 0.85,
        output_dir: Optional[str] = None,
        verbose: bool = False,
        **kwargs: Any,
    ):
        """Initialize base executor.

        Args:
            config: Optional ExecutorConfig object (takes precedence)
            cwd: Working directory
            model: Model identifier
            max_turns: Maximum turns (None = no limit)
            context_limit: Context limit in tokens
            context_threshold: Stop when context exceeds this
            output_dir: Output directory path
            verbose: Enable verbose logging
            **kwargs: Additional options (e.g., cost_budget)
        """
        if config:
            self.config = config
        else:
            self.config = ExecutorConfig(
                cwd=cwd,
                model=model,
                max_turns=max_turns,
                context_limit=context_limit,
                context_threshold=context_threshold,
                output_dir=output_dir,
                verbose=verbose,
                cost_budget=kwargs.get('cost_budget'),
            )

        # Logging
        self.logger = logging.getLogger(self.__class__.__name__)
        if self.config.verbose:
            self.logger.setLevel(logging.DEBUG)

        # State
        self._initialized: bool = False
        self._session_id: Optional[str] = None
        self._current_turn: int = 0
        self._total_input_tokens: int = 0
        self._total_output_tokens: int = 0
        self._context_used_pct: float = 0.0

        # Output directory
        self._output_dir = (
            Path(self.config.output_dir) if self.config.output_dir 
            else Path(self.config.cwd) / ".claude" / "outputs"
        )

    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------

    @property
    def session_id(self) -> Optional[str]:
        """Current session ID."""
        return self._session_id

    @property
    def current_turn(self) -> int:
        """Current turn number."""
        return self._current_turn

    @property
    def context_used_pct(self) -> float:
        """Context usage percentage (0.0-1.0)."""
        return self._context_used_pct

    @property
    def total_tokens(self) -> int:
        """Total tokens used (input + output)."""
        return self._total_input_tokens + self._total_output_tokens

    # -------------------------------------------------------------------------
    # Internal Methods
    # -------------------------------------------------------------------------

    def _check_sdk(self) -> None:
        """Check if SDK is available."""
        if not SDK_AVAILABLE:
            raise RuntimeError(
                "Anthropic SDK not available. Install with: pip install anthropic"
            )

    def _estimate_context_usage(self) -> float:
        """Estimate current context usage as fraction (0.0-1.0)."""
        model_key = "sonnet"
        for key in self.CONTEXT_LIMITS:
            if key in self.config.model.lower():
                model_key = key
                break

        limit = self.CONTEXT_LIMITS[model_key]
        self._context_used_pct = self.total_tokens / limit if limit else 0.0
        return self._context_used_pct

    def _should_stop(self) -> bool:
        """Check if execution should stop based on constraints."""
        if self._estimate_context_usage() >= self.config.context_threshold:
            self.logger.info("Context threshold reached")
            return True

        if self.config.max_turns and self._current_turn >= self.config.max_turns:
            self.logger.info("Max turns reached")
            return True

        return False

    def _generate_session_id(self, prefix: str = "session") -> str:
        """Generate unique session ID."""
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        self._session_id = f"{prefix}-{timestamp}"
        return self._session_id

    # -------------------------------------------------------------------------
    # Lifecycle Methods
    # -------------------------------------------------------------------------

    def setup(self) -> None:
        """Setup phase - initialize resources before execution."""
        self._check_sdk()
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._initialized = True
        self.logger.debug(f"Executor initialized: {self.__class__.__name__}")

    @abstractmethod
    async def _execute(self, task: str, **kwargs: Any) -> Any:
        """Core execution logic - must be implemented by subclasses.

        Args:
            task: Task description
            **kwargs: Additional execution parameters

        Returns:
            ExecutionResult or similar
        """
        pass

    def cleanup(self) -> None:
        """Cleanup phase - release resources after execution."""
        self._initialized = False
        self.logger.debug(f"Executor cleaned up: {self.__class__.__name__}")

    async def execute(self, task: str, **kwargs: Any) -> Any:
        """Main execution flow with lifecycle management.

        Orchestrates: setup() -> _execute() -> cleanup()

        Args:
            task: Task description
            **kwargs: Additional execution parameters

        Returns:
            Result from _execute()
        """
        try:
            self.setup()
            result = await self._execute(task, **kwargs)
            return result
        except Exception as e:
            self.logger.error(f"Execution failed: {e}")
            raise
        finally:
            self.cleanup()

    # -------------------------------------------------------------------------
    # Token Tracking
    # -------------------------------------------------------------------------

    def update_tokens(
        self,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cache_read: int = 0,
        cache_write: int = 0,
        message_id: Optional[str] = None,
    ) -> bool:
        """Update token counts.

        Args:
            input_tokens: Input tokens used
            output_tokens: Output tokens generated
            cache_read: Cache read tokens
            cache_write: Cache write tokens
            message_id: Optional message ID (for deduplication)

        Returns:
            True if tokens were counted
        """
        self._total_input_tokens += input_tokens
        self._total_output_tokens += output_tokens
        return True

    def get_metrics(self) -> Dict[str, Any]:
        """Get current execution metrics."""
        return {
            'session_id': self._session_id,
            'current_turn': self._current_turn,
            'total_input_tokens': self._total_input_tokens,
            'total_output_tokens': self._total_output_tokens,
            'total_tokens': self.total_tokens,
            'context_used_pct': self._context_used_pct,
            'model': self.config.model,
            'initialized': self._initialized,
        }
