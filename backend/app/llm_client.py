import os
import re
import json
import asyncio
from typing import List, Dict, Any, Optional
import httpx
from app.config import settings
from app.tools import TOOL_DEFINITIONS

class BedrockClient:
    """Amazon Bedrock Converse API Client supporting Nova Pro, Claude, etc."""
    def __init__(self, model_id: Optional[str] = None, region_name: Optional[str] = None):
        import boto3
        # If AWS_BEARER_TOKEN_BEDROCK is empty, unset it so boto3 uses SigV4 credentials from ~/.aws
        if not os.getenv("AWS_BEARER_TOKEN_BEDROCK"):
            os.environ.pop("AWS_BEARER_TOKEN_BEDROCK", None)

        self.model_id = model_id or settings.BEDROCK_MODEL_ID
        self.region_name = region_name or settings.AWS_REGION
        self.session = boto3.Session(region_name=self.region_name)
        self.client = self.session.client("bedrock-runtime")

    def _converse_sync(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stage_prompt: Optional[str] = None,
        force_tool: bool = False
    ) -> Dict[str, Any]:
        # Bedrock Converse format with native toolUse and toolResult blocks
        converse_messages = []
        for m in messages:
            role = m.get("role", "user")

            # Handle tool result from step tool execution loop
            if role == "tool":
                tid = m.get("tool_call_id") or "tooluse_0"
                t_content = str(m.get("content") or "")
                tool_block = {
                    "toolResult": {
                        "toolUseId": tid,
                        "content": [{"text": t_content[:3000]}]
                    }
                }
                if converse_messages and converse_messages[-1]["role"] == "user" and isinstance(converse_messages[-1]["content"], list) and "toolResult" in converse_messages[-1]["content"][0]:
                    converse_messages[-1]["content"].append(tool_block)
                else:
                    converse_messages.append({
                        "role": "user",
                        "content": [tool_block]
                    })
                continue

            # Handle assistant tool calls
            if role == "assistant" and m.get("tool_calls"):
                blocks = []
                txt = (m.get("content") or "").strip()
                if txt:
                    blocks.append({"text": txt})
                for tc in m["tool_calls"]:
                    func = tc.get("function", {})
                    args = func.get("arguments", {})
                    if isinstance(args, str):
                        try:
                            args = json.loads(args)
                        except Exception:
                            args = {}
                    blocks.append({
                        "toolUse": {
                            "toolUseId": tc.get("id") or "tooluse_0",
                            "name": func.get("name", ""),
                            "input": args
                        }
                    })
                converse_messages.append({"role": "assistant", "content": blocks})
                continue

            content = (m.get("content") or "").strip()
            if not content:
                continue
            if converse_messages and converse_messages[-1]["role"] == role and isinstance(converse_messages[-1]["content"], list) and "text" in converse_messages[-1]["content"][-1]:
                converse_messages[-1]["content"].append({"text": content})
            else:
                converse_messages.append({"role": role, "content": [{"text": content}]})

        # Ensure first message is user
        if not converse_messages or converse_messages[0]["role"] != "user":
            converse_messages.insert(0, {
                "role": "user",
                "content": [{"text": "Inspect the repository and prepare the deployment plan."}]
            })

        kwargs: Dict[str, Any] = {
            "modelId": self.model_id,
            "messages": converse_messages,
            "inferenceConfig": {"maxTokens": 2048, "temperature": 0.1}
        }

        if stage_prompt:
            kwargs["system"] = [{"text": stage_prompt}]

        if settings.BEDROCK_GUARDRAIL_ID:
            kwargs["guardrailConfig"] = {
                "guardrailIdentifier": settings.BEDROCK_GUARDRAIL_ID,
                "guardrailVersion": settings.BEDROCK_GUARDRAIL_VERSION,
                "trace": "enabled"
            }

        if tools:
            tool_cfg = {
                "tools": [
                    {
                        "toolSpec": {
                            "name": t["function"]["name"],
                            "description": t["function"]["description"],
                            "inputSchema": {"json": t["function"]["parameters"]},
                        }
                    }
                    for t in tools
                ]
            }
            if force_tool:
                tool_cfg["toolChoice"] = {"any": {}}
            kwargs["toolConfig"] = tool_cfg

        response = self.client.converse(**kwargs)
        output_msg = response.get("output", {}).get("message", {})
        raw_blocks = output_msg.get("content", [])

        # Extract text content and strip internal reasoning tags
        raw_text = "".join(b["text"] for b in raw_blocks if "text" in b)
        clean_text = re.sub(r"<thinking>.*?</thinking>", "", raw_text, flags=re.DOTALL).strip()

        # Extract tool calls
        tool_calls = []
        for b in raw_blocks:
            if "toolUse" in b:
                tu = b["toolUse"]
                tool_calls.append({
                    "id": tu.get("toolUseId", ""),
                    "type": "function",
                    "function": {
                        "name": tu.get("name", ""),
                        "arguments": tu.get("input", {})
                    }
                })

        return {
            "role": "assistant",
            "content": clean_text,
            "tool_calls": tool_calls
        }

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stage_prompt: Optional[str] = None,
        force_tool: bool = False
    ) -> Dict[str, Any]:
        try:
            return await asyncio.to_thread(self._converse_sync, messages, tools, stage_prompt, force_tool)
        except Exception as e:
            return {
                "role": "assistant",
                "content": f"[Bedrock Error]: {str(e)}",
                "tool_calls": []
            }


class OpenAICompatibleClient:
    """Standard OpenAI-compatible API client."""
    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None, api_key: Optional[str] = None):
        self.base_url = (base_url or settings.OPENAI_BASE_URL).rstrip("/")
        self.model = model or settings.OPENAI_MODEL
        self.api_key = api_key or settings.OPENAI_API_KEY

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stage_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        payload_messages = []
        if stage_prompt:
            payload_messages.append({"role": "system", "content": stage_prompt})

        for m in messages:
            payload_messages.append({
                "role": m.get("role", "user"),
                "content": m.get("content", "")
            })

        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": payload_messages,
            "temperature": 0.2
        }

        if tools:
            payload["tools"] = tools

        headers = {
            "Content-Type": "application/json"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = f"{self.base_url}/chat/completions"
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=90.0) as client:
                    res = await client.post(url, json=payload, headers=headers)
                    if res.status_code == 200:
                        data = res.json()
                        choices = data.get("choices", [])
                        if choices:
                            msg = choices[0].get("message", {})
                            return {
                                "role": "assistant",
                                "content": msg.get("content", "") or "",
                                "tool_calls": msg.get("tool_calls", [])
                            }
                        return {"role": "assistant", "content": "", "tool_calls": []}
                    elif res.status_code == 429 and attempt < max_retries - 1:
                        wait_sec = 6.0
                        retry_header = res.headers.get("retry-after")
                        if retry_header:
                            try:
                                wait_sec = float(retry_header) + 1.0
                            except Exception:
                                pass
                        else:
                            match = re.search(r"try again in (\d+(?:\.\d+)?)s", res.text)
                            if match:
                                wait_sec = float(match.group(1)) + 1.5
                            else:
                                wait_sec = 8.0 + (attempt * 4.0)
                        await asyncio.sleep(wait_sec)
                        continue
                    else:
                        return {
                            "role": "assistant",
                            "content": f"[LLM API Error {res.status_code}]: {res.text}",
                            "tool_calls": []
                        }
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(2.0)
                    continue
                return {
                    "role": "assistant",
                    "content": f"LLM error: {str(e)}",
                    "tool_calls": []
                }


class UnifiedLLMClient:
    """Unified client that routes between configured LLM providers."""
    def __init__(self):
        provider = settings.LLM_PROVIDER.lower().strip()
        if provider == "bedrock":
            self.backend = BedrockClient()
        else:
            self.backend = OpenAICompatibleClient()

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        stage_prompt: Optional[str] = None,
        force_tool: bool = False
    ) -> Dict[str, Any]:
        return await self.backend.chat(messages, tools, stage_prompt, force_tool)

llm_client = UnifiedLLMClient()
