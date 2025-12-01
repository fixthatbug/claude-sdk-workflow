"""
Configuration - Single Source of Truth for SDK Workflow.
Contains: pricing, model configs, thresholds, beta headers, budgets.
"""
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional
import os
class ModelTier(Enum):
    """Model tiers for routing decisions."""
    HAIKU = "haiku"
    SONNET = "sonnet"
    OPUS = "opus"
@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    model_id: str
    input_price_per_mtok: float # Price per million input tokens
    output_price_per_mtok: float # Price per million output tokens
    max_tokens: int
    context_window: int
    tier: ModelTier
    @property
    def cache_read_price(self) -> float:
        """Cache read is 10% of base input price (90% discount)."""
        return self.input_price_per_mtok * 0.1
    @property
    def cache_write_price(self) -> float:
        """Cache write is 125% of base input price."""
        return self.input_price_per_mtok * 1.25
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
    """Beta feature headers for API requests."""
    code_execution: str = "code-execution-2025-08-25"
    files_api: str = "files-api-2025-04-14"
    skills: str = "skills-2025-10-02"
    context_management: str = "context-management-2025-06-27"
    fine_grained_tools: str = "fine-grained-tool-streaming-2025-05-14"
    structured_outputs: str = "structured-outputs-2025-11-13"
    def get_list(self, *features: str) -> List[str]:
        """Get list of beta headers for specified features."""
        mapping = {
            "code_execution": self.code_execution,
            "files": self.files_api,
            "skills": self.skills,
            "context": self.context_management,
            "tools": self.fine_grained_tools,
            "structured": self.structured_outputs,
        }
        return [mapping[f] for f in features if f in mapping]
@dataclass
class RoutingConfig:
    """Configuration for model routing decisions."""
    # Keywords that suggest simple tasks (use Haiku)
    simple_keywords: List[str] = field(default_factory=lambda: [
        "extract", "format", "validate", "check", "list", "count",
        "quick", "just", "simply", "get", "find", "show"
    ])
    # Keywords that suggest complex tasks (use Sonnet)
    complex_keywords: List[str] = field(default_factory=lambda: [
        "refactor", "architect", "design", "research", "implement",
        "build", "create", "analyze", "optimize", "review"
    ])
    # Escalation triggers (quality issues in response)
    escalation_markers: List[str] = field(default_factory=lambda: [
        "I cannot", "I'm not sure", "I don't have", "unable to",
        "I apologize", "I'm unable"
    ])
    # Minimum response length (shorter = potential quality issue)
    min_quality_length: int = 50
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
    """Budget thresholds and limits."""
    daily_budget_usd: float = 10.0
    soft_limit_percent: float = 0.80 # Warn at 80%
    hard_limit_percent: float = 1.00 # Block non-critical at 100%
    emergency_limit_percent: float = 1.20 # Block all at 120%
    # Per-request limits
    max_input_tokens: int = 100_000
    max_output_tokens: int = 16_000
@dataclass
class TimeoutConfig:
    """Timeout configuration for API requests."""
    total: float = 60.0
    read: float = 30.0
    write: float = 10.0
    connect: float = 5.0
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
