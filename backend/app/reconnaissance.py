import os
import re
import json
from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field

class ComponentProfile(BaseModel):
    name: str
    path: str
    runtime: str
    role: str
    ports: List[int] = Field(default_factory=list)
    host_dependencies: List[str] = Field(default_factory=list)

class ArchitectureProfile(BaseModel):
    headline: str
    project_summary: str
    components: List[ComponentProfile]
    requires_docker_socket: bool = False
    requires_privileged: bool = False
    requires_gpu: bool = False
    cloud_sdks: List[str] = Field(default_factory=list)
    detected_databases: List[str] = Field(default_factory=list)
    paas_compatible: bool = True
    paas_blockers: List[str] = Field(default_factory=list)
    recommended_targets: List[Dict[str, str]]
    consultation_question: str
    consultation_options: List[str]

class CodebaseReconnaissance:
    """
    Deep recursive codebase and infrastructure reconnaissance engine.
    Reverse-engineers runtime topology, host capabilities, and platform compatibility.
    """

    def analyze_repository(self, repo_path: str) -> ArchitectureProfile:
        components: List[ComponentProfile] = []
        requires_docker_socket = False
        requires_privileged = False
        requires_gpu = False
        cloud_sdks = set()
        detected_databases = set()

        if not os.path.exists(repo_path):
            return self._build_generic_profile("Empty Workspace", [])

        # 1. Scan for existing compose / orchestration configs
        for compose_file in ["docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"]:
            cp = os.path.join(repo_path, compose_file)
            if os.path.exists(cp):
                try:
                    with open(cp, "r", encoding="utf-8", errors="replace") as f:
                        c_text = f.read()
                    if "/var/run/docker.sock" in c_text or "docker.sock" in c_text:
                        requires_docker_socket = True
                    if "privileged: true" in c_text or "privileged:\n" in c_text:
                        requires_privileged = True
                except Exception:
                    pass

        # 2. Recursive scan for services and manifests (up to 3 levels deep)
        for root, dirs, files in os.walk(repo_path):
            rel = os.path.relpath(root, repo_path)
            depth = len(rel.split(os.sep)) if rel != "." else 0
            if depth > 3:
                continue

            for skip in [".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build", ".next", "fixtures", "tests", "test", "__fixtures__"]:
                if skip in dirs:
                    dirs.remove(skip)

            # Node.js Component
            if "package.json" in files:
                comp = self._analyze_node_component(root, repo_path, rel)
                if comp:
                    components.append(comp)

            # Python Component
            if "requirements.txt" in files or "pyproject.toml" in files or "Pipfile" in files:
                comp = self._analyze_python_component(root, repo_path, rel)
                if comp:
                    components.append(comp)
                    # Check for docker libraries or cloud SDKs
                    for dep in comp.host_dependencies:
                        if "Docker Daemon" in dep or "docker" in dep.lower():
                            requires_docker_socket = True
                        if "AWS" in dep:
                            cloud_sdks.add("AWS (boto3)")

            # Go Component
            if "go.mod" in files:
                components.append(ComponentProfile(
                    name=os.path.basename(root) if rel != "." else "go-service",
                    path=rel,
                    runtime="Go",
                    role="backend-service",
                    ports=[8080]
                ))

            # Rust Component
            if "Cargo.toml" in files:
                components.append(ComponentProfile(
                    name=os.path.basename(root) if rel != "." else "rust-service",
                    path=rel,
                    runtime="Rust",
                    role="backend-service",
                    ports=[8080]
                ))

            # Deep code inspection for docker socket / GPU / cloud SDKs across source files
            for fname in files:
                if fname.endswith((".py", ".js", ".ts", ".go", ".sh", ".yaml", ".yml")):
                    fp = os.path.join(root, fname)
                    try:
                        with open(fp, "r", encoding="utf-8", errors="replace") as sf:
                            snippet = sf.read(8000)
                        if "/var/run/docker.sock" in snippet or "aiodocker" in snippet:
                            requires_docker_socket = True
                        if "torch.cuda" in snippet or "cuda" in snippet.lower() and "nvidia" in snippet.lower():
                            requires_gpu = True
                        if "boto3" in snippet or "@aws-sdk" in snippet:
                            cloud_sdks.add("AWS SDK")
                        if "psycopg2" in snippet or "sqlalchemy" in snippet or "pg" in snippet:
                            detected_databases.add("PostgreSQL")
                        if "pymongo" in snippet or "mongoose" in snippet:
                            detected_databases.add("MongoDB")
                        if "redis" in snippet.lower() and ("import redis" in snippet or "require('redis')" in snippet or "createClient" in snippet):
                            detected_databases.add("Redis")
                    except Exception:
                        pass

        # 3. Deduplicate components by path
        seen_paths = set()
        dedup_components = []
        for c in components:
            if c.path not in seen_paths:
                seen_paths.add(c.path)
                dedup_components.append(c)
        components = dedup_components

        # 4. Evaluate PaaS vs IaaS feasibility
        paas_compatible = True
        paas_blockers = []
        if requires_docker_socket:
            paas_compatible = False
            paas_blockers.append("Requires direct access to host Docker daemon (/var/run/docker.sock)")
        if requires_privileged:
            paas_compatible = False
            paas_blockers.append("Requires privileged execution (Docker-in-Docker daemon)")
        if requires_gpu:
            paas_compatible = False
            paas_blockers.append("Requires NVIDIA GPU hardware acceleration")

        # 5. Build viable recommendations and consultation
        return self._synthesize_profile(
            repo_path=repo_path,
            components=components,
            requires_docker_socket=requires_docker_socket,
            requires_privileged=requires_privileged,
            requires_gpu=requires_gpu,
            cloud_sdks=list(cloud_sdks),
            detected_databases=list(detected_databases),
            paas_compatible=paas_compatible,
            paas_blockers=paas_blockers
        )

    def _analyze_node_component(self, root: str, repo_path: str, rel: str) -> Optional[ComponentProfile]:
        pkg_p = os.path.join(root, "package.json")
        try:
            with open(pkg_p, "r", encoding="utf-8") as f:
                data = json.load(f)
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            name = data.get("name") or (os.path.basename(root) if rel != "." else "frontend")

            runtime = "Node.js"
            role = "web-service"
            port = 3000

            if "next" in deps:
                runtime = "Next.js"
                role = "fullstack-ui"
                port = 3000
            elif "react" in deps or "react-dom" in deps:
                runtime = "React (Vite)" if "vite" in deps else "React SPA"
                role = "frontend-ui"
                port = 3000
            elif "express" in deps:
                runtime = "Node.js (Express)"
                role = "api-service"
                port = 3000
            elif "vue" in deps:
                runtime = "Vue.js"
                role = "frontend-ui"
                port = 3000

            # Scan entrypoint files for custom ports
            for ep in ["server.js", "app.js", "index.js", "vite.config.ts", "vite.config.js"]:
                ep_p = os.path.join(root, ep)
                if os.path.exists(ep_p):
                    try:
                        with open(ep_p, "r", encoding="utf-8", errors="replace") as ef:
                            c = ef.read()
                        m = re.search(r'(?:PORT\s*=\s*(?:process\.env\.PORT\s*\|\|\s*)?|port\s*:\s*|listen\s*\(\s*)(\d{4,5})', c, re.IGNORECASE)
                        if m:
                            port = int(m.group(1))
                    except Exception:
                        pass

            host_deps = []
            if "dockerode" in deps or "docker" in deps:
                host_deps.append("Docker Daemon API")

            return ComponentProfile(
                name=name,
                path=rel,
                runtime=runtime,
                role=role,
                ports=[port],
                host_dependencies=host_deps
            )
        except Exception:
            return None

    def _analyze_python_component(self, root: str, repo_path: str, rel: str) -> Optional[ComponentProfile]:
        req_p = os.path.join(root, "requirements.txt")
        content = ""
        if os.path.exists(req_p):
            try:
                with open(req_p, "r", encoding="utf-8", errors="replace") as f:
                    content = f.read().lower()
            except Exception:
                pass

        runtime = "Python"
        role = "backend-service"
        port = None

        if "fastapi" in content:
            runtime = "Python (FastAPI)"
            role = "api-backend"
            port = 8000
        elif "django" in content:
            runtime = "Python (Django)"
            role = "web-backend"
            port = 8000
        elif "flask" in content:
            runtime = "Python (Flask)"
            role = "api-backend"
            port = 5000
        elif "tornado" in content or "aiohttp" in content:
            runtime = "Python (Async Service)"
            role = "api-backend"
            port = 8080

        # Scan for custom port in server entrypoints
        has_server_entrypoint = False
        for ep in ["main.py", "app.py", "server.py", "manage.py"]:
            ep_p = os.path.join(root, ep)
            if os.path.exists(ep_p):
                has_server_entrypoint = True
                try:
                    with open(ep_p, "r", encoding="utf-8", errors="replace") as ef:
                        c = ef.read()
                    m = re.search(r'(?:port\s*=\s*|PORT\s*=\s*|run\(.*port\s*=\s*)(\d{4,5})', c, re.IGNORECASE)
                    if m:
                        port = int(m.group(1))
                except Exception:
                    pass

        if not port and not has_server_entrypoint:
            role = "script-utility"
            ports = []
        else:
            ports = [port or 8000]

        host_deps = []
        if "docker" in content or "aiodocker" in content:
            host_deps.append("Host Docker Daemon Socket (/var/run/docker.sock)")
        if "boto3" in content or "awscrt" in content:
            host_deps.append("AWS SigV4 IAM Credentials")

        name = os.path.basename(root) if rel != "." else "backend"
        return ComponentProfile(
            name=name,
            path=rel,
            runtime=runtime,
            role=role,
            ports=ports,
            host_dependencies=host_deps
        )

    def _synthesize_profile(
        self,
        repo_path: str,
        components: List[ComponentProfile],
        requires_docker_socket: bool,
        requires_privileged: bool,
        requires_gpu: bool,
        cloud_sdks: List[str],
        detected_databases: List[str],
        paas_compatible: bool,
        paas_blockers: List[str]
    ) -> ArchitectureProfile:
        repo_name = os.path.basename(repo_path.rstrip("/\\")) or "application"

        # Determine architecture headline & summary
        web_components = [c for c in components if c.ports]
        if len(web_components) > 1:
            runtimes = list(dict.fromkeys(c.runtime for c in web_components))
            headline = f"Full-Stack Application ({' + '.join(runtimes[:2])})"
            summary = (
                f"Multi-component repository containing {len(components)} distinct modules: "
                f"{', '.join([f'{c.name} ({c.runtime} at `{c.path}`)' for c in components])}."
            )
        elif len(web_components) == 1:
            c = web_components[0]
            headline = f"{c.runtime} Application"
            summary = f"Single-service application built with {c.runtime} located at `{c.path}` (port `{c.ports[0]}`)."
        elif components:
            c = components[0]
            headline = f"{c.runtime} Workspace"
            summary = f"Workspace containing module `{c.name}` ({c.runtime} at `{c.path}`)."
        else:
            headline = "Generic Application"
            summary = "Single application workspace."

        recommended_targets = []
        consultation_options = []

        if not paas_compatible:
            headline += " [Host Daemon Required]"
            recommended_targets = [
                {
                    "target": "Cloud IaaS (AWS EC2 with Docker & Terraform)",
                    "title": "AWS EC2 VM with Docker Engine",
                    "description": "Full root virtual machine with Docker daemon installed. Ideal for container engines.",
                    "tradeoffs": "Full host control and privileged execution; requires managing the underlying VM."
                },
                {
                    "target": "Self-Managed VPS (Ubuntu + Docker Compose)",
                    "title": "Dedicated Linux VPS (Hetzner / DigitalOcean)",
                    "description": "Low-cost dedicated host with Docker Compose and direct socket access.",
                    "tradeoffs": "Lowest monthly cost; requires manual OS patch maintenance."
                },
                {
                    "target": "AWS ECS on EC2 (Privileged Task Definition)",
                    "title": "AWS Elastic Container Service on EC2",
                    "description": "Managed container orchestration supporting privileged mode and host socket mounts.",
                    "tradeoffs": "Scalable cloud orchestration; slightly higher setup complexity."
                },
                {
                    "target": "Local Staging Sandbox",
                    "title": "Local Ephemeral Sandbox",
                    "description": "Test and verify all services in the isolated DinD container environment.",
                    "tradeoffs": "Zero cloud costs; runs strictly in your workspace."
                }
            ]
            consultation_question = (
                f"I analyzed **{repo_name}**: it is a **{headline}**.\n\n"
                f"⚠️ **Critical Host Requirement**: This application requires direct access to a host Docker daemon (`/var/run/docker.sock`) or privileged container execution.\n\n"
                f"🚫 **PaaS Incompatibility**: Platforms like Vercel, Render, or Railway Standard **cannot** run this application because they disallow host Docker socket mounts.\n\n"
                f"Where would you like to deploy this infrastructure?"
            )
            consultation_options = [
                "Cloud IaaS (AWS EC2 with Docker & Terraform)",
                "Self-Managed VPS (Ubuntu + Docker Compose)",
                "AWS ECS on EC2 (Privileged Task Definition)",
                "Local Staging Sandbox"
            ]
        else:
            recommended_targets = [
                {
                    "target": "PaaS (Render / Railway / Vercel)",
                    "title": "Serverless Platform-as-a-Service",
                    "description": "Zero infrastructure management with automated git-push deployments.",
                    "tradeoffs": "Easiest to operate with zero VM maintenance; limited low-level host control."
                },
                {
                    "target": "Cloud IaaS (AWS ECS / GCP Cloud Run / Azure)",
                    "title": "Cloud Container Service",
                    "description": "Enterprise cloud container hosting with Terraform Infrastructure-as-Code.",
                    "tradeoffs": "High scalability and cloud VPC integration; requires cloud credentials."
                },
                {
                    "target": "Self-Managed VPS (Docker Compose + Nginx/Caddy)",
                    "title": "Self-Managed Linux VPS",
                    "description": "Simple container orchestration behind a reverse proxy on a dedicated server.",
                    "tradeoffs": "Predictable monthly cost; requires basic server maintenance."
                },
                {
                    "target": "Local Staging Sandbox",
                    "title": "Local Staging Environment",
                    "description": "Verify containers locally before choosing a cloud destination.",
                    "tradeoffs": "Free local testing."
                }
            ]
            consultation_question = (
                f"I analyzed **{repo_name}**: it is a **{headline}** (port `{components[0].ports[0] if (components and components[0].ports) else 8000}`). "
                f"This application is standard web architecture and can be deployed to PaaS, Cloud IaaS, or a VPS. "
                f"Where do you plan to deploy this stack?"
            )
            consultation_options = [
                "PaaS (Render / Railway / Vercel)",
                "Cloud IaaS (AWS ECS / GCP Cloud Run / Azure)",
                "Self-Managed VPS (Docker Compose + Nginx/Caddy)",
                "Local Staging Sandbox"
            ]

        return ArchitectureProfile(
            headline=headline,
            project_summary=summary,
            components=components,
            requires_docker_socket=requires_docker_socket,
            requires_privileged=requires_privileged,
            requires_gpu=requires_gpu,
            cloud_sdks=cloud_sdks,
            detected_databases=detected_databases,
            paas_compatible=paas_compatible,
            paas_blockers=paas_blockers,
            recommended_targets=recommended_targets,
            consultation_question=consultation_question,
            consultation_options=consultation_options
        )

    def _build_generic_profile(self, name: str, components: List[ComponentProfile]) -> ArchitectureProfile:
        return ArchitectureProfile(
            headline=name,
            project_summary=name,
            components=components,
            recommended_targets=[],
            consultation_question="Where do you plan to deploy this application?",
            consultation_options=["Cloud IaaS (AWS / GCP / Azure)", "PaaS (Render / Railway)", "Local Sandbox"]
        )

reconnaissance_engine = CodebaseReconnaissance()
