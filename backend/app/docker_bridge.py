import os
import time
import subprocess
from typing import Dict, Any, Optional
import docker
from app.config import settings
from app.guardrails import is_command_safe, truncate_output

class DockerBridge:
    def __init__(self):
        self.client = None
        self._init_docker()

    def _init_docker(self):
        try:
            self.client = docker.from_env()
            self.client.ping()
        except Exception:
            self.client = None

    def execute_command(
        self,
        command: str,
        working_dir: Optional[str] = None,
        container_name: Optional[str] = None,
        timeout: int = 120
    ) -> Dict[str, Any]:
        """
        Executes command inside the DinD sandbox container if available,
        or falls back to isolated subprocess execution within the repo directory.
        Mounts zero host directories and passes no host credentials.
        """
        safe, reason = is_command_safe(command)
        if not safe:
            return {
                "exit_code": 126,
                "stdout": "",
                "stderr": f"Security Guardrail: {reason}",
                "duration_ms": 0.0,
                "success": False
            }

        start_time = time.time()
        target_container = container_name or settings.SANDBOX_CONTAINER_NAME

        # 1. Try execution inside the DinD Sandbox container
        if self.client:
            try:
                container = self.client.containers.get(target_container)
                exec_result = container.exec_run(
                    cmd=["/bin/sh", "-c", f"cd /workspace && {command}"],
                    workdir="/workspace",
                    demux=True
                )
                duration_ms = (time.time() - start_time) * 1000
                stdout = exec_result.output[0].decode("utf-8", errors="replace") if exec_result.output and exec_result.output[0] else ""
                stderr = exec_result.output[1].decode("utf-8", errors="replace") if exec_result.output and exec_result.output[1] else ""

                return {
                    "exit_code": exec_result.exit_code,
                    "stdout": truncate_output(stdout),
                    "stderr": truncate_output(stderr),
                    "duration_ms": round(duration_ms, 2),
                    "success": exec_result.exit_code == 0
                }
            except docker.errors.NotFound:
                pass
            except Exception:
                pass

        # 2. Local isolated fallback execution strictly within session working_dir
        cwd = working_dir or settings.WORKSPACE_DIR
        os.makedirs(cwd, exist_ok=True)
        # Strip sensitive host environment variables
        safe_env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": cwd,
            "TEMP": cwd,
            "TMP": cwd,
            "LANG": "en_US.UTF-8",
        }

        try:
            proc = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                env=safe_env,
                timeout=timeout
            )
            duration_ms = (time.time() - start_time) * 1000
            return {
                "exit_code": proc.returncode,
                "stdout": truncate_output(proc.stdout),
                "stderr": truncate_output(proc.stderr),
                "duration_ms": round(duration_ms, 2),
                "success": proc.returncode == 0
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": 124,
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds.",
                "duration_ms": timeout * 1000,
                "success": False
            }
        except Exception as e:
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": f"Execution error: {str(e)}",
                "duration_ms": 0.0,
                "success": False
            }

    def teardown_workspace_containers(self, working_dir: str):
        """Stops and purges any docker-compose containers created in the workspace."""
        if os.path.exists(os.path.join(working_dir, "docker-compose.yml")):
            try:
                subprocess.run(
                    "docker compose down --volumes --remove-orphans",
                    shell=True,
                    cwd=working_dir,
                    capture_output=True,
                    timeout=30
                )
            except Exception:
                pass

docker_bridge = DockerBridge()
