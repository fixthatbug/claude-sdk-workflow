"""
Configuration - Single Source of Truth for Claude Agent SDK Workflow.
Production-ready implementation with advanced usage patterns.
This module provides centralized configuration for:
- Model pricing and routing decisions
- Beta feature headers
- Budget management and cost tracking
- Retry logic and circuit breakers
- Prompt caching configuration
- Timeout and connection settings
Based on Claude Agent SDK documentation and best practices.
"""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any
import os
import json
from datetime import datetime, timedelta
class ModelTier(Enum):
    """Model tiers for routing decisions based on task complexity."""
    HAIKU = "haiku"
    SONNET = "sonnet"
    OPUS = "opus"
    def __lt__(self, other):
        """Enable tier comparison for escalation logic."""
        tier_order = {ModelTier.HAIKU: 0, ModelTier.SONNET: 1, ModelTier.OPUS: 2}
        return tier_order[self] < tier_order[other]
@dataclass
class ModelConfig:
    """
    Configuration for a specific Claude model.
    Attributes:
        model_id: Full model identifier (e.g., "claude-haiku-4-5-20251001")
        input_price_per_mtok: Price per million input tokens in USD
        output_price_per_mtok: Price per million output tokens in USD
        max_tokens: Maximum output tokens supported
        context_window: Maximum context window size in tokens
        tier: Model tier for routing decisions
    """
    model_id: str
    input_price_per_mtok: float
    output_price_per_mtok: float
    max_tokens: int
    context_window: int
    tier: ModelTier
    @property
    def cache_read_price(self) -> float:
        """Cache read is 10% of base input price (90% discount)."""
        return self.input_price_per_mtok * 0.1
    @property
    def cache_write_price(self) -> float:
        """Cache write is 125% of base input price (25% markup)."""
        return self.input_price_per_mtok * 1.25
    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        cache_read_tokens: int = 0,
        cache_write_tokens: int = 0
    ) -> float:
        """
        Estimate total cost for a request with caching.
        Args:
            input_tokens: Number of input tokens
            output_tokens: Number of output tokens
            cache_read_tokens: Number of tokens read from cache
            cache_write_tokens: Number of tokens written to cache
        Returns:
            Estimated cost in USD
        """
        input_cost = (input_tokens / 1_000_000) * self.input_price_per_mtok
        output_cost = (output_tokens / 1_000_000) * self.output_price_per_mtok
        cache_read_cost = (cache_read_tokens / 1_000_000) * self.cache_read_price
        cache_write_cost = (cache_write_tokens / 1_000_000) * self.cache_write_price
        return input_cost + output_cost + cache_read_cost + cache_write_cost
    def fits_in_context(self, tokens: int) -> bool:
        """Check if token count fits within context window."""
        return tokens <= self.context_window
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for logging/storage."""
        return {
            "model_id": self.model_id,
            "input_price_per_mtok": self.input_price_per_mtok,
            "output_price_per_mtok": self.output_price_per_mtok,
            "max_tokens": self.max_tokens,
            "context_window": self.context_window,
            "tier": self.tier.value,
        }
# Model definitions (2025 pricing) - Claude 4.5 models only
MODELS: Dict[str, ModelConfig] = {
    "claude-haiku-4-5-20251001": ModelConfig(
        model_id="claude-haiku-4-5-20251001",
        input_price_per_mtok=0.80,
        output_price_per_mtok=4.00,
        max_tokens=8192,
        context_window=200_000,
        tier=ModelTier.HAIKU,
    ),
    "claude-sonnet-4-5-20250929": ModelConfig(
        model_id="claude-sonnet-4-5-20250929",
        input_price_per_mtok=3.00,
        output_price_per_mtok=15.00,
        max_tokens=16384,
        context_window=200_000,
        tier=ModelTier.SONNET,
    ),
    "claude-opus-4-5-20251101": ModelConfig(
        model_id="claude-opus-4-5-20251101",
        input_price_per_mtok=15.00,
        output_price_per_mtok=75.00,
        max_tokens=32768,
        context_window=200_000,
        tier=ModelTier.OPUS,
    ),
}
# Aliases for convenience - Claude 4.5 models only
MODEL_ALIASES = {
    "haiku": "claude-haiku-4-5-20251001",
    "haiku-4.5": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-5-20250929",
    "sonnet-4.5": "claude-sonnet-4-5-20250929",
    "opus": "claude-opus-4-5-20251101",
    "opus-4.5": "claude-opus-4-5-20251101",
}
@dataclass
class BetaHeaders:
    """
    Beta feature headers for Claude API requests.
    These headers enable experimental features in the Claude API.
    Multiple beta headers can be combined in a single request.
    """
    code_execution: str = "code-execution-2025-08-25"
    files_api: str = "files-api-2025-04-14"
    skills: str = "skills-2025-10-02"
    context_management: str = "context-management-2025-06-27"
    fine_grained_tools: str = "fine-grained-tool-streaming-2025-05-14"
    structured_outputs: str = "structured-outputs-2025-11-13"
    def get_list(self, *features: str) -> List[str]:
        """
        Get list of beta headers for specified features.
        Args:
            *features: Feature names (e.g., "code_execution", "files", "tools")
        Returns:
            List of beta header strings
        Example:
            >>> beta = BetaHeaders()
            >>> beta.get_list("code_execution", "tools")
            ['code-execution-2025-08-25', 'fine-grained-tool-streaming-2025-05-14']
        """
        mapping = {
            "code_execution": self.code_execution,
            "files": self.files_api,
            "skills": self.skills,
            "context": self.context_management,
            "tools": self.fine_grained_tools,
            "structured": self.structured_outputs,
        }
        return [mapping[f] for f in features if f in mapping]
    def get_all(self) -> List[str]:
        """Get all available beta headers."""
        return [
            self.code_execution,
            self.files_api,
            self.skills,
            self.context_management,
            self.fine_grained_tools,
            self.structured_outputs,
        ]
@dataclass
class RoutingConfig:
    """
    Configuration for intelligent model routing based on task complexity.
    The routing system analyzes prompts to select the most cost-effective model
    while maintaining quality. Simple tasks use Haiku, complex tasks use Sonnet.
    """
    # Keywords that suggest simple tasks (use Haiku)
    simple_keywords: List[str] = field(default_factory=lambda: [
        "extract", "format", "validate", "check", "list", "count",
        "quick", "just", "simply", "get", "find", "show", "summarize"
    ])
    # Keywords that suggest complex tasks (use Sonnet)
    complex_keywords: List[str] = field(default_factory=lambda: [
        "refactor", "architect", "design", "research", "implement",
        "build", "create", "analyze", "optimize", "review", "debug",
        "comprehensive", "detailed", "thorough"
    ])
    # Escalation triggers (quality issues in response)
    escalation_markers: List[str] = field(default_factory=lambda: [
        "I cannot", "I'm not sure", "I don't have", "unable to",
        "I apologize", "I'm unable", "I don't know", "unclear"
    ])
    # Minimum response length (shorter = potential quality issue)
    min_quality_length: int = 50
    # Token thresholds for routing
    large_context_threshold: int = 50_000 # Use Sonnet for large contexts
    # Default models for each mode
    default_oneshot_model: str = "haiku"
    default_streaming_model: str = "sonnet"
    default_orchestrator_model: str = "sonnet"
    default_subagent_model: str = "haiku"
    def should_escalate(self, response: str, current_tier: ModelTier) -> bool:
        """
        Determine if response quality warrants escalation to higher tier.
        Args:
            response: Model response text
            current_tier: Current model tier used
        Returns:
            True if escalation is recommended
        """
        # Already at highest tier
        if current_tier == ModelTier.OPUS:
            return False
        # Check for quality markers
        response_lower = response.lower()
        has_escalation_marker = any(
            marker in response_lower for marker in self.escalation_markers
        )
        # Check response length
        is_too_short = len(response.strip()) < self.min_quality_length
        return has_escalation_marker or is_too_short
@dataclass
class BudgetConfig:
    """
    Budget thresholds and limits for cost control.
    Implements a three-tier budget system:
    - Soft limit (80%): Warnings only
    - Hard limit (100%): Block non-critical requests
    - Emergency limit (120%): Block all requests
    """
    daily_budget_usd: float = 10.0
    soft_limit_percent: float = 0.80
    hard_limit_percent: float = 1.00
    emergency_limit_percent: float = 1.20
    # Per-request limits
    max_input_tokens: int = 100_000
    max_output_tokens: int = 16_000
    # Cost tracking
    current_spend: float = 0.0
    last_reset: Optional[datetime] = None
    def __post_init__(self):
        """Initialize tracking fields."""
        if self.last_reset is None:
            self.last_reset = datetime.now()
    @property
    def soft_limit_usd(self) -> float:
        """Soft limit in USD."""
        return self.daily_budget_usd * self.soft_limit_percent
    @property
    def hard_limit_usd(self) -> float:
        """Hard limit in USD."""
        return self.daily_budget_usd * self.hard_limit_percent
    @property
    def emergency_limit_usd(self) -> float:
        """Emergency limit in USD."""
        return self.daily_budget_usd * self.emergency_limit_percent
    @property
    def remaining_budget(self) -> float:
        """Remaining budget in USD."""
        return max(0, self.daily_budget_usd - self.current_spend)
    @property
    def usage_percent(self) -> float:
        """Current usage as percentage of daily budget."""
        return (self.current_spend / self.daily_budget_usd) * 100
    def should_reset(self) -> bool:
        """Check if daily budget should reset."""
        if self.last_reset is None:
            return True
        return datetime.now() - self.last_reset >= timedelta(days=1)
    def reset_if_needed(self):
        """Reset budget if 24 hours have passed."""
        if self.should_reset():
            self.current_spend = 0.0
            self.last_reset = datetime.now()
    def can_afford(self, estimated_cost: float, is_critical: bool = False) -> bool:
        """
        Check if request can be made within budget.
        Args:
            estimated_cost: Estimated cost in USD
            is_critical: Whether request is critical (bypass hard limit)
        Returns:
            True if request is within budget
        """
        self.reset_if_needed()
        projected_spend = self.current_spend + estimated_cost
        # Emergency limit blocks everything
        if projected_spend > self.emergency_limit_usd:
            return False
        # Hard limit blocks non-critical
        if not is_critical and projected_spend > self.hard_limit_usd:
            return False
        return True
    def record_spend(self, cost: float):
        """Record actual spend for tracking."""
        self.reset_if_needed()
        self.current_spend += cost
    def get_status(self) -> Dict[str, Any]:
        """Get current budget status."""
        self.reset_if_needed()
        return {
            "daily_budget": self.daily_budget_usd,
            "current_spend": self.current_spend,
            "remaining": self.remaining_budget,
            "usage_percent": self.usage_percent,
            "soft_limit_reached": self.current_spend >= self.soft_limit_usd,
            "hard_limit_reached": self.current_spend >= self.hard_limit_usd,
            "emergency_limit_reached": self.current_spend >= self.emergency_limit_usd,
            "last_reset": self.last_reset.isoformat() if self.last_reset else None,
        }
@dataclass
class TimeoutConfig:
    """
    Timeout configuration for API requests.
    Follows best practices for production deployments with
    separate timeouts for different operations.
    """
    total: float = 60.0 # Total request timeout
    read: float = 30.0 # Read timeout
    write: float = 10.0 # Write timeout
    connect: float = 5.0 # Connection timeout
    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary for SDK usage."""
        return {
            "total": self.total,
            "read": self.read,
            "write": self.write,
            "connect": self.connect,
        }
@dataclass
class RetryConfig:
    """Retry configuration for error handling."""
    max_retries: int = 2 # SDK default with exponential backoff
    max_strikes: int = 3 # 3-strike protocol for escalation
    # Fibonacci backoff delays (seconds)
    backoff_delays: List[float] = field(default_factory=lambda: [1, 2, 3, 5, 8])
    # Circuit breaker
    circuit_breaker_threshold: int = 5 # Consecutive failures before pause
    circuit_breaker_pause: float = 60.0 # Pause duration in seconds
@dataclass
class CacheConfig:
    """Prompt caching configuration."""
    default_ttl: str = "5min" # "5min" or "1hour"
    cache_threshold_tokens: int = 1024 # Minimum tokens to cache
    target_hit_rate: float = 0.75 # Target 75% cache hit rate
@dataclass
class Config:
    """Main configuration class - aggregates all config sections."""
    models: Dict[str, ModelConfig] = field(default_factory=lambda: MODELS)
    aliases: Dict[str, str] = field(default_factory=lambda: MODEL_ALIASES)
    beta: BetaHeaders = field(default_factory=BetaHeaders)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    timeout: TimeoutConfig = field(default_factory=TimeoutConfig)
    retry: RetryConfig = field(default_factory=RetryConfig)
    cache: CacheConfig = field(default_factory=CacheConfig)
    # Paths
    base_dir: Path = field(default_factory=lambda: Path.home() / ".claude")
    sessions_dir: Path = field(default_factory=lambda: Path.home() / ".claude" / "sessions")
    def resolve_model(self, model: str) -> ModelConfig:
        """Resolve model alias to full ModelConfig."""
        model_id = self.aliases.get(model, model)
        if model_id not in self.models:
            raise ValueError(f"Unknown model: {model}")
        return self.models[model_id]
    def get_model_for_task(self, task: str) -> str:
        """Route task to appropriate model based on keywords."""
        task_lower = task.lower()
        # Check for simple task indicators
        if any(kw in task_lower for kw in self.routing.simple_keywords):
            return self.routing.default_oneshot_model
        # Check for complex task indicators
        if any(kw in task_lower for kw in self.routing.complex_keywords):
            return self.routing.default_streaming_model
        # Default to simple (cost-effective)
        return self.routing.default_oneshot_model
    def with_model(self, model: str) -> "Config":
        """Create a new config with a different default model."""
        import copy
        new_config = copy.deepcopy(self)
        resolved = self.aliases.get(model, model)
        new_config.routing.default_oneshot_model = resolved
        new_config.routing.default_streaming_model = resolved
        new_config.routing.default_orchestrator_model = resolved
        return new_config
    @classmethod
    def from_env(cls) -> "Config":
        """Create config with environment variable overrides."""
        config = cls()
        # Override daily budget from env
        if budget := os.getenv("SDK_DAILY_BUDGET"):
            config.budget.daily_budget_usd = float(budget)
        # Override default model from env
        if model := os.getenv("SDK_DEFAULT_MODEL"):
            config.routing.default_oneshot_model = model
        return config
# Global config instance
_config: Optional[Config] = None
def get_config() -> Config:
    """Get or create global config instance."""
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config
