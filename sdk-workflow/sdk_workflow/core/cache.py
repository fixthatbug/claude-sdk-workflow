"""Prompt caching optimizer for Claude API requests.
Implements a 4-tier caching strategy to maximize cache hits and reduce costs:
1. System prompt (most stable, cached first)
2. Tool definitions (stable across session)
3. Conversation history (grows, cached for context)
4. Current message (dynamic, not cached)
"""
from typing import Any, Optional
from copy import deepcopy
class PromptCacheOptimizer:
    """Optimizes API requests with cache_control markers for prompt caching.
    Claude's prompt caching provides up to 90% cost reduction on cached
    content. This optimizer strategically places cache_control markers to
    maximize cache utilization.
    Cache Tiers:
        1. System Prompt: Most stable, rarely changes. Always cached.
        2. Tools: Stable within session. Cached after system prompt.
        3. History: Conversation context. Cached incrementally.
        4. Current: User's latest message. Never cached (always new).
    Usage:
        optimizer = PromptCacheOptimizer()
        request = optimizer.build_cached_request(
            system="You are a helpful assistant.",
            tools=[{"name": "search", ...}],
            history=[{"role": "user", "content": "Hello"}],
            current="What's the weather?"
        )
        response = client.messages.create(**request)
    """
    # Minimum tokens for caching to be beneficial (Claude API requirement)
    MIN_CACHE_TOKENS = 1024
    # Estimated tokens per character (rough approximation)
    TOKENS_PER_CHAR = 0.25
    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        """Initialize the cache optimizer.
        Args:
            model: Default model to use in requests.
        """
        self.model = model
    def _estimate_tokens(self, content: Any) -> int:
        """Estimate token count for content.
        Args:
            content: String or structured content to estimate.
        Returns:
            Estimated token count.
        """
        if isinstance(content, str):
            return int(len(content) * self.TOKENS_PER_CHAR)
        elif isinstance(content, list):
            return sum(self._estimate_tokens(item) for item in content)
        elif isinstance(content, dict):
            return self._estimate_tokens(str(content))
        return 0
    def _add_cache_control(self, content: Any, cache_type: str = "ephemeral") -> Any:
        """Add cache_control marker to content.
        Args:
            content: Content to mark for caching.
            cache_type: Cache type (currently only "ephemeral" supported).
        Returns:
            Content with cache_control marker added.
        """
        if isinstance(content, str):
            return {
                "type": "text",
                "text": content,
                "cache_control": {"type": cache_type}
            }
        elif isinstance(content, dict):
            result = deepcopy(content)
            result["cache_control"] = {"type": cache_type}
            return result
        elif isinstance(content, list):
            if not content:
                return content
            # Add cache control to last item in list
            result = deepcopy(content)
            last_item = result[-1]
            if isinstance(last_item, dict):
                last_item["cache_control"] = {"type": cache_type}
            elif isinstance(last_item, str):
                result[-1] = {
                    "type": "text",
                    "text": last_item,
                    "cache_control": {"type": cache_type}
                }
            return result
        return content
    def _build_system_content(self, system: str) -> list[dict]:
        """Build system content with cache control.
        Tier 1: System prompt is the most stable content.
        Always marked for caching if it exceeds minimum token threshold.
        Args:
            system: System prompt text.
        Returns:
            List of content blocks with appropriate cache markers.
        """
        if self._estimate_tokens(system) >= self.MIN_CACHE_TOKENS:
            return [self._add_cache_control(system)]
        return [{"type": "text", "text": system}]
    def _build_tools_with_cache(self, tools: list[dict]) -> list[dict]:
        """Build tools array with cache control on last tool.
        Tier 2: Tools are stable within a session.
        Cache marker on last tool captures all tool definitions.
        Args:
            tools: List of tool definitions.
        Returns:
            Tools list with cache control on last item.
        """
        if not tools:
            return []
        result = deepcopy(tools)
        if self._estimate_tokens(tools) >= self.MIN_CACHE_TOKENS:
            result[-1] = self._add_cache_control(result[-1])
        return result
    def _build_history_with_cache(
        self,
        history: list[dict],
        cache_breakpoints: Optional[list[int]] = None
    ) -> list[dict]:
        """Build conversation history with strategic cache breakpoints.
        Tier 3: History grows over conversation.
        Cache at strategic points to enable incremental caching.
        Args:
            history: List of previous messages.
            cache_breakpoints: Indices to place cache markers (optional).
                              If None, caches at end of history.
        Returns:
            History with cache control markers at breakpoints.
        """
        if not history:
            return []
        result = deepcopy(history)
        # Default: cache at end of history
        if cache_breakpoints is None:
            if len(result) > 0 and self._estimate_tokens(history) >= self.MIN_CACHE_TOKENS:
                last_msg = result[-1]
                if isinstance(last_msg.get("content"), str):
                    result[-1]["content"] = [self._add_cache_control(last_msg["content"])]
                elif isinstance(last_msg.get("content"), list) and last_msg["content"]:
                    result[-1]["content"] = self._add_cache_control(last_msg["content"])
        else:
            # Cache at specified breakpoints
            for idx in cache_breakpoints:
                if 0 <= idx < len(result):
                    msg = result[idx]
                    if isinstance(msg.get("content"), str):
                        result[idx]["content"] = [self._add_cache_control(msg["content"])]
                    elif isinstance(msg.get("content"), list) and msg["content"]:
                        result[idx]["content"] = self._add_cache_control(msg["content"])
        return result
    def _build_current_message(self, current: str) -> dict:
        """Build the current user message.
        Tier 4: Current message is always new/dynamic.
        Never cached as it changes with each request.
        Args:
            current: Current user message text.
        Returns:
            Message dict without cache control.
        """
        return {
            "role": "user",
            "content": current
        }
    def build_cached_request(
        self,
        system: str,
        tools: Optional[list[dict]] = None,
        history: Optional[list[dict]] = None,
        current: str = "",
        model: Optional[str] = None,
        max_tokens: int = 4096,
        cache_breakpoints: Optional[list[int]] = None,
        **kwargs
    ) -> dict:
        """Build a complete API request with optimized caching.
        Implements 4-tier caching strategy:
        1. System prompt (cached if >= 1024 tokens)
        2. Tools (cached if >= 1024 tokens)
        3. History (cached at breakpoints or end)
        4. Current message (never cached)
        Args:
            system: System prompt text.
            tools: Optional list of tool definitions.
            history: Optional list of previous messages.
            current: Current user message.
            model: Model to use (defaults to instance model).
            max_tokens: Maximum response tokens.
            cache_breakpoints: Optional indices for history cache points.
            **kwargs: Additional API parameters.
        Returns:
            Complete request dict ready for client.messages.create().
        Example:
            >>> optimizer = PromptCacheOptimizer()
            >>> request = optimizer.build_cached_request(
            ... system="You are a coding assistant.",
            ... tools=[{"name": "run_code", "description": "Execute Python"}],
            ... history=[
            ... {"role": "user", "content": "Hello"},
            ... {"role": "assistant", "content": "Hi!"}
            ... ],
            ... current="Write a function to sort a list"
            ... )
            >>> response = client.messages.create(**request)
        """
        # Build messages list
        messages = []
        # Add cached history (Tier 3)
        if history:
            messages.extend(
                self._build_history_with_cache(history, cache_breakpoints)
            )
        # Add current message (Tier 4 - no cache)
        if current:
            messages.append(self._build_current_message(current))
        # Build request
        request = {
            "model": model or self.model,
            "max_tokens": max_tokens,
            "system": self._build_system_content(system), # Tier 1
            "messages": messages,
            **kwargs
        }
        # Add cached tools (Tier 2)
        if tools:
            request["tools"] = self._build_tools_with_cache(tools)
        return request
    def estimate_cache_savings(
        self,
        system: str,
        tools: Optional[list[dict]] = None,
        history: Optional[list[dict]] = None
    ) -> dict:
        """Estimate potential cache savings for given content.
        Args:
            system: System prompt text.
            tools: Optional tool definitions.
            history: Optional conversation history.
        Returns:
            Dict with token estimates and potential savings percentage.
        """
        system_tokens = self._estimate_tokens(system)
        tools_tokens = self._estimate_tokens(tools) if tools else 0
        history_tokens = self._estimate_tokens(history) if history else 0
        cacheable_tokens = 0
        if system_tokens >= self.MIN_CACHE_TOKENS:
            cacheable_tokens += system_tokens
        if tools_tokens >= self.MIN_CACHE_TOKENS:
            cacheable_tokens += tools_tokens
        if history_tokens >= self.MIN_CACHE_TOKENS:
            cacheable_tokens += history_tokens
        total_tokens = system_tokens + tools_tokens + history_tokens
        cache_ratio = cacheable_tokens / total_tokens if total_tokens > 0 else 0
        return {
            "system_tokens": system_tokens,
            "tools_tokens": tools_tokens,
            "history_tokens": history_tokens,
            "total_tokens": total_tokens,
            "cacheable_tokens": cacheable_tokens,
            "cache_ratio": cache_ratio,
            "potential_savings_percent": cache_ratio * 90 # 90% discount on cached
        }
