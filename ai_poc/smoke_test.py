#!/usr/bin/env python3
"""
POC smoke test: evaluate open-weight and proprietary models across OpenAI-compatible
(Google AI Studio, Bedrock, etc.) and Amazon Bedrock Converse backends to drive a
tool-calling agent loop for the LabOps deploy assistant.

Backends:
  1. openai (default):
     Works with OpenAI-compatible endpoints (Google AI Studio Gemini,
     Bedrock OpenAI-compatible endpoint for gpt-oss, vLLM, etc.).

     Google AI Studio Setup:
       pip install openai
       export GEMINI_API_KEY="<your-key>"   # or put in .env
       python smoke_test.py --backend openai --models gemini-2.5-flash

     Bedrock OpenAI Setup:
       export LLM_BASE_URL="https://bedrock-runtime.<region>.amazonaws.com/openai/v1"
       export LLM_API_KEY="<Bedrock API Key>"
       python smoke_test.py --backend openai --models openai.gpt-oss-120b

  2. converse:
     Uses Amazon Bedrock Converse API via boto3 (supports Gemma, Qwen, Nova, Claude, etc.).

     Setup:
       pip install -U boto3
       export AWS_BEARER_TOKEN_BEDROCK="<your short-term key>"
       export AWS_REGION="<region>"  # default: us-east-1
       python smoke_test.py --backend converse --models <id1>,<id2>

What it checks, per model, over N trials each:
  1. ping            - plain chat works, and how many tokens it costs
  2. tool_first      - given a fresh repo, does it call list_dir with a path?
  3. tool_followup   - given a list_dir result, does it call read_file on package.json?
  4. json_fallback   - with no tools parameter, can it emit strict JSON {tool, args}?

A token budget stops the run early so it cannot drain your credit.
"""
import argparse
import base64
import json
import os
import re
import sys
import time

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

try:
    import boto3
except ImportError:
    boto3 = None

DEFAULT_REGION = os.getenv("AWS_REGION", "us-east-1")
DEFAULT_OPENAI_BASE_URL = f"https://bedrock-runtime.{DEFAULT_REGION}.amazonaws.com/openai/v1"
PREFERRED = ["gemini-2.5-flash", "gemini-1.5-flash", "gemini-2.5-pro", "gemini-1.5-pro", "openai.gpt-oss-120b", "gpt-oss-120b"]

TOOLS = [
    {"type": "function", "function": {
        "name": "list_dir", "description": "List files in a directory of the repo.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "read_file", "description": "Read a file from the repo.",
        "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
    {"type": "function", "function": {
        "name": "ask_user", "description": "Ask the user a question and wait for the answer.",
        "parameters": {"type": "object", "properties": {"question": {"type": "string"}}, "required": ["question"]}}},
    {"type": "function", "function": {
        "name": "run_command", "description": "Propose a shell command to run in the sandbox. The user must approve it.",
        "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}}},
]
TOOL_NAMES = [t["function"]["name"] for t in TOOLS]

CONVERSE_TOOLS = {
    "tools": [
        {
            "toolSpec": {
                "name": t["function"]["name"],
                "description": t["function"]["description"],
                "inputSchema": {"json": t["function"]["parameters"]},
            }
        }
        for t in TOOLS
    ]
}

SYSTEM = ("You are a deployment assistant working in the INSPECT stage. "
          "The user's application code is finished; you only add the deployment layer. "
          "Call exactly one tool per turn.")
USER = "The repo is cloned at /work/app. Start by looking at what is in the repo root."

FOLLOWUP = [
    {"role": "system", "content": SYSTEM},
    {"role": "user", "content": USER},
    {"role": "assistant", "content": None, "tool_calls": [
        {"id": "call_1", "type": "function",
         "function": {"name": "list_dir", "arguments": json.dumps({"path": "/work/app"})}}]},
    {"role": "tool", "tool_call_id": "call_1", "content": "package.json\nserver.js\nREADME.md"},
]

FOLLOWUP_CONVERSE = [
    {"role": "user", "content": [{"text": USER}]},
    {
        "role": "assistant",
        "content": [
            {
                "toolUse": {
                    "toolUseId": "call_1",
                    "name": "list_dir",
                    "input": {"path": "/work/app"},
                }
            }
        ],
    },
    {
        "role": "user",
        "content": [
            {
                "toolResult": {
                    "toolUseId": "call_1",
                    "content": [{"text": "package.json\nserver.js\nREADME.md"}],
                }
            }
        ],
    },
]

JSON_SYSTEM = (SYSTEM + " Reply with ONLY a JSON object of the form "
               '{"tool": "<name>", "args": {...}} and nothing else. '
               "Available tools: list_dir(path), read_file(path), ask_user(question), run_command(command).")


def extract_region_from_token(token):
    """Safely extract the AWS region scoped in a Bedrock bearer token."""
    if not token or not token.startswith("bedrock-api-key-"):
        return None
    try:
        raw_b64 = token[len("bedrock-api-key-"):]
        raw_b64 += "=" * (-len(raw_b64) % 4)
        decoded = base64.b64decode(raw_b64).decode("utf-8", errors="ignore")
        m = re.search(r'(?:%2F|/)([a-z]{2}-[a-z]+-\d)(?:%2F|/)bedrock', decoded)
        if m:
            return m.group(1)
    except Exception:
        pass
    return None


def load_env():
    """Load environment variables from .env without printing, logging, or saving secrets."""
    env_paths = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
    ]
    for env_path in env_paths:
        if os.path.isfile(env_path):
            try:
                with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().strip()
                lines = content.splitlines()
                for line in lines:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        k, v = line.split("=", 1)
                        k, v = k.strip(), v.strip().strip("\"'")
                        if k and k not in os.environ:
                            os.environ[k] = v
                # Also support a bare Bedrock API key pasted directly into .env
                if len(lines) == 1 and "=" not in lines[0] and lines[0].startswith("bedrock-api-key-"):
                    token = lines[0].strip()
                    if "AWS_BEARER_TOKEN_BEDROCK" not in os.environ:
                        os.environ["AWS_BEARER_TOKEN_BEDROCK"] = token
                    if "LLM_API_KEY" not in os.environ:
                        os.environ["LLM_API_KEY"] = token
            except Exception:
                pass
            break

    # Google AI Studio / Gemini endpoint configuration
    if "LLM_API_KEY" not in os.environ:
        if "GEMINI_API_KEY" in os.environ:
            os.environ["LLM_API_KEY"] = os.environ["GEMINI_API_KEY"]
        elif "GOOGLE_API_KEY" in os.environ:
            os.environ["LLM_API_KEY"] = os.environ["GOOGLE_API_KEY"]

    if ("GEMINI_API_KEY" in os.environ or "GOOGLE_API_KEY" in os.environ) and "LLM_BASE_URL" not in os.environ:
        os.environ["LLM_BASE_URL"] = "https://generativelanguage.googleapis.com/v1beta/openai/"

    # Normalize region names (e.g. DEFAULT-REGION or AWS_DEFAULT_REGION -> AWS_REGION)
    if "AWS_REGION" not in os.environ:
        for alt_key in ["DEFAULT-REGION", "DEFAULT_REGION", "AWS_DEFAULT_REGION"]:
            if alt_key in os.environ:
                os.environ["AWS_REGION"] = os.environ[alt_key]
                break

    # Auto-detect region directly from the Bedrock API key if still unset
    if "AWS_REGION" not in os.environ:
        token = os.environ.get("AWS_BEARER_TOKEN_BEDROCK") or os.environ.get("LLM_API_KEY")
        detected = extract_region_from_token(token)
        if detected:
            os.environ["AWS_REGION"] = detected


class Budget:
    def __init__(self, limit):
        self.limit, self.used = limit, 0

    def add(self, n):
        self.used += n
        if self.used > self.limit:
            raise RuntimeError(f"token budget exceeded ({self.used} > {self.limit}); stopping")


def call(client, budget, model, messages, tools=None):
    kwargs = dict(model=model, messages=messages, temperature=0, max_tokens=400)
    if tools:
        kwargs.update(tools=tools, tool_choice="auto")
    t0 = time.time()
    r = client.chat.completions.create(**kwargs)
    dt = time.time() - t0
    tokens = r.usage.total_tokens if r.usage else 0
    budget.add(tokens)
    return r.choices[0].message, dt, tokens


def converse(client, budget, model, messages, system=None, tool_config=None):
    kwargs = {
        "modelId": model,
        "messages": messages,
        "inferenceConfig": {"maxTokens": 400, "temperature": 0},
    }
    if system:
        kwargs["system"] = [{"text": s} if isinstance(s, str) else s for s in (system if isinstance(system, list) else [system])]
    if tool_config:
        kwargs["toolConfig"] = tool_config
    t0 = time.time()
    r = client.converse(**kwargs)
    dt = time.time() - t0
    tokens = r.get("usage", {}).get("totalTokens", 0)
    budget.add(tokens)
    return r["output"]["message"], dt, tokens


def check_tool(msg, expect_name, expect_in_path=None):
    if not msg.tool_calls:
        return False, "text reply, no tool call" if msg.content else "empty reply"
    fn = msg.tool_calls[0].function
    try:
        args = json.loads(fn.arguments or "{}")
    except json.JSONDecodeError:
        return False, "arguments are not valid JSON"
    if fn.name != expect_name:
        return False, f"called {fn.name} instead"
    if expect_in_path and expect_in_path not in str(args.get("path", "")):
        return False, f"unexpected args {args}"
    return True, ""


def get_converse_text(msg):
    if not isinstance(msg, dict):
        return ""
    texts = []
    for block in msg.get("content", []):
        if isinstance(block, dict) and "text" in block:
            texts.append(block["text"])
    return "".join(texts).strip()


def check_converse_tool(msg, expect_name, expect_in_path=None):
    if not isinstance(msg, dict):
        return False, "invalid message format"
    content = msg.get("content", [])
    tool_uses = [b["toolUse"] for b in content if isinstance(b, dict) and "toolUse" in b]
    if not tool_uses:
        text = get_converse_text(msg)
        return False, "text reply, no tool call" if text else "empty reply"
    tu = tool_uses[0]
    name = tu.get("name")
    args = tu.get("input", {})
    if name != expect_name:
        return False, f"called {name} instead"
    if expect_in_path:
        path_val = args.get("path", "") if isinstance(args, dict) else str(args)
        if expect_in_path not in str(path_val):
            return False, f"unexpected args {args}"
    return True, ""


def check_json(target):
    if isinstance(target, dict):
        text = get_converse_text(target)
    elif hasattr(target, "content"):
        text = (target.content or "").strip()
    elif isinstance(target, str):
        text = target.strip()
    else:
        text = str(target).strip()

    if text.startswith("```"):
        text = text.strip("`")
        text = text[4:] if text.lower().startswith("json") else text
    try:
        obj = json.loads(text.strip())
    except json.JSONDecodeError:
        return False, "not valid JSON"
    if not isinstance(obj, dict) or obj.get("tool") not in TOOL_NAMES or not isinstance(obj.get("args"), dict):
        return False, "wrong shape"
    return True, ""


def run_model(backend, client, budget, model, trials):
    results = {"model": model, "tests": {}, "latency": [], "tokens": 0}

    def record(name, ok, why):
        r = results["tests"].setdefault(name, {"ok": 0, "n": 0, "fails": []})
        r["n"] += 1
        r["ok"] += int(ok)
        if not ok and why not in r["fails"]:
            r["fails"].append(why)

    def attempt(name, fn):
        try:
            msg, dt, tokens = fn()
            results["latency"].append(dt)
            results["tokens"] += tokens
            return msg
        except RuntimeError:
            raise
        except Exception as e:
            err_msg = str(e)
            if "on-demand throughput" in err_msg.lower():
                print(f"  [Hint] On-demand throughput is not supported for '{model}'. "
                      f"An inference profile ID (e.g. with an 'apac.', 'us.', or 'global.' prefix like 'apac.{model}') may be needed.")
            record(name, False, f"error: {err_msg[:120]}")
            return None

    if backend == "converse":
        msg = attempt("ping", lambda: converse(client, budget, model,
                      [{"role": "user", "content": [{"text": "Reply with the word ok."}]}]))
        if msg is not None:
            record("ping", bool(get_converse_text(msg)), "empty reply")
        for _ in range(trials):
            msg = attempt("tool_first", lambda: converse(client, budget, model,
                          [{"role": "user", "content": [{"text": USER}]}],
                          system=SYSTEM, tool_config=CONVERSE_TOOLS))
            if msg is not None:
                record("tool_first", *check_converse_tool(msg, "list_dir"))
            msg = attempt("tool_followup", lambda: converse(client, budget, model,
                          FOLLOWUP_CONVERSE, system=SYSTEM, tool_config=CONVERSE_TOOLS))
            if msg is not None:
                record("tool_followup", *check_converse_tool(msg, "read_file", "package.json"))
            msg = attempt("json_fallback", lambda: converse(client, budget, model,
                          [{"role": "user", "content": [{"text": USER}]}],
                          system=JSON_SYSTEM))
            if msg is not None:
                record("json_fallback", *check_json(msg))
    else:
        msg = attempt("ping", lambda: call(client, budget, model,
                      [{"role": "user", "content": "Reply with the word ok."}]))
        if msg is not None:
            record("ping", bool(msg.content), "empty reply")
        for _ in range(trials):
            msg = attempt("tool_first", lambda: call(client, budget, model,
                          [{"role": "system", "content": SYSTEM}, {"role": "user", "content": USER}], TOOLS))
            if msg is not None:
                record("tool_first", *check_tool(msg, "list_dir"))
            msg = attempt("tool_followup", lambda: call(client, budget, model, FOLLOWUP, TOOLS))
            if msg is not None:
                record("tool_followup", *check_tool(msg, "read_file", "package.json"))
            msg = attempt("json_fallback", lambda: call(client, budget, model,
                          [{"role": "system", "content": JSON_SYSTEM}, {"role": "user", "content": USER}]))
            if msg is not None:
                record("json_fallback", *check_json(msg))

    return results


def main():
    load_env()

    ap = argparse.ArgumentParser(description="Smoke test LLM tool-calling capabilities.")
    ap.add_argument("--backend", choices=["openai", "converse"], default="openai",
                    help="inference backend: openai (default) or converse (Bedrock Converse API)")
    ap.add_argument("--models", help="comma-separated model IDs (required in converse mode)")
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--max-tokens", type=int, default=100_000, help="total token budget across the whole run")
    args = ap.parse_args()

    region = os.getenv("AWS_REGION", "us-east-1")

    if args.backend == "converse":
        if boto3 is None:
            sys.exit("boto3 is not installed. Please run: pip install -U boto3")
        ver_parts = []
        for part in boto3.__version__.split("."):
            digits = "".join(c for c in part if c.isdigit())
            if digits:
                ver_parts.append(int(digits))
        if tuple(ver_parts[:2]) < (1, 39):
            print(f"Warning: boto3 version is {boto3.__version__}. AWS_BEARER_TOKEN_BEDROCK requires boto3 >= 1.39.0. "
                  "If the token is ignored, upgrade boto3: pip install -U boto3\n")

        if not args.models:
            sys.exit("In converse mode, model listing is skipped and --models is required. E.g. --models us.amazon.nova-lite-v1:0")

        models = [m.strip() for m in args.models.split(",") if m.strip()]

        session = boto3.Session(region_name=region)
        creds = session.get_credentials()
        has_bearer = bool(os.getenv("AWS_BEARER_TOKEN_BEDROCK"))
        if not creds and not has_bearer:
            sys.exit("Authentication error: No active AWS CLI credentials or AWS_BEARER_TOKEN_BEDROCK found.")

        client = session.client("bedrock-runtime")

    else:
        # openai backend
        if OpenAI is None:
            sys.exit("openai is not installed. Please run: pip install openai")
        if os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"):
            default_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
        else:
            default_url = f"https://bedrock-runtime.{region}.amazonaws.com/openai/v1"
        base_url = os.getenv("LLM_BASE_URL", default_url)
        key = os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or os.getenv("AWS_BEARER_TOKEN_BEDROCK")
        if not key:
            sys.exit("Set LLM_API_KEY or GEMINI_API_KEY in your environment or .env file.")
        client = OpenAI(base_url=base_url, api_key=key)

        if args.models:
            models = [m.strip() for m in args.models.split(",") if m.strip()]
        else:
            try:
                available = [m.id for m in client.models.list().data]
            except Exception as e:
                sys.exit(f"Failed to list models from {base_url}: {e}\nProvide model ID(s) manually with --models.")
            models = []
            for pattern in PREFERRED:
                hit = next((m for m in available if pattern in m.lower()), None)
                if hit and hit not in models:
                    models.append(hit)
            if not models:
                print("No preferred models matched. Available IDs:")
                print("\n".join(f"  {m}" for m in available))
                sys.exit("Re-run with --models <id>[,<id>...]")

    if args.backend == "openai" and "generativelanguage.googleapis.com" in base_url:
        endpoint_desc = "Google AI Studio"
    elif args.backend == "converse":
        endpoint_desc = f"region: {region}"
    else:
        endpoint_desc = f"region: {region}" if "bedrock" in base_url else base_url

    print(f"Backend: {args.backend}  ({endpoint_desc})")
    print(f"Testing: {', '.join(models)}  (trials={args.trials}, token budget={args.max_tokens})\n")

    budget, all_results = Budget(args.max_tokens), []
    try:
        for model in models:
            print(f"-> {model}")
            all_results.append(run_model(args.backend, client, budget, model, args.trials))
    except RuntimeError as e:
        print(f"\n{e}")

    header = f"=== Summary [backend: {args.backend}, endpoint: {endpoint_desc}] ==="
    print(f"\n{header}")

    for r in all_results:
        lat = sum(r["latency"]) / len(r["latency"]) if r["latency"] else 0
        print(f"\n{r['model']}   avg latency {lat:.1f}s   tokens {r['tokens']}")
        for name, t in r["tests"].items():
            note = f"   fails: {'; '.join(t['fails'])}" if t["fails"] else ""
            print(f"  {name:<14} {t['ok']}/{t['n']}{note}")
    print(f"\nTotal tokens used: {budget.used}")
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "smoke_results.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"Saved {os.path.basename(out_path)}")


if __name__ == "__main__":
    main()
