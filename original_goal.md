# LabOps Deploy Assistant: Product Specification & Build Plan
*Oct 31, 2026 · @vansh malani*

## Goal and Product Scope
The project is an interactive containerization and deployment assistant for LabOps that takes a finished repository via a public Git URL, isolates it inside a disposable sandbox container, interviews the developer, and generates verified containerization artifacts (Dockerfile, compose file, `.env.example`, deploy runbook) with human-in-the-loop approval on every action.

**Core Product Pitch**: A Git link as a hard gate keeps the user's host machine out of the picture entirely, which is our primary pitch against tools that run on the host with access to private files and environment variables.

---

## 🧭 The Core Product Flow

1. **Start Screen (Hard Gate)**
   - Single input field: *"Paste a link to a Git repository"*.
   - Badge / Notice: *"Public repositories only for now"*.
   - Reassurance: *"It can download things, but it can't reach your computer or your accounts."*
   - Real-time HTTPS and public repository URL validation (rejecting private SSH URLs and embedded tokens).
   - Trust Card with the explicit promises:
     > **A private workspace, just for this.** Your project is copied into a temporary workspace, separate from your computer and your accounts.  
     > **Gone when you're done.** When you close this session, the workspace and everything in it is deleted.  
     > **No secrets needed.** Don't paste passwords or keys. I won't ask for them, and I skip files that usually hold them.  
     > **One thing to know:** to understand your project, I read your files and send their text to an AI model.

2. **Setting Up Your Workspace (Live Setup Screen)**
   Shows while the shallow clone and inspection run, with live status lines and reassurance:
   - *"Opening a fresh workspace…"* (Ephemeral sandbox created)
   - *"Downloading your project from GitHub…"* (Shallow clone `--depth 1`)
   - *"Setting aside files that might hold secrets…"* (Quarantines `.env`, key files, credentials so the model never sees them)
   - *"Taking a look at what's inside…"* (Stack inspection)
   - *"Ready. This looks like a Node app."* (or FastAPI app)

3. **Hand-Off to Chat**
   - The assistant opens immediately with what it found (e.g. *"This looks like a Node app with an Express server and package.json dependencies."*).
   - Begins the short interview (companion database needed, ports, learn vs. ship).
   - Proposes configuration files (`write_file`) and build/verify commands (`run_command`), waiting for user approval at each step.

4. **Closing & Teardown**
   - Before the workspace is deleted, offers *"Download your files"* (the verified Dockerfile, docker-compose.yml, .env.example, and deploy runbook bundle).
   - Shows a clear confirmation once the workspace is gone, proving the deletion happened to build trust and ensure users never lose their artifacts.

---

## 🔒 Security Promises & Enforcement Checklist

- [x] **Ephemeral Disposable Sandboxes**: Run the sandbox as a disposable container, deleted when the session ends and after an idle timeout.
- [x] **Zero Host Mounts & Zero Host Env**: Mount nothing from the host and pass no host environment variables into it.
- [x] **Secret Quarantine & Exclusion**: Executor strictly refuses to read files like `.env`, `.env.*`, key files (`.pem`, `.key`, `id_rsa`), and credentials. If variables are needed, the assistant generates `.env.example` with placeholder values and asks for non-secret values.
- [x] **Constrained Git Clone**: Shallow clone (`--depth 1`), strict timeout (45s), size limit checks (100MB max).
- [x] **Public Repositories Only**: Private repositories requiring tokens are excluded to guarantee zero secrets in flight.
- [x] **Path Traversal Protection**: All file read/write operations strictly jailed to the isolated session directory.
- [x] **Stop Rule**: If build fails due to user's application code, quote the error verbatim and halt rather than attempting arbitrary app code refactoring.

---

## In Scope
- One model backend (Amazon Bedrock / OpenAI-compatible).
- Tools: `list_dir`, `read_file`, `write_file`, `ask_user`, `run_command`. File writes and commands need user approval.
- Three short interview questions (learn or just ship, database needed, local or server).
- Supported repo types: Node.js (Express, Next, etc.) and Python (FastAPI, Flask, etc.).
- Finish line: the app responds on its port inside the sandbox, and the assistant exports verified artifacts.

## Out of Scope
- Kubernetes, ArgoCD and AWS execution (mentioned only as next steps in the recommendation runbook).
- Autonomous mode without human approval.
- Other arbitrary languages, RAG, and anything touching real cloud accounts.
