import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.auth.jwt import decode_token
from app.core.websockets import ws_manager

ws_router = APIRouter(tags=["WebSockets"])


@ws_router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
):
    try:
        payload = decode_token(token)
        user_id_str = payload.get("sub")
        org_id_str = payload.get("org_id")

        if not user_id_str or not org_id_str:
            await websocket.close(code=4001)
            return

        user_id = uuid.UUID(user_id_str)
        org_id = uuid.UUID(org_id_str)
    except Exception:
        await websocket.close(code=4003)
        return

    await ws_manager.connect(websocket, org_id, user_id)

    try:
        while True:
            data = await websocket.receive_text()
            # Respond to client ping/heartbeats
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, org_id, user_id)
    except Exception:
        ws_manager.disconnect(websocket, org_id, user_id)
