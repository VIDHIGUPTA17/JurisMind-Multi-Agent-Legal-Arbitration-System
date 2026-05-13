"""
SSE streaming endpoint for real-time arbitration stage updates.

GET /cases/{case_id}/arbitration/stream
"""
import asyncio
import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from fastapi.responses import StreamingResponse

from app.agents.orchestrator import subscribe_to_case, unsubscribe_from_case
from app.core.security import get_current_user_id, decode_token

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cases", tags=["stream"])


@router.get("/{case_id}/arbitration/stream")
async def stream_arbitration(
    case_id: str,
    token: Optional[str] = Query(None),
    user_id: Optional[str] = Depends(get_current_user_id) if False else None,
):
    # Accept token via query param (EventSource API can't set headers)
    if token:
        try:
            payload = decode_token(token)
            resolved_user_id = payload.get("sub")
        except Exception:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token required")
    """
    Server-Sent Events stream for a case arbitration pipeline.
    Each event has `type` and `data` fields.
    """
    queue = subscribe_to_case(case_id)
    logger.info("sse_subscribed", extra={"case_id": case_id, "user_id": resolved_user_id})

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    payload = json.dumps(event["data"])
                    yield f"event: {event['type']}\ndata: {payload}\n\n"
                    if event["type"] == "verdict_ready":
                        break
                except asyncio.TimeoutError:
                    # Keep-alive ping
                    yield ": ping\n\n"
        finally:
            unsubscribe_from_case(case_id, queue)
            logger.info("sse_unsubscribed", extra={"case_id": case_id})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
