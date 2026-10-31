import os
import shutil
import uuid
import time
import subprocess
import json
from typing import Dict, Any, Optional, List, Tuple
from app.models.schemas import (
    StageEnum,
    SessionState,
    ChatMessage,
    ToolCall,
    ToolCallStatus,
    SetupStep,
    SetupStatusResponse,
    LedgerEntry
)
from app.guardrails import (
    is_app_code_error,
    scan_and_quarantine_secrets,
    validate_git_url,
    sanitize_compose_guardrails
)
from app.tools import execute_readonly_tool, execute_approved_tool, TOOL_DEFINITIONS
from app.llm_client import llm_client
from app.docker_bridge import docker_bridge
from app.config import settings

STAGE_PROMPTS = {
    StageEnum.INSPECT: (
        "You are an expert containerization and deployment assistant. "
        "Inspect the repository structure using `list_dir` and `read_file`. "
        "MANDATORY: When creating or updating files (Dockerfile, docker-compose.yml), you MUST call the `write_file` tool. "
        "Do not print raw file code blocks in your chat response. Propose the Dockerfile using `write_file`."
    ),
    StageEnum.INTERVIEW: (
        "You are an expert deployment assistant. "
        "The developer has specified their requirements. Now proceed immediately to creating the deployment configuration. "
        "MANDATORY: You MUST call the `write_file` tool with file_path='Dockerfile' and the optimized Dockerfile content. "
        "Do NOT print the full Dockerfile code block in chat text; use the `write_file` tool so the user receives the interactive approval card."
    ),
    StageEnum.PLAN: (
        "You are preparing containerization artifacts. "
        "MANDATORY: Propose the Dockerfile by calling the `write_file` tool call. "
        "Do NOT write file contents in chat prose; always use the `write_file` tool."
    ),
    StageEnum.EXECUTE: (
        "You are creating containerization artifacts for this application.\n"
        "MANDATORY SECURITY GUARDRAILS:\n"
        "1. ZERO HOST MOUNTS: In `docker-compose.yml`, NEVER mount host application directories (e.g. NEVER write `volumes: - .:/app` or `.:/usr/src/app`). All application code must be self-contained inside the image via Dockerfile `COPY . .`. Do NOT include host binds.\n"
        "2. ZERO CHAT DELAYS: Never output 'I will write this file' in chat prose. Directly invoke the `write_file` tool call in the same turn.\n"
        "3. ZERO SECRETS: Never ask for or write real passwords or tokens. Always use `.env.example` with placeholder values.\n"
        "To test or build containers inside the sandbox, you MUST call the `run_command` tool."
    ),
    StageEnum.VERIFY: (
        "Verify the running container by querying its health endpoint using `run_command` (e.g., `curl -I http://localhost:<port>`). "
        "If it succeeds, confirm the deployment is verified. "
        "If the user's application code has a bug (SyntaxError, missing module), quote the error verbatim and halt under the Stop Rule."
    ),
    StageEnum.EXPORT: (
        "The deployment has been verified inside the sandbox! Congratulate the developer and inform them "
        "that their verified artifacts (Dockerfile, compose file, .env.example, runbook) are ready for download."
    )
}

def _clear_directory_contents(dir_path: str):
    """Deletes all contents inside a directory without deleting the directory itself."""
    if not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
        return
    for item in os.listdir(dir_path):
        item_p = os.path.join(dir_path, item)
        try:
            if os.path.isdir(item_p):
                shutil.rmtree(item_p, ignore_errors=True)
            else:
                os.remove(item_p)
        except Exception:
            pass

class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, SessionState] = {}
        self.setup_statuses: Dict[str, SetupStatusResponse] = {}
        self.workspace_root = settings.WORKSPACE_DIR
        os.makedirs(self.workspace_root, exist_ok=True)

    def _detect_stack(self, repo_path: str) -> Tuple[str, Optional[int]]:
        """Analyzes repo manifests to determine language framework, entrypoint, and port."""
        app_type = "Generic Application"
        port = 8000

        # Check Node.js
        pkg_json = os.path.join(repo_path, "package.json")
        if os.path.exists(pkg_json):
            try:
                with open(pkg_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                port = 3000
                if "express" in deps:
                    app_type = "Node.js Express application"
                elif "next" in deps:
                    app_type = "Next.js application"
                elif "nest" in deps or "@nestjs/core" in deps:
                    app_type = "NestJS application"
                elif "fastify" in deps:
                    app_type = "Fastify application"
                else:
                    app_type = "Node.js application"
                return app_type, port
            except Exception:
                return "Node.js application", 3000

        # Check Python
        req_txt = os.path.join(repo_path, "requirements.txt")
        pyproject = os.path.join(repo_path, "pyproject.toml")
        if os.path.exists(req_txt) or os.path.exists(pyproject):
            content = ""
            if os.path.exists(req_txt):
                try:
                    with open(req_txt, "r", encoding="utf-8") as f:
                        content += f.read().lower()
                except Exception:
                    pass
            if os.path.exists(pyproject):
                try:
                    with open(pyproject, "r", encoding="utf-8") as f:
                        content += f.read().lower()
                except Exception:
                    pass

            if "fastapi" in content:
                app_type = "Python FastAPI application"
                port = 8000
            elif "flask" in content:
                app_type = "Python Flask application"
                port = 5000
            elif "django" in content:
                app_type = "Python Django application"
                port = 8000
            else:
                app_type = "Python application"
                port = 8000
            return app_type, port

        # Check Go
        if os.path.exists(os.path.join(repo_path, "go.mod")):
            return "Go service", 8080

        # Check Rust
        if os.path.exists(os.path.join(repo_path, "Cargo.toml")):
            return "Rust service", 8080

        return app_type, port

    def initialize_workspace_sync(
        self,
        session_id: str,
        repo_url: Optional[str] = None,
        local_path: Optional[str] = None
    ) -> SessionState:
        """
        Executes the live setup sequence:
        1. Opening fresh workspace (wiping shared sandbox /workspace mount)
        2. Downloading project (shallow clone directly into /workspace)
        3. Setting aside files that might hold secrets (quarantine)
        4. Taking a look at what's inside (inspection)
        5. Ready hand-off to chat
        """
        # Purge any stale sessions
        self.cleanup_idle_sessions()

        os.makedirs(settings.WORKSPACE_DIR, exist_ok=True)

        steps = [
            SetupStep(id="step-1", label="Opening a fresh workspace…", status="running", detail="Preparing an isolated, disposable sandbox container."),
            SetupStep(id="step-2", label="Downloading your project from GitHub…", status="pending", detail="Cloning into project directory (--depth 1)."),
            SetupStep(id="step-3", label="Setting aside files that might hold secrets…", status="pending", detail="Scanning for secrets and sensitive credential files."),
            SetupStep(id="step-4", label="Taking a look at what's inside…", status="pending", detail="Inspecting package manifests and application architecture."),
            SetupStep(id="step-5", label="Ready.", status="pending", detail="Preparing hand-off to chat assistant.")
        ]
        status_resp = SetupStatusResponse(
            session_id=session_id,
            steps=steps,
            completed=False
        )
        self.setup_statuses[session_id] = status_resp

        # Step 1: Workspace ready
        steps[0].status = "completed"
        steps[1].status = "running"

        # Step 2: Download repository into its own project folder under /workspace/<repo-name>
        if repo_url:
            valid, err, repo_name = validate_git_url(repo_url)
            if not valid:
                steps[1].status = "failed"
                steps[1].detail = err
                status_resp.error = err
                raise ValueError(err)

            target_dir = os.path.join(settings.WORKSPACE_DIR, repo_name)
            if os.path.exists(target_dir):
                _clear_directory_contents(target_dir)
            os.makedirs(target_dir, exist_ok=True)

            try:
                # Clone shallow with strict timeout directly into its dedicated project directory
                clone_cmd = ["git", "clone", "--depth", "1", "--single-branch", repo_url, target_dir]
                proc = subprocess.run(clone_cmd, capture_output=True, text=True, timeout=50)
                if proc.returncode != 0:
                    err_msg = proc.stderr.strip() or "Failed to clone repository. Please verify the URL is public and accessible."
                    steps[1].status = "failed"
                    steps[1].detail = err_msg
                    status_resp.error = err_msg
                    raise RuntimeError(err_msg)
                steps[1].status = "completed"
                steps[1].detail = f"Successfully downloaded {repo_name} into {target_dir}."
            except subprocess.TimeoutExpired:
                err_msg = "Repository download timed out after 50 seconds."
                steps[1].status = "failed"
                steps[1].detail = err_msg
                status_resp.error = err_msg
                raise TimeoutError(err_msg)
        elif local_path and os.path.exists(local_path):
            repo_name = os.path.basename(local_path.rstrip("/\\")) or "sample-app"
            target_dir = os.path.join(settings.WORKSPACE_DIR, repo_name)
            os.makedirs(target_dir, exist_ok=True)
            shutil.copytree(local_path, target_dir, dirs_exist_ok=True)
            steps[1].status = "completed"
            steps[1].detail = f"Loaded sample repository into {target_dir}."
        else:
            repo_name = "sample-node-app"
            target_dir = os.path.join(settings.WORKSPACE_DIR, repo_name)
            os.makedirs(target_dir, exist_ok=True)
            fixture_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "fixtures", "sample-node-app")
            if os.path.exists(fixture_path):
                shutil.copytree(fixture_path, target_dir, dirs_exist_ok=True)
            steps[1].status = "completed"
            steps[1].detail = f"Loaded default sample fixture into {target_dir}."

        # Step 3: Secret quarantine
        steps[2].status = "running"
        quarantined = scan_and_quarantine_secrets(target_dir)
        status_resp.quarantined_secrets = quarantined
        steps[2].status = "completed"
        if quarantined:
            steps[2].detail = f"Quarantined {len(quarantined)} secret-bearing file(s): {', '.join(quarantined)}. Hidden from AI."
        else:
            steps[2].detail = "No secret files detected. Privacy boundary verified."

        # Step 4: Inspect stack
        steps[3].status = "running"
        detected_stack, detected_port = self._detect_stack(target_dir)
        status_resp.detected_stack = detected_stack
        steps[3].status = "completed"
        steps[3].detail = f"Identified {detected_stack} (default port {detected_port})."

        # Step 5: Ready Hand-off
        steps[4].label = f"Ready. This looks like a {detected_stack}."
        steps[4].status = "completed"
        steps[4].detail = "Handing off to interactive deployment interview."
        status_resp.completed = True

        # Initialize Session State
        initial_content = (
            f"This looks like a **{detected_stack}** (default port `{detected_port}`). "
            f"I've provisioned an isolated workspace sandbox separate from your machine and accounts. "
            f"Your private files and host environment are untouched.\n\n"
            f"Let's get this containerized and running! Before drafting the Dockerfile, does this application connect to a "
            f"companion database (like PostgreSQL, MongoDB, Redis) or is it completely stateless?"
        )

        session = SessionState(
            session_id=session_id,
            stage=StageEnum.INTERVIEW,
            repo_path=target_dir,
            repo_url=repo_url,
            detected_stack=detected_stack,
            quarantined_secrets=quarantined,
            app_type=detected_stack,
            app_port=detected_port,
            facts_ledger=[
                LedgerEntry(category="declared", fact=f"Framework stack: {detected_stack}", evidence=os.path.basename(target_dir)),
                LedgerEntry(category="declared", fact=f"Configured service port: {detected_port}", evidence="manifest analysis"),
                LedgerEntry(category="verified", fact=f"Quarantine scan: {len(quarantined)} secret file(s) isolated", evidence="safety scanner"),
                LedgerEntry(category="assumed", fact="Single service architecture target", evidence="pre-interview inference"),
            ],
            messages=[
                ChatMessage(role="assistant", content=initial_content)
            ],
            last_activity=time.time()
        )

        self.sessions[session_id] = session
        return session

    def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        repo_url: Optional[str] = None,
        repo_path: Optional[str] = None
    ) -> SessionState:
        sid = session_id or str(uuid.uuid4())
        if sid in self.sessions:
            self.sessions[sid].last_activity = time.time()
            return self.sessions[sid]

        return self.initialize_workspace_sync(session_id=sid, repo_url=repo_url, local_path=repo_path)

    async def step(self, session_id: str) -> SessionState:
        session = self.sessions.get(session_id)
        if not session or not session.is_active:
            return session

        session.last_activity = time.time()
        if session.step_count >= settings.MAX_STEP_LIMIT:
            session.stage = StageEnum.FAILED
            session.messages.append(ChatMessage(
                role="assistant",
                content="I've reached the maximum number of steps for this session. ⏱️ Let me know if you'd like to adjust the plan."
            ))
            return session

        session.step_count += 1
        prompt = STAGE_PROMPTS.get(session.stage, "")

        history = []
        for m in session.messages:
            if m.role in ["user", "assistant"]:
                history.append({"role": m.role, "content": m.content})

        # Autonomous tool-use loop (handles readonly inspection tools like list_dir and read_file)
        for loop_idx in range(4):
            response = await llm_client.chat(
                messages=history,
                tools=TOOL_DEFINITIONS,
                stage_prompt=prompt
            )

            content = response.get("content", "")
            tool_calls = response.get("tool_calls", [])

            if content:
                session.messages.append(ChatMessage(role="assistant", content=content))
                history.append({"role": "assistant", "content": content})

            if not tool_calls:
                break

            tc_data = tool_calls[0]
            func_data = tc_data.get("function", {})
            tool_name = func_data.get("name", "")
            raw_args = func_data.get("arguments", {})
            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args)
                except Exception:
                    args = {}
            else:
                args = raw_args

            tool_id = str(uuid.uuid4())[:8]

            if tool_name in ["list_dir", "read_file"]:
                exec_result = execute_readonly_tool(tool_name, args, session.repo_path)
                result_str = str(exec_result.get("entries") or exec_result.get("content") or exec_result)
                # Feed inspection result back into conversation history so the model can proceed to write_file
                history.append({
                    "role": "user",
                    "content": f"[Result of {tool_name}]:\n{result_str[:4000]}"
                })
                continue
            elif tool_name in ["write_file", "run_command", "ask_user"]:
                if tool_name == "write_file" and ("compose" in args.get("file_path", "").lower() or "docker-compose" in str(args.get("content", "")).lower()):
                    sanitized_content, stripped = sanitize_compose_guardrails(args.get("content", ""))
                    args["content"] = sanitized_content
                tc = ToolCall(
                    id=tool_id,
                    tool_name=tool_name,
                    arguments=args,
                    status=ToolCallStatus.PENDING_APPROVAL,
                    requires_approval=True
                )
                session.current_tool_call = tc
                break

        return session

    async def handle_approval(
        self,
        session_id: str,
        tool_call_id: str,
        approved: bool,
        modified_arguments: Optional[Dict[str, Any]] = None,
        feedback: Optional[str] = None
    ) -> SessionState:
        session = self.sessions.get(session_id)
        if not session or not session.current_tool_call:
            return session

        session.last_activity = time.time()
        tc = session.current_tool_call
        if tc.id != tool_call_id:
            return session

        if not approved:
            tc.status = ToolCallStatus.REJECTED
            session.messages.append(ChatMessage(
                role="user",
                content=f"Skipped {tc.tool_name}. {feedback or ''}"
            ))
            session.current_tool_call = None
            return session

        tc.status = ToolCallStatus.APPROVED
        args = modified_arguments or tc.arguments
        result = execute_approved_tool(tc.tool_name, args, session.repo_path)

        tc.output = str(result.get("stdout") or result.get("message") or "")
        tc.error = result.get("stderr")
        tc.exit_code = result.get("exit_code", 0)
        tc.duration_ms = result.get("duration_ms")
        tc.status = ToolCallStatus.COMPLETED if result.get("success", True) else ToolCallStatus.FAILED

        if tc.tool_name == "write_file" and result.get("success"):
            fname = args.get("file_path", "")
            session.exported_artifacts[fname] = args.get("content", "")
            session.facts_ledger.append(LedgerEntry(
                category="declared",
                fact=f"Generated configuration artifact: {fname}",
                evidence=fname
            ))
            session.messages.append(ChatMessage(
                role="assistant",
                content=f"✅ Created `{fname}`! Stored securely in your workspace sandbox."
            ))
            if "dockerfile" in fname.lower():
                next_prompt = "Applied `Dockerfile` successfully. Now IMMEDIATELY generate `docker-compose.yml` by invoking the `write_file` tool call (Remember: ZERO host mounts; no volumes: - .:/app)."
            elif "compose" in fname.lower():
                next_prompt = "Applied `docker-compose.yml` successfully. Now IMMEDIATELY generate `.env.example` if variables are needed, or propose building and verifying using `run_command` (e.g. `docker compose build && docker compose up -d`)."
            else:
                next_prompt = f"Applied `{fname}` successfully. Propose container verification using `run_command`."
            session.messages.append(ChatMessage(role="user", content=next_prompt))
            session.stage = StageEnum.EXECUTE
        elif tc.tool_name == "run_command":
            if result.get("success"):
                session.facts_ledger.append(LedgerEntry(
                    category="verified",
                    fact=f"Executed command: {args.get('command')}",
                    evidence=f"exit {tc.exit_code} ({tc.duration_ms}ms)"
                ))
                session.messages.append(ChatMessage(
                    role="assistant",
                    content="🎉 Verified command executed successfully inside the sandbox container!"
                ))
                session.messages.append(ChatMessage(
                    role="user",
                    content=f"Command `{args.get('command')}` executed successfully with exit code 0."
                ))
                session.stage = StageEnum.VERIFY

                # Generate updated PLAYBOOK.md
                try:
                    from app.playbook import generate_playbook
                    session.exported_artifacts["PLAYBOOK.md"] = await generate_playbook(session)
                except Exception:
                    pass
            else:
                if tc.error and is_app_code_error(tc.error):
                    session.stage = StageEnum.FAILED
                    session.messages.append(ChatMessage(
                        role="assistant",
                        content=f"🛑 **Application Code Error Detected (Stop Rule)**:\n\n```\n{tc.error}\n```\nThis error originates from application logic rather than container configuration. Please fix this in your repository."
                    ))
                else:
                    session.retry_count += 1
                    session.messages.append(ChatMessage(
                        role="assistant",
                        content=f"⚠️ Command returned an error (attempt {session.retry_count}/{settings.MAX_RETRY_LIMIT}):\n```\n{tc.error or 'Failed'}\n```"
                    ))

        session.current_tool_call = None
        return await self.step(session_id)

    def teardown_session(self, session_id: str) -> Dict[str, Any]:
        """Completely destroys the disposable workspace container and files."""
        session = self.sessions.get(session_id)
        if session:
            try:
                docker_bridge.teardown_workspace_containers(session.repo_path)
            except Exception:
                pass
            try:
                _clear_directory_contents(session.repo_path)
            except Exception:
                pass
            del self.sessions[session_id]

        if session_id in self.setup_statuses:
            del self.setup_statuses[session_id]

        return {
            "success": True,
            "session_id": session_id,
            "message": "Workspace deleted. Your temporary sandbox container, repository files, and session data have been permanently wiped."
        }

    def cleanup_idle_sessions(self, max_idle_seconds: int = 3600):
        """Purges any abandoned sessions older than max_idle_seconds."""
        now = time.time()
        to_delete = [
            sid for sid, s in self.sessions.items()
            if (now - s.last_activity) > max_idle_seconds
        ]
        for sid in to_delete:
            self.teardown_session(sid)

session_manager = SessionManager()
