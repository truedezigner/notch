from __future__ import annotations

import asyncio
import time


class ChangeFeed:
    """Process-local wake-up signal for authenticated native clients.

    Notch currently runs as one Uvicorn process. The revision starts from wall-clock
    nanoseconds so a restarted process also causes connected clients to refresh.
    Durable data continues to live only in SQLite; this feed carries no content.
    """

    def __init__(self) -> None:
        self._condition = asyncio.Condition()
        self._revision = time.time_ns()

    async def current(self) -> int:
        async with self._condition:
            return self._revision

    async def publish(self) -> int:
        async with self._condition:
            self._revision += 1
            self._condition.notify_all()
            return self._revision

    async def wait(self, since: int, timeout_seconds: float) -> tuple[int, bool]:
        async with self._condition:
            if self._revision != since:
                return self._revision, True
            try:
                await asyncio.wait_for(
                    self._condition.wait_for(lambda: self._revision != since),
                    timeout=timeout_seconds,
                )
            except TimeoutError:
                return self._revision, False
            return self._revision, True


change_feed = ChangeFeed()
