import io
import os
import zipfile
from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from typing import Dict, Any
from app.models.schemas import (
    SessionInitRequest,
    SessionState,
    ApprovalActionRequest,
    InterviewAnswer,
    UserMessageRequest,
    ChatMessage,
    StageEnum,
    SetupStatusResponse
)
from app.state_machine import session_manager
from app.guardrails import validate_git_url

router = APIRouter(prefix="/api/session", tags=["Session"])

@router.post("/validate-url")
def validate_url(req: Dict[str, str]):
    """Pre-checks a git repository URL before submitting."""
    url = req.get("repo_url", "")
    valid, err, repo_name = validate_git_url(url)
    return {
        "valid": valid,
        "error": err,
        "repo_name": repo_name
    }

@router.post("/init", response_model=SessionState)
async def init_session(req: SessionInitRequest):
    try:
        session = session_manager.get_or_create_session(
            session_id=req.session_id,
            repo_url=req.repo_url,
            repo_path=req.local_path
        )
        return session
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except (RuntimeError, TimeoutError) as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize workspace: {str(e)}")

@router.get("/{session_id}/setup-status", response_model=SetupStatusResponse)
async def get_setup_status(session_id: str):
    status = session_manager.setup_statuses.get(session_id)
    if not status:
        # If already ready or session exists
        session = session_manager.sessions.get(session_id)
        if session:
            return SetupStatusResponse(
                session_id=session_id,
                steps=[],
                completed=True,
                detected_stack=session.detected_stack,
                quarantined_secrets=session.quarantined_secrets
            )
        raise HTTPException(status_code=404, detail="Setup status not found")
    return status

@router.get("/{session_id}", response_model=SessionState)
async def get_session(session_id: str):
    session = session_manager.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@router.post("/{session_id}/message", response_model=SessionState)
async def send_user_message(session_id: str, req: UserMessageRequest):
    session = session_manager.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    msg_clean = req.message.strip().lower()
    # Context-aware developer greeting handling (prevents generic guardrail deflection on hi/hello)
    if msg_clean in ["hi", "hello", "hey", "yo", "help"]:
        repo_name = os.path.basename(session.repo_path)
        greeting_text = (
            f"Hello! I am ready to help you containerize **{repo_name}** ({session.detected_stack}). "
            f"To get started, please select whether your application requires a companion database (PostgreSQL, MongoDB, Redis) or if it is completely stateless using the choice card below."
        )
        session.messages.append(ChatMessage(role="user", content=req.message))
        session.messages.append(ChatMessage(role="assistant", content=greeting_text))
        return session

    # Message recorded; prompt injection and topic boundaries handled natively by Bedrock Guardrail
    session.messages.append(ChatMessage(role="user", content=req.message))
    if session.stage == StageEnum.INTERVIEW:
        session.stage = StageEnum.EXECUTE
    updated = await session_manager.step(session_id)
    return updated

@router.post("/{session_id}/step", response_model=SessionState)
async def trigger_step(session_id: str):
    session = session_manager.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    updated = await session_manager.step(session_id)
    return updated

@router.post("/{session_id}/approve", response_model=SessionState)
async def approve_tool(session_id: str, req: ApprovalActionRequest):
    updated = await session_manager.handle_approval(
        session_id=session_id,
        tool_call_id=req.tool_call_id,
        approved=req.approved,
        modified_arguments=req.modified_arguments,
        feedback=req.feedback
    )
    return updated

@router.post("/{session_id}/answer", response_model=SessionState)
async def submit_answer(session_id: str, ans: InterviewAnswer):
    session = session_manager.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    session.answers[ans.question_id] = ans.answer
    session.messages.append(ChatMessage(role="user", content=ans.answer))
    if session.current_tool_call and session.current_tool_call.tool_name == "ask_user":
        session.current_tool_call = None
    session.stage = StageEnum.EXECUTE
    return await session_manager.step(session_id)

@router.get("/{session_id}/export")
async def export_artifacts(session_id: str) -> Dict[str, Any]:
    session = session_manager.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    from app.playbook import generate_playbook
    playbook_md = await generate_playbook(session)
    session.exported_artifacts["PLAYBOOK.md"] = playbook_md

    return {
        "session_id": session_id,
        "stage": session.stage,
        "artifacts": session.exported_artifacts,
        "facts_ledger": session.facts_ledger
    }

@router.get("/{session_id}/download")
async def download_bundle(session_id: str):
    """
    Packages generated containerization artifacts and deployment runbook
    into a zip archive so users keep their work before the workspace is deleted.
    """
    session = session_manager.sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Add generated artifacts
        for filename, content in session.exported_artifacts.items():
            clean_name = filename.replace("\\", "/").lstrip("/")
            zf.writestr(clean_name, content)

        # Also pull Dockerfile / docker-compose from workspace if present on disk
        for fallback_f in ["Dockerfile", "docker-compose.yml", ".dockerignore", ".env.example"]:
            disk_p = os.path.join(session.repo_path, fallback_f)
            if os.path.exists(disk_p) and fallback_f not in session.exported_artifacts:
                try:
                    with open(disk_p, "r", encoding="utf-8") as f:
                        zf.writestr(fallback_f, f.read())
                except Exception:
                    pass

        # Generate comprehensive DEPLOY_RUNBOOK.md
        runbook_content = f"""# Deployment Runbook: {session.app_type or 'Application'}
Generated by LabOps Deploy Assistant for session `{session.session_id}`

## Summary
- **App Stack**: {session.detected_stack or 'Application'}
- **Service Port**: {session.app_port or 8000}
- **Quarantined Secrets**: {len(session.quarantined_secrets)} files protected during setup

## How to Run Locally

### 1. Configure Environment
Copy `.env.example` to `.env` and fill in your private variables:
```bash
cp .env.example .env
```

### 2. Build and Run with Docker Compose
```bash
docker compose up --build
```
Or with plain Docker:
```bash
docker build -t app:latest .
docker run -p {session.app_port or 8000}:{session.app_port or 8000} --env-file .env app:latest
```

### 3. Verify Health
```bash
curl -I http://localhost:{session.app_port or 8000}
```

## Cloud & Production Next Steps
- Push your verified image to AWS ECR / Docker Hub.
- Deploy to your LabOps cluster or Kubernetes namespace with ArgoCD.
- Manage production secrets securely via AWS Secrets Manager or HashiCorp Vault.
"""
        zf.writestr("DEPLOY_RUNBOOK.md", runbook_content)

    zip_buffer.seek(0)
    short_id = session_id[:8]
    filename = f"deploy-artifacts-{short_id}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )

@router.delete("/{session_id}")
async def delete_workspace(session_id: str):
    """
    Permanently deletes the workspace sandbox and container.
    Builds trust by confirming the deletion happened.
    """
    result = session_manager.teardown_session(session_id)
    return result
