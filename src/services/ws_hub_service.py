from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List

from fastapi import WebSocket, WebSocketDisconnect


class WebSocketHub:
    """Track websocket clients and fan out runner updates."""

    def __init__(self, *, max_clients: int, logger: Any):
        self.max_clients = max(1, int(max_clients))
        self.logger = logger
        self.clients: List[WebSocket] = []

    async def broadcast(self, message: Dict[str, Any]) -> None:
        if not self.clients:
            return

        message_text = json.dumps(message, default=str)
        clients = list(self.clients)
        results = await asyncio.gather(
            *(client.send_text(message_text) for client in clients),
            return_exceptions=True,
        )

        disconnected: List[WebSocket] = []
        for client, result in zip(clients, results):
            if isinstance(result, Exception):
                disconnected.append(client)

        for client in disconnected:
            self._disconnect(client)

    async def handle_connection(self, websocket: WebSocket) -> None:
        if len(self.clients) >= self.max_clients:
            await websocket.close(code=1013, reason="Too many websocket clients")
            return

        await websocket.accept()
        self.clients.append(websocket)
        self.logger.info("WebSocket client connected. Total: %s", len(self.clients))

        try:
            while True:
                data = await websocket.receive_text()
                await self._handle_client_message(websocket, data)
        except WebSocketDisconnect:
            pass
        finally:
            self._disconnect(websocket)
            self.logger.info(
                "WebSocket client disconnected. Remaining: %s", len(self.clients)
            )

    def _disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.clients:
            self.clients.remove(websocket)

    async def _handle_client_message(self, websocket: WebSocket, data: str) -> None:
        try:
            msg = json.loads(data)
        except json.JSONDecodeError:
            return

        message_type = msg.get("type")
        if message_type == "ping":
            await websocket.send_json({"type": "pong"})
            return
        if message_type == "subscribe":
            run_id = msg.get("run_id")
            await websocket.send_json(
                {
                    "type": "subscribed",
                    "run_id": run_id,
                }
            )
