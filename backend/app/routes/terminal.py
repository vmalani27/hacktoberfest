import asyncio
import json
import logging
import aiodocker
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.config import settings
from app.state_machine import session_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["Terminal"])

@router.websocket("/terminal/{session_id}")
async def terminal_websocket(websocket: WebSocket, session_id: str):
    await websocket.accept()
    container_name = settings.SANDBOX_CONTAINER_NAME

    docker = aiodocker.Docker()
    try:
        try:
            container = await docker.containers.get(container_name)
        except Exception:
            await websocket.send_text(
                f"\r\n\x1b[33m[Notice] Sandbox container '{container_name}' is starting or not reachable.\x1b[0m\r\n"
            )
            await docker.close()
            await websocket.close(code=1000)
            return

        # Resolve project folder for this session
        session = session_manager.sessions.get(session_id)
        target_dir = session.repo_path if (session and session.repo_path) else "/workspace"

        # Start an interactive TTY shell into the sandbox inside the project folder
        shell_cmd = [
            "/bin/sh", "-c",
            f"mkdir -p '{target_dir}' && cd '{target_dir}' && (command -v bash >/dev/null 2>&1 && exec bash -l || exec sh -l)"
        ]
        exec_obj = await container.exec(
            cmd=shell_cmd,
            stdin=True,
            stdout=True,
            stderr=True,
            tty=True,
            workdir="/workspace"
        )
        stream = exec_obj.start(detach=False)

        async with stream:
            async def ws_to_exec():
                try:
                    while True:
                        msg = await websocket.receive()
                        if msg.get("type") == "websocket.disconnect":
                            return
                        data = msg.get("bytes")
                        if data is None:
                            text = msg.get("text")
                            if text is None:
                                continue
                            try:
                                json_msg = json.loads(text)
                                if isinstance(json_msg, dict) and json_msg.get("type") == "resize":
                                    cols = int(json_msg.get("cols", 80))
                                    rows = int(json_msg.get("rows", 24))
                                    try:
                                        await exec_obj.resize(w=cols, h=rows)
                                    except Exception:
                                        pass
                                    continue
                            except Exception:
                                pass
                            data = text.encode("utf-8")
                        await stream.write_in(data)
                except (WebSocketDisconnect, asyncio.CancelledError):
                    pass
                except Exception as e:
                    logger.debug(f"ws_to_exec error: {e}")

            async def exec_to_ws():
                try:
                    while True:
                        output = await stream.read_out()
                        if output is None:
                            break
                        if output.data:
                            await websocket.send_bytes(output.data)
                except (WebSocketDisconnect, asyncio.CancelledError):
                    pass
                except Exception as e:
                    logger.debug(f"exec_to_ws error: {e}")

            task1 = asyncio.create_task(ws_to_exec())
            task2 = asyncio.create_task(exec_to_ws())
            done, pending = await asyncio.wait([task1, task2], return_when=asyncio.FIRST_COMPLETED)
            for p in pending:
                p.cancel()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"Terminal session error: {e}")
    finally:
        await docker.close()
