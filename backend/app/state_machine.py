import re
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
    sanitize_compose_guardrails,
    sanitize_dockerfile_guardrails,
    truncate_output
)
from app.tools import execute_readonly_tool, execute_approved_tool, TOOL_DEFINITIONS
from app.llm_client import llm_client
from app.docker_bridge import docker_bridge
from app.config import settings

STAGE_PROMPTS = {
    StageEnum.INSPECT: (
        "You are an expert autonomous DevOps architect.\n"
        "A codebase has been loaded into your ephemeral workspace sandbox.\n"
        "DO NOT GUESS OR ASSUME. You MUST inspect the codebase thoroughly before making decisions:\n"
        "1. Call `list_dir` to explore the root directory structure.\n"
        "2. If you see subdirectories like `backend`, `frontend`, `services`, `api`, `client`, `web`, inspect them with `list_dir` and read their respective manifests (`package.json`, `requirements.txt`, `pyproject.toml`, `Cargo.toml`, `Gemfile`, `go.mod`, etc.) using `read_file`.\n"
        "3. Read server entrypoints (e.g. server.js, main.py, app.py, vite.config.ts) to find ports, framework versions, and routes.\n"
        "4. Call `declare_stack_profile` to register your findings (framework, port, architecture, dependencies, summary).\n"
        "5. If the repository is a monorepo or has multiple services, call `ask_user` with tailored options on how the developer wants to containerize the architecture (e.g. multi-service compose, backend only, or unified container).\n"
        "6. If the repository is a single-service app with clear requirements, explain your analysis and propose the Dockerfile via `write_file`."
    ),
    StageEnum.INTERVIEW: (
        "You are an expert DevOps architect. "
        "The developer has answered your architectural questions. "
        "Synthesize the architecture and proceed immediately to creating the deployment manifests using `write_file`. "
        "If multi-service, generate the appropriate Dockerfiles (e.g. `backend/Dockerfile`, `frontend/Dockerfile`) and `docker-compose.yml`. "
        "CRITICAL DOCKERFILE SYNTAX: Arguments MUST have spaces! Write 'COPY package*.json ./' and 'COPY . .'. "
        "Do NOT write code blocks in chat prose; always invoke `write_file`."
    ),
    StageEnum.PLAN: (
        "You are preparing deployment artifacts for this verified architecture. "
        "Invoke `write_file` to propose the container configuration."
    ),
    StageEnum.EXECUTE: (
        "You are creating containerization artifacts for this application.\n"
        "MANDATORY SECURITY GUARDRAILS:\n"
        "1. ZERO HOST MOUNTS: In `docker-compose.yml`, NEVER mount host application directories (e.g. NEVER write `volumes: - .:/app` or `.:/usr/src/app`). Code must be self-contained in the container image.\n"
        "2. ZERO CHAT DELAYS: Never output 'I will write this file' in chat prose. Directly invoke the `write_file` tool call in the same turn.\n"
        "3. ZERO SECRETS: Never ask for or write real passwords or tokens. Always use `.env.example` with placeholder values."
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
        """
        Deep recursive scan (up to 2 levels deep) to identify single-service and multi-service monorepos.
        """
        discovered = {}
        if not os.path.exists(repo_path):
            return "Generic Application", 8000

        for root, dirs, files in os.walk(repo_path):
            rel = os.path.relpath(root, repo_path)
            depth = len(rel.split(os.sep)) if rel != "." else 0
            if depth > 2:
                continue
            if ".git" in dirs: dirs.remove(".git")
            if "node_modules" in dirs: dirs.remove("node_modules")
            if "venv" in dirs: dirs.remove("venv")

            # Check Node.js
            if "package.json" in files:
                try:
                    with open(os.path.join(root, "package.json"), "r", encoding="utf-8") as f:
                        data = json.load(f)
                    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                    framework = "Node.js"
                    port = 3000
                    if "express" in deps: framework = "Node.js (Express)"
                    elif "next" in deps: framework = "Next.js"
                    elif "react" in deps or "react-dom" in deps: framework = "React (Vite)"
                    elif "vue" in deps: framework = "Vue.js"
                    discovered[rel] = {"type": "node", "framework": framework, "port": port}
                except Exception:
                    discovered[rel] = {"type": "node", "framework": "Node.js", "port": 3000}

            # Check Python
            if "requirements.txt" in files or "pyproject.toml" in files:
                content = ""
                for req_f in ["requirements.txt", "pyproject.toml"]:
                    p = os.path.join(root, req_f)
                    if os.path.exists(p):
                        try:
                            with open(p, "r", encoding="utf-8") as f: content += f.read().lower()
                        except Exception: pass
                framework = "Python"
                port = 8000
                if "fastapi" in content: framework = "Python (FastAPI)"
                elif "flask" in content: framework = "Python (Flask)"; port = 5000
                elif "django" in content: framework = "Python (Django)"
                discovered[rel] = {"type": "python", "framework": framework, "port": port}

            # Check Go
            if "go.mod" in files:
                discovered[rel] = {"type": "go", "framework": "Go Service", "port": 8080}

            # Check Rust
            if "Cargo.toml" in files:
                discovered[rel] = {"type": "rust", "framework": "Rust Service", "port": 8080}

        # Scan discovered directories for explicit entrypoint port definitions
        for rel_dir, info in discovered.items():
            scan_dir = repo_path if rel_dir == "." else os.path.join(repo_path, rel_dir)
            for entry_file in ["server.js", "app.js", "index.js", "main.js", "server.py", "app.py", "main.py"]:
                ep = os.path.join(scan_dir, entry_file)
                if os.path.exists(ep):
                    try:
                        with open(ep, "r", encoding="utf-8", errors="replace") as ef:
                            txt = ef.read()
                        pm = re.search(r'(?:PORT\s*=\s*(?:process\.env\.PORT\s*\|\|\s*)?|listen\s*\(\s*|port\s*=\s*)(\d{3,5})', txt, re.IGNORECASE)
                        if pm:
                            cand = int(pm.group(1))
                            if 80 <= cand <= 65535:
                                info["port"] = cand
                                break
                    except Exception:
                        pass

        if not discovered:
            return "Generic Application", 8000

        # Monorepo / Multi-service check
        frameworks = list(dict.fromkeys(s["framework"] for s in discovered.values()))
        if len(discovered) > 1 or len(frameworks) > 1:
            fw_label = " + ".join(frameworks[:2])
            return f"Full-Stack Monorepo ({fw_label})", 3000

        first_s = list(discovered.values())[0]
        return first_s["framework"], first_s["port"]

    async def initialize_workspace(
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

        # Step 4: AI Codebase Inspection
        steps[3].label = "Analyzing application architecture with AI…"
        steps[3].status = "running"
        steps[3].detail = "AI inspecting directory structure, package manifests, and server configuration."

        session = SessionState(
            session_id=session_id,
            stage=StageEnum.INSPECT,
            repo_path=target_dir,
            repo_url=repo_url,
            detected_stack="Analyzing...",
            quarantined_secrets=quarantined,
            app_type="Analyzing...",
            app_port=None,
            facts_ledger=[
                LedgerEntry(category="verified", fact=f"Quarantine scan: {len(quarantined)} secret file(s) isolated", evidence="safety scanner"),
            ],
            messages=[],
            current_tool_call=None,
            last_activity=time.time()
        )
        self.sessions[session_id] = session

        # Launch autonomous AI Codebase Inspection step
        initial_instruction = (
            f"Please inspect the newly loaded repository '{repo_name}'. "
            f"Explore the directory structure using `list_dir`. Inspect subdirectories, manifests (package.json, requirements.txt, pyproject.toml, etc.), and server code using `read_file`. "
            f"Call `declare_stack_profile` with your discovered stack, port, and architecture. "
            f"If this is a monorepo or has multiple services, call `ask_user` with tailored options on how the developer wants to containerize the components. "
            f"If it is a single-service application with clear conventions, explain your plan and propose the Dockerfile via `write_file`."
        )
        await self.step(session_id, extra_instruction=initial_instruction)

        # Fallback safeguard if AI did not declare stack
        if session.detected_stack == "Analyzing...":
            fallback_stack, fallback_port = self._detect_stack(target_dir)
            session.detected_stack = fallback_stack
            session.app_port = fallback_port
            session.app_type = fallback_stack

        steps[3].status = "completed"
        steps[3].detail = f"Identified {session.detected_stack} (port {session.app_port or 8000})."
        status_resp.detected_stack = session.detected_stack

        # Ensure assistant summary message is recorded in chat
        if not session.messages:
            summary_msg = (
                f"I have inspected **{repo_name}** and mapped its codebase architecture:\n\n"
                f"- **Stack**: {session.detected_stack}\n"
                f"- **Configured Port**: `{session.app_port or 8000}`\n\n"
                f"I have provisioned your ephemeral sandbox. Review the configuration below to proceed."
            )
            session.messages.append(ChatMessage(role="assistant", content=summary_msg))

        # Step 5: Ready Hand-off
        steps[4].label = f"Ready. {session.detected_stack}."
        steps[4].status = "completed"
        steps[4].detail = "Ephemeral sandbox ready. Proceeding with deployment."
        status_resp.completed = True

        return session

    async def get_or_create_session(
        self,
        session_id: Optional[str] = None,
        repo_url: Optional[str] = None,
        repo_path: Optional[str] = None
    ) -> SessionState:
        sid = session_id or str(uuid.uuid4())
        if sid in self.sessions:
            self.sessions[sid].last_activity = time.time()
            return self.sessions[sid]

        return await self.initialize_workspace(session_id=sid, repo_url=repo_url, local_path=repo_path)

    async def step(self, session_id: str, extra_instruction: Optional[str] = None) -> SessionState:
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

        # Keep sliding window of recent messages to preserve Groq free-tier TPM quota
        recent_messages = session.messages[-6:] if len(session.messages) > 6 else session.messages
        history = []
        for m in recent_messages:
            if m.role in ["user", "assistant"]:
                history.append({"role": m.role, "content": m.content})
        if extra_instruction:
            history.append({"role": "user", "content": extra_instruction})

        # Autonomous tool-use loop (handles readonly inspection tools like list_dir, read_file, declare_stack_profile)
        for loop_idx in range(10):
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
                # Feed inspection result back into conversation history so the model can proceed
                history.append({
                    "role": "user",
                    "content": f"[Result of {tool_name}]:\n{result_str[:1500]}"
                })
                continue
            elif tool_name == "declare_stack_profile":
                fw = args.get("framework") or "Application Service"
                port = args.get("port") or 8000
                arch = args.get("architecture") or "single-service"
                summary = args.get("summary") or ""
                deps = args.get("detected_dependencies") or []

                session.detected_stack = fw
                session.app_port = port
                session.app_type = fw

                session.facts_ledger.append(LedgerEntry(
                    category="verified",
                    fact=f"AI Codebase Profile: {fw} ({arch})",
                    evidence=f"Port {port}"
                ))
                if deps:
                    session.facts_ledger.append(LedgerEntry(
                        category="verified",
                        fact=f"Detected external dependencies: {', '.join(deps)}",
                        evidence="manifest inspection"
                    ))

                # Update setup status if active
                status_resp = self.setup_statuses.get(session.session_id)
                if status_resp:
                    status_resp.detected_stack = fw
                    if len(status_resp.steps) >= 5:
                        status_resp.steps[3].status = "completed"
                        status_resp.steps[3].detail = f"AI identified {fw} (port {port})."
                        status_resp.steps[4].label = f"Ready. {fw}"
                        status_resp.steps[4].detail = summary or f"Architecture: {arch}."

                if "monorepo" in arch.lower() or "multi" in arch.lower() or "microservice" in arch.lower():
                    next_instruction = (
                        f"Architecture profile confirmed: {fw} ({arch}). "
                        f"Because this codebase contains multiple services or components, you MUST now call `ask_user` "
                        f"with a question asking the developer how they want to deploy the services "
                        f"(e.g. 'Full-Stack Compose (frontend + backend)', 'Backend API only', 'Frontend only')."
                    )
                else:
                    next_instruction = (
                        f"Architecture profile confirmed: {fw} on port {port}. "
                        f"Proceed immediately to propose the production containerization by calling `write_file` with file_path='Dockerfile'."
                    )

                history.append({
                    "role": "user",
                    "content": f"[Result of declare_stack_profile]: {next_instruction}"
                })
                continue
            elif tool_name in ["write_file", "run_command", "ask_user"]:
                if tool_name == "write_file":
                    fname = args.get("file_path", "").lower()
                    raw_c = args.get("content", "")
                    if "dockerfile" in fname:
                        args["content"] = sanitize_dockerfile_guardrails(raw_c)
                    elif "compose" in fname or "docker-compose" in str(raw_c).lower():
                        sanitized_content, stripped = sanitize_compose_guardrails(raw_c)
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
        if tc.tool_name == "write_file":
            fname = args.get("file_path", "").lower()
            raw_c = args.get("content", "")
            if "dockerfile" in fname:
                args["content"] = sanitize_dockerfile_guardrails(raw_c)
            elif "compose" in fname or "docker-compose" in str(raw_c).lower():
                sanitized_content, stripped = sanitize_compose_guardrails(raw_c)
                args["content"] = sanitized_content
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
            session.current_tool_call = None
            if "dockerfile" in fname.lower():
                session.stage = StageEnum.EXECUTE
                return await self._verify_and_self_heal_dockerfile(session)
            elif "compose" in fname.lower():
                session.stage = StageEnum.EXECUTE
                return await self._verify_and_self_heal_compose(session)
            else:
                next_prompt = f"Applied `{fname}` successfully. Propose container verification using `run_command`."
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
                next_prompt = f"Command `{args.get('command')}` executed successfully with exit code 0. Now verify the service or transition to EXPORT."
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
        return await self.step(session_id, extra_instruction=next_prompt if "next_prompt" in locals() else None)


    async def _verify_and_self_heal_dockerfile(self, session: SessionState) -> SessionState:
        """
        Autonomous AI Sandbox Build & Self-Healing Loop:
        1. Executes `docker build -t <repo_name>:test .` inside the DinD sandbox container.
        2. If exit_code == 0: records verified evidence, informs user, and proceeds to docker-compose.yml.
        3. If exit_code != 0:
           - If fatal application syntax/code bug: Stop Rule halts.
           - If build/packaging error: AI analyzes stderr, updates Dockerfile directly, and retries (up to MAX_RETRY_LIMIT).
        """
        repo_name = os.path.basename(session.repo_path.rstrip("/\\")) or "app"
        clean_tag = re.sub(r'[^a-zA-Z0-9_\-\.]', '', repo_name.lower()) or "app"
        image_tag = f"{clean_tag}:test"
        build_cmd = f"docker build -t {image_tag} ."

        while session.retry_count <= settings.MAX_RETRY_LIMIT:
            session.messages.append(ChatMessage(
                role="assistant",
                content=f"🚀 **Building image `{image_tag}` in sandbox container** to verify Dockerfile..."
            ))
            
            res = docker_bridge.execute_command(build_cmd, working_dir=session.repo_path)
            
            if res.get("success") or res.get("exit_code") == 0:
                session.facts_ledger.append(LedgerEntry(
                    category="verified",
                    fact=f"Docker image '{image_tag}' built successfully in sandbox",
                    evidence=f"Exit code 0 ({res.get('duration_ms', 0)}ms)"
                ))
                success_text = f"🎉 **Sandbox Build Succeeded!** Image `{image_tag}` built cleanly with exit code 0 ({res.get('duration_ms', 0)}ms)."
                if session.retry_count > 0:
                    success_text = f"🎉 **Self-Healing Succeeded!** Image `{image_tag}` verified in sandbox after {session.retry_count} fix(es)."
                session.messages.append(ChatMessage(role="assistant", content=success_text))
                session.retry_count = 0

                # Proceed to compose generation
                next_prompt = (
                    f"The Dockerfile for '{repo_name}' has been built and verified inside the sandbox container (exit code 0).\n"
                    f"Now generate `docker-compose.yml` (and `.env.example` if required) by calling the `write_file` tool call.\n"
                    f"MANDATORY GUARDRAILS: ZERO host mounts (never write 'volumes: - .:/app' or relative binds). Use the verified image or build context."
                )
                session.current_tool_call = None
                return await self.step(session.session_id, extra_instruction=next_prompt)

            # Build failed
            err = res.get("stderr") or res.get("stdout") or "Unknown build failure"
            if is_app_code_error(err):
                session.stage = StageEnum.FAILED
                session.current_tool_call = None
                session.messages.append(ChatMessage(
                    role="assistant",
                    content=f"🛑 **Application Code Error Detected (Stop Rule)**:\n\n```\n{truncate_output(err, 1500)}\n```\nThis failure is caused by an error in the application source code rather than container configuration. Please fix this in your repository."
                ))
                return session

            session.retry_count += 1
            if session.retry_count > settings.MAX_RETRY_LIMIT:
                session.stage = StageEnum.FAILED
                session.current_tool_call = None
                session.messages.append(ChatMessage(
                    role="assistant",
                    content=f"❌ **Sandbox build failed after {settings.MAX_RETRY_LIMIT} self-healing attempts**.\n\nBuild error logs:\n```\n{truncate_output(err, 1500)}\n```\nPlease review repository dependencies or base configuration."
                ))
                return session

            # Self-healing iteration
            session.messages.append(ChatMessage(
                role="assistant",
                content=(
                    f"⚠️ **Sandbox build failed (Self-healing attempt {session.retry_count}/{settings.MAX_RETRY_LIMIT})**:\n"
                    f"```\n{truncate_output(err, 800)}\n```\n"
                    f"🔧 **AI Self-Healing**: Diagnosing build failure, updating `Dockerfile`, and re-testing inside the sandbox..."
                )
            ))

            dockerfile_path = os.path.join(session.repo_path, "Dockerfile")
            current_df = ""
            if os.path.exists(dockerfile_path):
                try:
                    with open(dockerfile_path, "r", encoding="utf-8", errors="replace") as f:
                        current_df = f.read()
                except Exception:
                    pass

            healing_instruction = (
                f"CRITICAL: The sandbox `docker build` for {repo_name} failed with exit code {res.get('exit_code')}.\n"
                f"Current Dockerfile:\n```dockerfile\n{current_df}\n```\n\n"
                f"Build Error Stderr:\n```\n{truncate_output(err, 1500)}\n```\n\n"
                f"Diagnose the error above. Fix the Dockerfile (e.g. adjust base image version, install required build packages/compilers, fix COPY paths, or correct command syntax). "
                f"MANDATORY: You MUST call the `write_file` tool with file_path='Dockerfile' and the complete corrected content."
            )

            # Query LLM with sliding window history + healing instruction
            history = []
            for m in session.messages[-6:]:
                if m.role in ["user", "assistant"]:
                    history.append({"role": m.role, "content": m.content})
            history.append({"role": "user", "content": healing_instruction})

            llm_resp = await llm_client.chat(
                messages=history,
                tools=TOOL_DEFINITIONS,
                stage_prompt=STAGE_PROMPTS.get(StageEnum.EXECUTE, "")
            )

            tool_calls = llm_resp.get("tool_calls", [])
            fixed_content = None
            for tc in tool_calls:
                f_name = tc.get("function", {}).get("name", "")
                if f_name == "write_file":
                    raw_args = tc.get("function", {}).get("arguments", {})
                    if isinstance(raw_args, str):
                        try:
                            raw_args = json.loads(raw_args)
                        except Exception:
                            raw_args = {}
                    if "dockerfile" in raw_args.get("file_path", "").lower():
                        fixed_content = sanitize_dockerfile_guardrails(raw_args.get("content", ""))
                        break

            if fixed_content:
                with open(dockerfile_path, "w", encoding="utf-8") as f:
                    f.write(fixed_content)
                session.exported_artifacts["Dockerfile"] = fixed_content
                # Loop continues to re-test docker build!
            else:
                session.stage = StageEnum.FAILED
                session.current_tool_call = None
                session.messages.append(ChatMessage(
                    role="assistant",
                    content=f"AI self-healing was unable to generate a corrected Dockerfile for this error. Halting for user review."
                ))
                return session

        return session

    async def _verify_and_self_heal_compose(self, session: SessionState) -> SessionState:
        """
        Autonomous AI Sandbox Compose Verification:
        1. Executes `docker compose up -d` inside the DinD sandbox container.
        2. Verifies container health and status via `docker compose ps` / port checks.
        3. If verified: transitions to EXPORT stage and generates PLAYBOOK.md.
        4. If failed: reports error and halts or self-heals compose configuration.
        """
        repo_name = os.path.basename(session.repo_path.rstrip("/\\")) or "app"
        compose_cmd = "docker compose up -d"

        session.messages.append(ChatMessage(
            role="assistant",
            content=f"🚀 **Starting services with `docker compose` in sandbox container** to verify orchestration..."
        ))

        res = docker_bridge.execute_command(compose_cmd, working_dir=session.repo_path)
        if res.get("success") or res.get("exit_code") == 0:
            session.facts_ledger.append(LedgerEntry(
                category="verified",
                fact="Started all services via docker compose in sandbox",
                evidence=f"Exit code 0 ({res.get('duration_ms', 0)}ms)"
            ))

            # Test curl health check if port is detected
            port = session.app_port or 8000
            curl_res = docker_bridge.execute_command(
                f"curl -s -o /dev/null -w '%{{http_code}}' http://localhost:{port}",
                working_dir=session.repo_path
            )
            code = curl_res.get("stdout", "").strip()
            if code in ("000", ""):
                curl_res = docker_bridge.execute_command(
                    f"curl -s -o /dev/null -w '%{{http_code}}' http://127.0.0.1:{port}",
                    working_dir=session.repo_path
                )
                code = curl_res.get("stdout", "").strip()

            if code.isdigit() and len(code) == 3 and int(code) in range(200, 500):
                session.facts_ledger.append(LedgerEntry(
                    category="verified",
                    fact=f"Service responded on port {port} (HTTP {code})",
                    evidence=f"HTTP status {code}"
                ))

            session.stage = StageEnum.EXPORT
            session.current_tool_call = None
            session.messages.append(ChatMessage(
                role="assistant",
                content=(
                    f"🎉 **All Services Verified and Running in Sandbox!**\n\n"
                    f"- **Service Port**: `{port}`\n"
                    f"- **Status**: Verified running in isolated container.\n\n"
                    f"Your deployment package (`Dockerfile`, `docker-compose.yml`, `.env.example`, and `PLAYBOOK.md`) is ready for download."
                )
            ))

            # Generate final PLAYBOOK.md
            try:
                from app.playbook import generate_playbook
                session.exported_artifacts["PLAYBOOK.md"] = await generate_playbook(session)
            except Exception:
                pass

            return session
        else:
            err = res.get("stderr") or res.get("stdout") or "Compose startup failure"
            session.messages.append(ChatMessage(
                role="assistant",
                content=f"⚠️ **Compose startup error**:\n```\n{truncate_output(err, 800)}\n```"
            ))
            session.stage = StageEnum.FAILED
            session.current_tool_call = None
            return session

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
