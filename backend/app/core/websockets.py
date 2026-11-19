import json
import uuid
from typing import Dict, Set, Any
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # Maps org_id -> Dict[user_id, Set[WebSocket]]
        self._org_connections: Dict[uuid.UUID, Dict[uuid.UUID, Set[WebSocket]]] = {}

    async def connect(self, websocket: WebSocket, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
        await websocket.accept()
        if org_id not in self._org_connections:
            self._org_connections[org_id] = {}
        if user_id not in self._org_connections[org_id]:
            self._org_connections[org_id][user_id] = set()
        self._org_connections[org_id][user_id].add(websocket)

    def disconnect(self, websocket: WebSocket, org_id: uuid.UUID, user_id: uuid.UUID) -> None:
        if org_id in self._org_connections:
            if user_id in self._org_connections[org_id]:
                self._org_connections[org_id][user_id].discard(websocket)
                if not self._org_connections[org_id][user_id]:
                    del self._org_connections[org_id][user_id]
            if not self._org_connections[org_id]:
                del self._org_connections[org_id]

    async def broadcast_to_org(self, org_id: uuid.UUID, event: str, payload: Dict[str, Any]) -> None:
        """Broadcasts event strictly to connected users belonging to the specified tenant."""
        if org_id not in self._org_connections:
            return

        message = json.dumps({"event": event, "data": payload})
        stale_sockets = []

        for user_id, sockets in list(self._org_connections[org_id].items()):
            for ws in list(sockets):
                try:
                    await ws.send_text(message)
                except Exception:
                    stale_sockets.append((user_id, ws))

        for u_id, s in stale_sockets:
            self.disconnect(s, org_id, u_id)

    async def send_to_user(self, org_id: uuid.UUID, user_id: uuid.UUID, event: str, payload: Dict[str, Any]) -> None:
        """Sends event directly to a specific user inside the tenant."""
        if org_id not in self._org_connections or user_id not in self._org_connections[org_id]:
            return

        message = json.dumps({"event": event, "data": payload})
        stale_sockets = []

        for ws in list(self._org_connections[org_id][user_id]):
            try:
                await ws.send_text(message)
            except Exception:
                stale_sockets.append(ws)

        for s in stale_sockets:
            self.disconnect(s, org_id, user_id)


ws_manager = ConnectionManager()
