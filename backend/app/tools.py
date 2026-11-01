import os
from typing import Dict, Any, List
from app.guardrails import truncate_output, is_secret_file
from app.docker_bridge import docker_bridge

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List files and directories in a given relative path within the repo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Subdirectory path relative to repo root. Empty string or '.' for root."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read contents of a file within the repository (e.g. package.json, requirements.txt, server code). Secret files (.env, key files) are strictly blocked.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to file in repo."
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write or overwrite a configuration file (such as Dockerfile, docker-compose.yml, .dockerignore, .env.example). Requires user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Relative path to file to write."
                    },
                    "content": {
                        "type": "string",
                        "description": "Full file content to write."
                    }
                },
                "required": ["file_path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a shell command inside the repository sandbox (e.g., docker build, docker compose up, curl). Requires user approval.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "Shell command to run."
                    }
                },
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user",
            "description": "Ask the user a clarifying question before proceeding (e.g. interview questions about ports, database, environment).",
            "parameters": {
                "type": "object",
                "properties": {
                    "question_id": {
                        "type": "string",
                        "description": "Unique key identifier for question."
                    },
                    "question": {
                        "type": "string",
                        "description": "The question to present to the user."
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of choice options if multiple choice, or empty for free-text."
                    }
                },
                "required": ["question_id", "question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "declare_stack_profile",
            "description": "Declare the discovered application profile after inspecting repository files (stack, architecture, service port, dependencies). Call this during inspection.",
            "parameters": {
                "type": "object",
                "properties": {
                    "framework": {
                        "type": "string",
                        "description": "Primary framework and language (e.g. 'Node.js (Express + Socket.io)', 'Python (FastAPI)', 'Go Service', 'Ruby on Rails', 'Next.js + Flask Monorepo')"
                    },
                    "port": {
                        "type": "integer",
                        "description": "Discovered listening port for the main application service (e.g. 5007, 8000, 3000, 8080)"
                    },
                    "architecture": {
                        "type": "string",
                        "description": "Architecture archetype: 'single-service', 'monorepo', 'microservices', or 'static-spa'"
                    },
                    "detected_dependencies": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Detected backing services or databases (e.g. ['PostgreSQL', 'Redis', 'MongoDB']) or empty if stateless"
                    },
                    "summary": {
                        "type": "string",
                        "description": "Concise 1-2 sentence technical summary of the codebase architecture"
                    }
                },
                "required": ["framework", "port", "architecture"]
            }
        }
    },
]

def _is_safe_repo_path(repo_path: str, target_subpath: str) -> bool:
    """Ensure path cannot escape repository root."""
    try:
        resolved_repo = os.path.realpath(repo_path)
        resolved_target = os.path.realpath(os.path.join(repo_path, target_subpath.lstrip("/\\")))
        return resolved_target.startswith(resolved_repo)
    except Exception:
        return False

def execute_readonly_tool(tool_name: str, args: Dict[str, Any], repo_path: str) -> Dict[str, Any]:
    """Executes read-only tools immediately without requiring user approval."""
    if tool_name == "list_dir":
        rel_path = args.get("path", "")
        if not _is_safe_repo_path(repo_path, rel_path):
            return {"error": "Access denied: Path escapes repository workspace."}

        target_dir = os.path.join(repo_path, rel_path).strip()
        if not os.path.exists(target_dir):
            return {"error": f"Path not found: {args.get('path')}"}
        try:
            entries = os.listdir(target_dir)
            files = []
            for item in entries:
                if item == ".git":
                    continue
                full_p = os.path.join(target_dir, item)
                rel_item = os.path.relpath(full_p, repo_path)
                # Show if quarantined
                if is_secret_file(rel_item):
                    files.append(f"[QUARANTINED SECRET] {item}")
                else:
                    files.append(f"{'[DIR]' if os.path.isdir(full_p) else '[FILE]'} {item}")
            return {"entries": files}
        except Exception as e:
            return {"error": str(e)}

    elif tool_name == "declare_stack_profile":
        fw = args.get("framework", "Application Service")
        port = args.get("port", 8000)
        arch = args.get("architecture", "single-service")
        return {
            "status": "success",
            "message": f"Successfully declared stack profile: {fw} (port {port}, architecture: {arch})."
        }

    elif tool_name == "read_file":
        file_path = args.get("file_path", "").strip()
        if not _is_safe_repo_path(repo_path, file_path):
            return {"error": "Access denied: Path escapes repository workspace."}

        # ENFORCE ZERO SECRETS PROMISE: Refuse to read .env or credential/key files
        if is_secret_file(file_path):
            return {
                "error": f"Access denied: '{file_path}' has been set aside because it might hold sensitive secrets or keys. The assistant refuses to read secret files to preserve your privacy."
            }

        target_file = os.path.join(repo_path, file_path).strip()
        if not os.path.exists(target_file):
            return {"error": f"File not found: {args.get('file_path')}"}
        try:
            with open(target_file, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return {"content": truncate_output(content, max_length=6000)}
        except Exception as e:
            return {"error": str(e)}

    return {"error": f"Unknown or non-readonly tool: {tool_name}"}

def execute_approved_tool(tool_name: str, args: Dict[str, Any], repo_path: str) -> Dict[str, Any]:
    """Executes tools that were explicitly approved by the user."""
    if tool_name == "write_file":
        rel_path = args.get("file_path", "").lstrip("/\\")
        if not _is_safe_repo_path(repo_path, rel_path):
            return {"error": "Access denied: Path escapes repository workspace."}

        # Do not allow overwriting genuine secret files; encourage .env.example
        if is_secret_file(rel_path) and not rel_path.endswith(".example") and not rel_path.endswith(".sample"):
            return {
                "error": f"Forbidden: Writing to '{rel_path}' is restricted. Please generate `.env.example` with placeholder values instead."
            }

        content = args.get("content", "")
        dest = os.path.join(repo_path, rel_path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8") as f:
            f.write(content)
        return {
            "success": True,
            "message": f"Successfully wrote {len(content)} bytes to {rel_path}",
            "file_path": rel_path
        }

    elif tool_name == "run_command":
        cmd = args.get("command", "")
        return docker_bridge.execute_command(command=cmd, working_dir=repo_path)

    return {"error": f"Invalid tool execution: {tool_name}"}
