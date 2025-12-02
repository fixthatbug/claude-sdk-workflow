"""Cache Management - Context caching and monitoring."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached context entry."""
    key: str
    content: str
    tokens: int
    created_at: datetime = field(default_factory=datetime.now)
    last_accessed: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    ttl_minutes: int = 5


class ContextCacheManager:
    """Manage context caching for efficient token usage."""
    
    # Minimum tokens for caching to be worthwhile
    MIN_CACHE_TOKENS = 1024
    # Maximum cached entries
    MAX_ENTRIES = 10
    
    def __init__(self, ttl_minutes: int = 5):
        self.default_ttl = ttl_minutes
        self._cache: Dict[str, CacheEntry] = {}
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}
    
    def should_cache(self, content: str, tokens: int) -> bool:
        """Determine if content should be cached."""
        return tokens >= self.MIN_CACHE_TOKENS
    
    def cache(self, key: str, content: str, tokens: int) -> bool:
        """Cache content if appropriate."""
        if not self.should_cache(content, tokens):
            return False
        
        # Evict if at capacity
        if len(self._cache) >= self.MAX_ENTRIES:
            self._evict_oldest()
        
        self._cache[key] = CacheEntry(
            key=key,
            content=content,
            tokens=tokens,
            ttl_minutes=self.default_ttl
        )
        return True
    
    def get(self, key: str) -> Optional[str]:
        """Retrieve cached content."""
        if key not in self._cache:
            self._stats["misses"] += 1
            return None
        
        entry = self._cache[key]
        
        # Check TTL
        age = datetime.now() - entry.created_at
        if age > timedelta(minutes=entry.ttl_minutes):
            del self._cache[key]
            self._stats["misses"] += 1
            return None
        
        entry.last_accessed = datetime.now()
        entry.access_count += 1
        self._stats["hits"] += 1
        
        return entry.content
    
    def _evict_oldest(self) -> None:
        """Evict least recently used entry."""
        if not self._cache:
            return
        
        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_accessed)
        del self._cache[oldest_key]
        self._stats["evictions"] += 1
    
    def clear(self) -> int:
        """Clear all cached entries. Returns count cleared."""
        count = len(self._cache)
        self._cache.clear()
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        return {
            **self._stats,
            "entries": len(self._cache),
            "hit_rate": self._stats["hits"] / total if total > 0 else 0,
            "total_tokens_cached": sum(e.tokens for e in self._cache.values()),
        }


class CacheMonitor:
    """Monitor cache efficiency and provide optimization suggestions."""
    
    def __init__(self, cache_manager: ContextCacheManager):
        self.cache = cache_manager
        self._samples: List[Dict] = []
        self._max_samples = 100
    
    def record_request(
        self,
        input_tokens: int,
        cache_read_tokens: int,
        cache_write_tokens: int,
    ) -> None:
        """Record a request for analysis."""
        sample = {
            "timestamp": datetime.now(),
            "input_tokens": input_tokens,
            "cache_read": cache_read_tokens,
            "cache_write": cache_write_tokens,
            "savings_ratio": cache_read_tokens / input_tokens if input_tokens > 0 else 0,
        }
        
        self._samples.append(sample)
        if len(self._samples) > self._max_samples:
            self._samples.pop(0)
    
    def get_efficiency(self) -> Dict[str, float]:
        """Calculate cache efficiency metrics."""
        if not self._samples:
            return {"savings_ratio": 0, "avg_cache_read": 0, "recommendation": "insufficient_data"}
        
        avg_savings = sum(s["savings_ratio"] for s in self._samples) / len(self._samples)
        avg_read = sum(s["cache_read"] for s in self._samples) / len(self._samples)
        
        recommendation = "good"
        if avg_savings < 0.1:
            recommendation = "increase_caching"
        elif avg_savings > 0.7:
            recommendation = "optimal"
        
        return {
            "savings_ratio": avg_savings,
            "avg_cache_read": avg_read,
            "samples": len(self._samples),
            "recommendation": recommendation,
        }
    
    def suggest_cache_candidates(self, content: str, threshold: int = 2000) -> List[str]:
        """Suggest content sections that would benefit from caching."""
        candidates = []
        
        # Look for repeated or large blocks
        lines = content.split('\n')
        blocks = []
        current_block = []
        
        for line in lines:
            if line.strip():
                current_block.append(line)
            elif current_block:
                blocks.append('\n'.join(current_block))
                current_block = []
        
        if current_block:
            blocks.append('\n'.join(current_block))
        
        # Suggest blocks over threshold
        for block in blocks:
            estimated_tokens = len(block) // 4  # Rough estimate
            if estimated_tokens >= threshold:
                candidates.append(block[:100] + "..." if len(block) > 100 else block)
        
        return candidates


class ContextEditingManager:
    """Manage context window editing and optimization."""
    
    def __init__(self, max_context_tokens: int = 200000):
        self.max_tokens = max_context_tokens
        self._edits: List[Dict] = []
    
    def estimate_tokens(self, content: str) -> int:
        """Estimate token count for content."""
        return len(content) // 4  # Rough approximation
    
    def compact(self, messages: List[Dict], target_tokens: int) -> List[Dict]:
        """Compact message history to fit target token budget."""
        total = sum(self.estimate_tokens(m.get("content", "")) for m in messages)
        
        if total <= target_tokens:
            return messages
        
        # Keep system message and recent messages
        compacted = []
        if messages and messages[0].get("role") == "system":
            compacted.append(messages[0])
            messages = messages[1:]
        
        # Prioritize recent messages
        remaining = target_tokens - sum(self.estimate_tokens(m.get("content", "")) for m in compacted)
        
        for msg in reversed(messages):
            msg_tokens = self.estimate_tokens(msg.get("content", ""))
            if msg_tokens <= remaining:
                compacted.insert(-1 if compacted else 0, msg)
                remaining -= msg_tokens
            else:
                break
        
        self._edits.append({
            "timestamp": datetime.now(),
            "original_tokens": total,
            "compacted_tokens": target_tokens - remaining,
            "messages_removed": len(messages) - len(compacted) + 1,
        })
        
        return compacted
    
    def summarize_for_context(self, content: str, max_tokens: int = 1000) -> str:
        """Create a summarized version for context inclusion."""
        estimated = self.estimate_tokens(content)
        if estimated <= max_tokens:
            return content
        
        # Simple truncation with summary marker
        target_chars = max_tokens * 4
        truncated = content[:target_chars]
        
        return f"{truncated}\n\n[Content truncated from {estimated} to {max_tokens} tokens]"


__all__ = [
    'CacheEntry',
    'ContextCacheManager',
    'CacheMonitor',
    'ContextEditingManager',
]
