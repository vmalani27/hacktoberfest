import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.state_machine import session_manager

router = APIRouter(prefix="/ws", tags=["WebSocket"])

@router.websocket("/agent/{session_id}")
async def agent_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    session = session_manager.get_or_create_session(session_id=session_id)
    
    # Send initial state snapshot
    await websocket.send_text(json.dumps({
        "type": "state_sync",
        "data": session.model_dump()
    }))

    try:
        while True:
            raw_data = await websocket.receive_text()
            payload = json.loads(raw_data)
            action = payload.get("action")

            if action == "step":
                session = await session_manager.step(session_id)
            elif action == "approve":
                session = await session_manager.handle_approval(
                    session_id=session_id,
                    tool_call_id=payload.get("tool_call_id"),
                    approved=payload.get("approved", True),
                    modified_arguments=payload.get("modified_arguments"),
                    feedback=payload.get("feedback")
                )
            elif action == "answer":
                q_id = payload.get("question_id")
                ans = payload.get("answer")
                session.answers[q_id] = ans
                session.messages.append(ChatMessage(role="user", content=f"User selection for {q_id}: {ans}"))
                if session.current_tool_call and session.current_tool_call.tool_name == "ask_user":
                    session.current_tool_call = None
                if len(session.answers) >= 1 and session.stage == StageEnum.INTERVIEW:
                    session.stage = StageEnum.PLAN
                session = await session_manager.step(session_id)

            # Broadcast latest state back to client
            await websocket.send_text(json.dumps({
                "type": "state_sync",
                "data": session.model_dump()
            }))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": str(e)
        }))
