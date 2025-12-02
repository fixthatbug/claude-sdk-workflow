"""Cache Manager - Context caching and monitoring.

Re-exports from cache.py with unified interface.
"""

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
    
    MIN_CACHE_TOKENS = 1024
    MAX_ENTRIES = 10
    
    def __init__(self, ttl_minutes: int = 5):
        self.default_ttl = ttl_minutes
        self._cache: Dict[str, CacheEntry] = {}
        self._stats = {"hits": 0, "misses": 0, "evictions": 0}
    
    def should_cache(self, content: str, tokens: int) -> bool:
        return tokens >= self.MIN_CACHE_TOKENS
    
    def cache(self, key: str, content: str, tokens: int) -> bool:
        if not self.should_cache(content, tokens):
            return False
        
        if len(self._cache) >= self.MAX_ENTRIES:
            self._evict_oldest()
        
        self._cache[key] = CacheEntry(
            key=key, content=content, tokens=tokens, ttl_minutes=self.default_ttl
        )
        return True
    
    def get(self, key: str) -> Optional[str]:
        if key not in self._cache:
            self._stats["misses"] += 1
            return None
        
        entry = self._cache[key]
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
        if not self._cache:
            return
        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].last_accessed)
        del self._cache[oldest_key]
        self._stats["evictions"] += 1
    
    def clear(self) -> int:
        count = len(self._cache)
        self._cache.clear()
        return count
    
    def get_stats(self) -> Dict[str, Any]:
        total = self._stats["hits"] + self._stats["misses"]
        return {
            **self._stats,
            "entries": len(self._cache),
            "hit_rate": self._stats["hits"] / total if total > 0 else 0,
            "total_tokens_cached": sum(e.tokens for e in self._cache.values()),
        }


class CacheMonitor:
    """Monitor cache efficiency."""
    
    def __init__(self, cache_manager: ContextCacheManager):
        self.cache = cache_manager
        self._samples: List[Dict] = []
        self._max_samples = 100
    
    def record_request(self, input_tokens: int, cache_read_tokens: int, cache_write_tokens: int) -> None:
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


class ContextEditingManager:
    """Manage context window editing and optimization."""
    
    def __init__(self, max_context_tokens: int = 200000):
        self.max_tokens = max_context_tokens
        self._edits: List[Dict] = []
    
    def estimate_tokens(self, content: str) -> int:
        return len(content) // 4
    
    def compact(self, messages: List[Dict], target_tokens: int) -> List[Dict]:
        total = sum(self.estimate_tokens(m.get("content", "")) for m in messages)
        
        if total <= target_tokens:
            return messages
        
        compacted = []
        if messages and messages[0].get("role") == "system":
            compacted.append(messages[0])
            messages = messages[1:]
        
        remaining = target_tokens - sum(self.estimate_tokens(m.get("content", "")) for m in compacted)
        
        for msg in reversed(messages):
            msg_tokens = self.estimate_tokens(msg.get("content", ""))
            if msg_tokens <= remaining:
                compacted.insert(-1 if compacted else 0, msg)
                remaining -= msg_tokens
            else:
                break
        
        return compacted


# Unified CacheManager that combines all functionality
class CacheManager:
    """Unified cache manager combining all cache functionality."""
    
    def __init__(self, ttl_minutes: int = 5, max_context_tokens: int = 200000):
        self.context_cache = ContextCacheManager(ttl_minutes)
        self.monitor = CacheMonitor(self.context_cache)
        self.context_editor = ContextEditingManager(max_context_tokens)
    
    def cache(self, key: str, content: str, tokens: int) -> bool:
        return self.context_cache.cache(key, content, tokens)
    
    def get(self, key: str) -> Optional[str]:
        return self.context_cache.get(key)
    
    def record_request(self, input_tokens: int, cache_read: int, cache_write: int) -> None:
        self.monitor.record_request(input_tokens, cache_read, cache_write)
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "cache": self.context_cache.get_stats(),
            "efficiency": self.monitor.get_efficiency(),
        }
    
    def compact_messages(self, messages: List[Dict], target_tokens: int) -> List[Dict]:
        return self.context_editor.compact(messages, target_tokens)


__all__ = [
    "CacheEntry",
    "ContextCacheManager",
    "CacheMonitor",
    "ContextEditingManager",
    "CacheManager",
]
