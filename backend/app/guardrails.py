import re
import os
from typing import Tuple, List, Optional
from urllib.parse import urlparse

BLOCKED_COMMAND_PATTERNS = [
    r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*\s+(/|\~|\$HOME)(\s|$|\*)",
    r"\bmkfs\b",
    r"\bshred\b",
    r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:", # fork bomb
    r"\bdd\s+if=/dev/zero\b",
    r"\bchmod\s+-R\s+777\s+(/|\~|\$HOME)",
    r">(\s*)/dev/sd[a-z]",
    r"\b(mount|umount|chroot)\b",
    r"\b(printenv|export\s+-p)\b",
    r"/etc/shadow",
    r"/etc/sudoers",
    r"\bcurl\s+.*(@|\.env)",
]

# Patterns for files that typically hold secrets, API keys, or credentials
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)",
    r"disregard\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)",
    r"forget\s+(all\s+)?(previous|prior|above)\s+(instructions|prompts|rules)",
    r"you\s+are\s+now\s+(an?|a)\s+",
    r"act\s+as\s+(an?|a)\s+",
    r"system\s+(override|prompt|reset)",
    r"jailbreak",
    r"\bDAN\s+mode\b",
    r"repeat\s+(everything|the\s+text)\s+above",
    r"what\s+is\s+your\s+system\s+prompt",
]

def check_prompt_injection(user_input: str) -> Tuple[bool, str]:
    """
    Detects attempts to hijack, jailbreak, or distract the deployment assistant.
    Returns (is_injection, reason).
    """
    cleaned = (user_input or "").strip()
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, cleaned, re.IGNORECASE):
            return True, f"Blocked prompt injection pattern: {pattern}"
    return False, ""

SECRET_FILE_REGEXES = [
    r"^\.env(\..+)?$",
    r".*\.(pem|key|pkcs12|pfx|p12|keystore)$",
    r"^id_(rsa|dsa|ecdsa|ed25519)(\.pub)?$",
    r".*(credential|service[-_]?account|private[-_]?key).*\.(json|yaml|yml|txt)$",
    r"^\.aws([\\/].+)?$",
    r"^\.netrc$",
    r"^\.npmrc$",
]

# Safe non-secret templates that are explicitly allowed
ALLOWED_ENV_TEMPLATES = [
    r"^\.env\.example$",
    r"^\.env\.sample$",
    r"^\.env\.template$",
]

def is_secret_file(file_path: str) -> bool:
    """
    Check if a relative file path matches patterns of files holding secrets/credentials.
    Templates like .env.example are explicitly permitted.
    """
    normalized = file_path.replace("\\", "/").strip().lstrip("/")
    basename = os.path.basename(normalized)

    # Allow harmless example templates
    for allowed_pattern in ALLOWED_ENV_TEMPLATES:
        if re.match(allowed_pattern, basename, re.IGNORECASE):
            return False

    # Check against secret patterns
    for secret_pattern in SECRET_FILE_REGEXES:
        if re.search(secret_pattern, basename, re.IGNORECASE) or re.search(secret_pattern, normalized, re.IGNORECASE):
            return True

    return False

def scan_and_quarantine_secrets(repo_path: str) -> List[str]:
    """
    Scans a cloned repository for secret-bearing files.
    Returns list of discovered secret files that must be isolated/set aside.
    """
    quarantined = []
    if not os.path.exists(repo_path):
        return quarantined

    for root, dirs, files in os.walk(repo_path):
        # Skip .git directory
        if ".git" in dirs:
            dirs.remove(".git")
        for fname in files:
            full_path = os.path.join(root, fname)
            rel_path = os.path.relpath(full_path, repo_path).replace("\\", "/")
            if is_secret_file(rel_path):
                quarantined.append(rel_path)

    return quarantined

def validate_git_url(url: str) -> Tuple[bool, str, Optional[str]]:
    """
    Validates a Git repository URL before cloning:
    - Must be HTTPS
    - Must be a public repository (no basic auth tokens or credentials in URL)
    - Must be a recognizable git URL (github.com, gitlab.com, bitbucket.org, etc.)
    Returns (is_valid, error_message, cleaned_repo_name).
    """
    cleaned = (url or "").strip()
    if not cleaned:
        return False, "Please paste a Git repository URL.", None

    # Reject SSH links
    if cleaned.startswith("git@"):
        return (
            False,
            "SSH URLs require private SSH keys. Please use a public HTTPS repository URL (e.g., https://github.com/owner/repo).",
            None
        )

    # Enforce HTTPS only
    if not cleaned.startswith("https://"):
        return (
            False,
            "Only HTTPS repository links are supported. Public repositories only for now.",
            None
        )

    # Reject URLs containing tokens or passwords (e.g. https://ghp_xxx@github.com or https://user:pass@...)
    parsed = urlparse(cleaned)
    if parsed.username or parsed.password:
        return (
            False,
            "Do not paste repository links containing personal access tokens or credentials. Public repositories only for now.",
            None
        )

    # Recognizable repo check
    netloc = parsed.netloc.lower()
    path = parsed.path.strip("/").rstrip(".git")
    if not netloc or not path or len(path.split("/")) < 2:
        return (
            False,
            "Please provide a valid public repository link in format https://github.com/owner/repository",
            None
        )

    repo_name = path.split("/")[-1]
    return True, "", repo_name

def sanitize_compose_guardrails(content: str) -> Tuple[str, List[str]]:
    """
    Enforces the Zero Host Mounts security guardrail.
    Strips relative host binds like '.:/app' or './:/usr/src/app' from docker-compose.yml
    because production container artifacts must be self-contained (packaged via Dockerfile COPY).
    Returns (cleaned_content, list_of_violations_fixed).
    """
    lines = content.splitlines()
    cleaned_lines = []
    violations = []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("-") and ":" in stripped:
            entry = stripped.lstrip("- ").strip()
            src = entry.split(":", 1)[0].strip()
            # Match host relative paths: ., .., ./, ../, $PWD, ~, or absolute host roots
            if src in (".", "..") or src.startswith(("./", ".\\", "../", "..\\", "$PWD", "${PWD}", "~")):
                violations.append(stripped)
                continue
            if src.startswith("/") and not src.startswith("/var/run/docker.sock"):
                violations.append(stripped)
                continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines), violations

def is_command_safe(command: str) -> Tuple[bool, str]:
    """Check command against blocked destructive and exfiltration patterns."""
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return False, f"Command contains blocked pattern: {pattern}"
    return True, ""

def truncate_output(output: str, max_length: int = 4000) -> str:
    """Truncates terminal or file output to avoid bloating context."""
    if not output:
        return ""
    if len(output) > max_length:
        return output[:max_length] + f"\n... [Output truncated, {len(output) - max_length} characters omitted] ..."
    return output

def is_app_code_error(error_output: str) -> bool:
    """
    Detect if failure is caused by user application code error
    (e.g., SyntaxError, ModuleNotFoundError, ImportError, TypeError)
    versus Docker/deployment infrastructure setup.
    """
    indicators = [
        "SyntaxError:",
        "IndentationError:",
        "ModuleNotFoundError: No module named",
        "ReferenceError:",
        "TypeError:",
        "Cannot find module",
        "Parse error on line",
    ]
    return any(ind in error_output for ind in indicators)
