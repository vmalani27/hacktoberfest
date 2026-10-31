import socket
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Request, Response, HTTPException
import httpx
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/sandbox", tags=["Sandbox"])

# Common web application ports to probe
CANDIDATE_PORTS = [3000, 5000, 8000, 8080, 5173, 4000, 8888, 9000, 4200, 80]

@router.get("/ports")
async def get_open_ports() -> List[Dict[str, Any]]:
    """Probes the sandbox container to detect any active listening HTTP ports."""
    target_host = settings.SANDBOX_CONTAINER_NAME
    open_ports = []

    for port in CANDIDATE_PORTS:
        is_open = False
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.2)
                res = s.connect_ex((target_host, port))
                if res == 0:
                    is_open = True
        except Exception:
            is_open = False

        if is_open:
            open_ports.append({
                "port": port,
                "url": f"/api/sandbox/proxy/{port}/",
                "label": f"Port {port}"
            })

    return open_ports

@router.get("/ports/{port}")
async def check_port(port: int) -> Dict[str, Any]:
    """Check if a specific port is listening inside the sandbox."""
    target_host = settings.SANDBOX_CONTAINER_NAME
    is_open = False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.3)
            res = s.connect_ex((target_host, port))
            is_open = (res == 0)
    except Exception:
        is_open = False

    return {
        "port": port,
        "open": is_open,
        "preview_url": f"/api/sandbox/proxy/{port}/" if is_open else None
    }

@router.api_route("/proxy/{port}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
@router.api_route("/proxy/{port}/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])
async def proxy_sandbox_port(port: int, path: str = "", request: Request = None):
    """
    Dynamically reverse-proxies HTTP requests from host/browser
    directly to the web application listening inside the sandbox container.
    """
    target_host = settings.SANDBOX_CONTAINER_NAME
    query = request.url.query if request else ""
    target_url = f"http://{target_host}:{port}/{path}"
    if query:
        target_url += f"?{query}"

    body = await request.body() if request else None

    # Forward headers excluding host
    headers = dict(request.headers) if request else {}
    headers.pop("host", None)

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            upstream_res = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=body,
                follow_redirects=True
            )

            # Build response
            excluded_headers = ["content-encoding", "content-length", "transfer-encoding", "connection"]
            resp_headers = {
                k: v for k, v in upstream_res.headers.items()
                if k.lower() not in excluded_headers
            }

            return Response(
                content=upstream_res.content,
                status_code=upstream_res.status_code,
                headers=resp_headers,
                media_type=upstream_res.headers.get("content-type")
            )
    except httpx.ConnectError:
        raise HTTPException(
            status_code=502,
            detail=f"Service on port {port} inside sandbox is not accepting connections yet."
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error connecting to sandbox port {port}: {str(e)}"
        )
