from __future__ import annotations

import json

import httpx

from .settings import settings


async def publish(*, topic: str, title: str, message: str, click_url: str | None = None, priority: int | None = None, tags: list[str] | None = None) -> None:
    url = settings.NTFY_BASE_URL.rstrip("/") + "/" + topic.lstrip("/")
    headers = {}
    if title:
        headers["Title"] = title
    if click_url:
        headers["Click"] = click_url
    if priority is not None:
        headers["Priority"] = str(priority)
    if tags:
        headers["Tags"] = ",".join(tags)

    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.post(url, content=message.encode("utf-8"), headers=headers)
        r.raise_for_status()


def topic_for_handle(handle: str) -> str:
    return f"{settings.NTFY_TOPIC_PREFIX}{handle}".lower()
