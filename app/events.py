"""Diffusion des événements MQTT vers tous les clients WebSocket."""

from __future__ import annotations

import asyncio
from typing import Any


class WsEventHub:
    """Un événement MQTT est envoyé à chaque abonné WebSocket (pas une queue partagée)."""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        self._subscribers.discard(queue)

    def publish(self, event: dict[str, Any]) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass
