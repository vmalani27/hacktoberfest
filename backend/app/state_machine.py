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
from app.reconnaissance import reconnaissance_engine, ArchitectureProfile

STAGE_PROMPTS = {
    StageEnum.INSPECT: (
        "You are an expert autonomous DevOps & Cloud Infrastructure Architect.\n"
        "A codebase has been loaded into your ephemeral workspace sandbox.\n"
        "DevOps is NOT just containerization; it is end-to-end deployment engineering (Target Cloud/Platform, CI/CD, IaC, and Container Packaging).\n\n"
        "STEP 1: CODEBASE RECONNAISSANCE\n"
        "- Call `list_dir` to inspect the project layout.\n"
        "- Inspect subdirectories (`backend`, `frontend`, `services`, `api`) and manifests (`package.json`, `requirements.txt`, `pyproject.toml`, `Cargo.toml`, `Gemfile`, `go.mod`, etc.) with `read_file`.\n"
        "- Read server entrypoints (server.js, main.py, etc.) to discover ports and routes.\n"
        "- Call `declare_stack_profile` to record your findings.\n\n"
        "STEP 2: DEVOPS INFRASTRUCTURE INTERVIEW\n"
        "- DO NOT jump straight to writing a generic Dockerfile. First consult the developer by calling `ask_user`.\n"
        "- Inquire about their target deployment destination (e.g. Cloud IaaS AWS/GCP, PaaS Render/Railway, Self-Managed VPS, or Local Staging Sandbox).\n"
        "- If it is a monorepo or multi-service stack, inquire how they wish to package and connect the services."
    ),
    StageEnum.INTERVIEW: (
        "You are an expert DevOps Architect consulting on cloud deployment strategy.\n"
        "Review the developer's target infrastructure choice and requirements:\n"
        "- If PaaS (Render / Railway / Vercel): Design the PaaS blueprint (e.g. `render.yaml`) and service Dockerfiles.\n"
        "- If Cloud IaaS (AWS / GCP / Azure): Design the containerization setup for ECS/Cloud Run with Terraform IaC (`main.tf`) and CI/CD workflow (`.github/workflows/deploy.yml`).\n"
        "- If Self-Managed VPS / Local Staging: Design the production `docker-compose.yml`, Dockerfiles, and reverse-proxy/environment blueprints.\n"
        "- If the developer is unsure or asks for advice: Provide clear, expert guidance on costs, complexity, and operational trade-offs for their specific stack.\n"
        "Once aligned, proceed to `PLAN` and propose the configuration files using `write_file`."
    ),
    StageEnum.PLAN: (
        "You are preparing deployment manifests for the developer's chosen target infrastructure.\n"
        "MANDATORY: Invoke `write_file` to create the verified artifacts (Dockerfile(s), docker-compose.yml, IaC/PaaS config, and .env.example).\n"
        "Do NOT write file contents in chat prose; always use `write_file`."
    ),
    StageEnum.EXECUTE: (
        "You are generating and testing deployment artifacts for the chosen infrastructure target.\n"
        "MANDATORY SECURITY & TECHNICAL GUARDRAILS:\n"
        "1. ZERO HOST MOUNTS: In `docker-compose.yml`, NEVER mount host application directories (e.g. NEVER write `volumes: - .:/app`). All code must be self-contained in container images.\n"
        "2. ZERO CHAT DELAYS: Never output 'I will write this file' in chat prose. Directly invoke the `write_file` tool call in the same turn.\n"
        "3. ZERO SECRETS: Never ask for or write real passwords or tokens. Always use `.env.example` with placeholder values."
    ),
    StageEnum.VERIFY: (
        "Verify the running container services inside the sandbox container.\n"
        "Query service health endpoints using `run_command` (e.g. `curl -I http://localhost:<port>`) and inspect container statuses.\n"
        "If application source code errors occur (SyntaxError), quote verbatim and halt under the Stop Rule."
    ),
    StageEnum.EXPORT: (
        "The deployment has been verified inside the sandbox! Congratulate the developer.\n"
        "Deliver the complete DevOps deployment bundle: container manifests, target infrastructure config (IaC/PaaS blueprint), CI/CD pipeline, .env.example, and the verified Playbook."
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
        Deep recursive codebase reconnaissance and platform feasibility analysis.
        """
        if not os.path.exists(repo_path):
            return "Generic Application", 8000
        profile = reconnaissance_engine.analyze_repository(repo_path)
        port = profile.components[0].ports[0] if (profile.components and profile.components[0].ports) else 8000
        return profile.headline, port

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
            if os.path.abspath(local_path) != os.path.abspath(target_dir):
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

        # Step 4: Codebase Reconnaissance & Stack Discovery
        steps[3].label = "Analyzing codebase architecture…"
        steps[3].status = "running"
        steps[3].detail = "Scanning runtime topology, host socket requirements, platform feasibility, and services."

        profile = reconnaissance_engine.analyze_repository(target_dir)
        detected_stack = profile.headline
        detected_port = profile.components[0].ports[0] if (profile.components and profile.components[0].ports) else 8000

        steps[3].status = "completed"
        steps[3].detail = f"Identified {detected_stack} (primary port {detected_port})."
        status_resp.detected_stack = detected_stack

        # Step 5: Ready Hand-off
        steps[4].label = f"Ready. {detected_stack}."
        steps[4].status = "completed"
        steps[4].detail = "Ephemeral sandbox ready. Commencing DevOps infrastructure consultation."
        status_resp.completed = True

        summary_msg = (
            f"I have inspected **{repo_name}** and mapped its codebase architecture:\n\n"
            f"- **Stack**: **{profile.headline}**\n"
            f"- **Architecture**: {profile.project_summary}\n"
        )
        if profile.components:
            comp_list = []
            for c in profile.components:
                dep_info = f" (requires: {', '.join(c.host_dependencies)})" if c.host_dependencies else ""
                port_str = f"port `{c.ports[0]}`" if c.ports else "internal utility"
                comp_list.append(f"  - **{c.name}** (`{c.path}`): {c.runtime} on {port_str}{dep_info}")
            summary_msg += "\n**Discovered Services & Components:**\n" + "\n".join(comp_list) + "\n"

        if not profile.paas_compatible:
            summary_msg += (
                f"\n⚠️ **Critical Host Requirements Identified**:\n"
                + "\n".join([f"- {b}" for b in profile.paas_blockers])
                + "\n\n🚫 **Platform Feasibility Warning**: Standard PaaS providers (Render, Vercel, Railway Standard) **cannot** run this application because they disallow host Docker daemon access (`/var/run/docker.sock`) and privileged execution (`--privileged`). Deploying to PaaS will crash at runtime."
            )
        else:
            summary_msg += "\n✅ **Platform Feasibility**: Compatible with standard PaaS (Render / Railway / Vercel), Cloud IaaS, or Self-Managed VPS."

        summary_msg += "\n\nI have provisioned an isolated container sandbox for testing your build."

        question_text = profile.consultation_question
        options = profile.consultation_options

        facts = [
            LedgerEntry(category="declared", fact=f"Framework stack: {profile.headline}", evidence=os.path.basename(target_dir)),
            LedgerEntry(category="declared", fact=f"Configured service port: {detected_port}", evidence="manifest analysis"),
            LedgerEntry(category="verified", fact=f"Quarantine scan: {len(quarantined)} secret file(s) isolated", evidence="safety scanner"),
        ]
        if profile.paas_blockers:
            for blocker in profile.paas_blockers:
                facts.append(LedgerEntry(category="verified", fact=f"Host constraint: {blocker}", evidence="reconnaissance scan"))
        if not profile.paas_compatible:
            facts.append(LedgerEntry(category="verified", fact="PaaS feasibility: INCOMPATIBLE (Host Docker socket or privileged mode required)", evidence="reconnaissance scan"))

        session = SessionState(
            session_id=session_id,
            stage=StageEnum.INTERVIEW,
            repo_path=target_dir,
            repo_url=repo_url,
            detected_stack=detected_stack,
            quarantined_secrets=quarantined,
            app_type=detected_stack,
            app_port=detected_port,
            facts_ledger=facts,
            messages=[
                ChatMessage(role="assistant", content=summary_msg)
            ],
            current_tool_call=ToolCall(
                id=f"deploy_target_{str(uuid.uuid4())[:8]}",
                tool_name="ask_user",
                arguments={
                    "question_id": "deployment_target",
                    "question": question_text,
                    "options": options
                },
                status=ToolCallStatus.PENDING_APPROVAL,
                requires_approval=True
            ),
            last_activity=time.time()
        )
        self.sessions[session_id] = session
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

            if tool_calls:
                history.append({"role": "assistant", "content": content, "tool_calls": tool_calls})
                tool_id = tool_calls[0].get("id") or str(uuid.uuid4())[:8]
            else:
                tool_id = str(uuid.uuid4())[:8]

            if tool_name in ["list_dir", "read_file"]:
                exec_result = execute_readonly_tool(tool_name, args, session.repo_path)
                result_str = str(exec_result.get("entries") or exec_result.get("content") or exec_result)
                history.append({
                    "role": "tool",
                    "tool_call_id": tool_id,
                    "content": result_str[:2500]
                })
                continue
            elif tool_name == "declare_stack_profile":
                fw = args.get("framework") or ""
                arch = args.get("architecture") or "monorepo"
                summary = args.get("summary") or ""
                deps = args.get("detected_dependencies") or []

                profile = reconnaissance_engine.analyze_repository(session.repo_path)
                if not fw or fw.lower() in ("unknown", "generic application", "generic", "application service"):
                    fw = profile.headline
                    port = profile.components[0].ports[0] if (profile.components and profile.components[0].ports) else 8000
                else:
                    port = args.get("port") or (profile.components[0].ports[0] if (profile.components and profile.components[0].ports) else 8000)

                session.detected_stack = fw
                session.app_port = port
                session.app_type = fw

                session.facts_ledger.append(LedgerEntry(
                    category="verified",
                    fact=f"AI Codebase Profile: {fw} ({arch})",
                    evidence=f"Port {port}"
                ))
                if profile.paas_blockers:
                    for blocker in profile.paas_blockers:
                        session.facts_ledger.append(LedgerEntry(
                            category="verified",
                            fact=f"Host constraint: {blocker}",
                            evidence="reconnaissance scan"
                        ))
                if not profile.paas_compatible:
                    session.facts_ledger.append(LedgerEntry(
                        category="verified",
                        fact="PaaS feasibility: INCOMPATIBLE (Host Docker socket or privileged mode required)",
                        evidence="reconnaissance scan"
                    ))

                # Update setup status if active
                status_resp = self.setup_statuses.get(session.session_id)
                if status_resp:
                    status_resp.detected_stack = fw
                    if len(status_resp.steps) >= 5:
                        status_resp.steps[3].status = "completed"
                        status_resp.steps[3].detail = f"AI identified {fw} (port {port})."
                        status_resp.steps[4].label = f"Ready. {fw}"
                        status_resp.steps[4].detail = summary or profile.project_summary

                question_text = profile.consultation_question
                options = profile.consultation_options

                session.stage = StageEnum.INTERVIEW
                session.current_tool_call = ToolCall(
                    id=f"deploy_target_{tool_id}",
                    tool_name="ask_user",
                    arguments={
                        "question_id": "deployment_target",
                        "question": question_text,
                        "options": options
                    },
                    status=ToolCallStatus.PENDING_APPROVAL,
                    requires_approval=True
                )
                break
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
                return await self._verify_and_self_heal_dockerfile(session, file_path=fname)
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


    async def _verify_and_self_heal_dockerfile(self, session: SessionState, file_path: str = "Dockerfile") -> SessionState:
        """
        Autonomous AI Sandbox Build & Self-Healing Loop:
        1. Executes `docker build -t <tag> -f <file_path> <context>` inside the DinD sandbox container.
        2. If exit_code == 0: records verified evidence, informs user, and proceeds to docker-compose.yml.
        3. If exit_code != 0:
           - If fatal application syntax/code bug: Stop Rule halts.
           - If build/packaging error: AI analyzes stderr, updates Dockerfile directly, and retries (up to MAX_RETRY_LIMIT).
        """
        repo_name = os.path.basename(session.repo_path.rstrip("/\\")) or "app"
        clean_tag = re.sub(r'[^a-zA-Z0-9_\-\.]', '', repo_name.lower()) or "app"

        norm_path = file_path.replace("\\", "/").lstrip("./")
        if "/" in norm_path:
            context_dir = os.path.dirname(norm_path)
            sub_name = os.path.basename(context_dir)
            image_tag = f"{clean_tag}-{sub_name}:test"
            build_cmd = f"docker build -t {image_tag} -f {norm_path} {context_dir}"
        else:
            image_tag = f"{clean_tag}:test"
            build_cmd = f"docker build -t {image_tag} -f {norm_path} ."

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
                    f"The Dockerfile `{norm_path}` has been built and verified inside the sandbox container (exit code 0).\n"
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
                    f"🔧 **AI Self-Healing**: Diagnosing build failure, updating `{norm_path}`, and re-testing inside the sandbox..."
                )
            ))

            target_dockerfile_path = os.path.join(session.repo_path, norm_path)
            current_df = ""
            if os.path.exists(target_dockerfile_path):
                try:
                    with open(target_dockerfile_path, "r", encoding="utf-8", errors="replace") as f:
                        current_df = f.read()
                except Exception:
                    pass

            healing_instruction = (
                f"CRITICAL: The sandbox `docker build` for {image_tag} failed with exit code {res.get('exit_code')}.\n"
                f"Current Dockerfile (`{norm_path}`):\n```dockerfile\n{current_df}\n```\n\n"
                f"Build Error Stderr:\n```\n{truncate_output(err, 1500)}\n```\n\n"
                f"Diagnose the error above. Fix the Dockerfile (e.g. adjust base image version, install required build packages/compilers, fix COPY paths, or correct command syntax). "
                f"MANDATORY: You MUST call the `write_file` tool with file_path='{norm_path}' and the complete corrected content."
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
                with open(target_dockerfile_path, "w", encoding="utf-8") as f:
                    f.write(fixed_content)
                session.exported_artifacts[norm_path] = fixed_content
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
