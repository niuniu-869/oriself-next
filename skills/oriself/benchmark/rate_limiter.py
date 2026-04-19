"""
异步令牌桶 · 给整个 benchmark 装一个全局 RPM 上限。

实现：单消费者 async token bucket。capacity = rpm，refill_rate = rpm/60 token/秒。
每次 LLM 调用前 `await limiter.acquire(1)`，桶里没令牌就等。
"""
from __future__ import annotations

import asyncio
import time


class AsyncRateLimiter:
    def __init__(self, rpm: int):
        self.rpm = rpm
        self.capacity = float(rpm)
        self.tokens = float(rpm)
        self.refill_rate = rpm / 60.0  # per second
        self._last = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, n: float = 1.0) -> float:
        """获取 n 个令牌，返回等待的秒数（用于观测）。"""
        total_wait = 0.0
        while True:
            async with self._lock:
                now = time.monotonic()
                elapsed = now - self._last
                self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
                self._last = now
                if self.tokens >= n:
                    self.tokens -= n
                    return total_wait
                missing = n - self.tokens
                wait = missing / self.refill_rate
            total_wait += wait
            await asyncio.sleep(wait)
