from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import time

class StageEnum(str, Enum):
    INSPECT = "INSPECT"
    INTERVIEW = "INTERVIEW"
    PLAN = "PLAN"
    EXECUTE = "EXECUTE"
    VERIFY = "VERIFY"
    EXPORT = "EXPORT"
    FAILED = "FAILED"
    COMPLETED = "COMPLETED"

class ToolCallStatus(str, Enum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class ToolCall(BaseModel):
    id: str
    tool_name: str
    arguments: Dict[str, Any]
    status: ToolCallStatus = ToolCallStatus.PENDING_APPROVAL
    requires_approval: bool = True
    output: Optional[str] = None
    error: Optional[str] = None
    exit_code: Optional[int] = None
    duration_ms: Optional[float] = None
    created_at: float = Field(default_factory=time.time)

class InterviewAnswer(BaseModel):
    question_id: str
    answer: str

class UserMessageRequest(BaseModel):
    message: str

class ChatMessage(BaseModel):
    role: str # user, assistant, system, tool
    content: str
    tool_call: Optional[ToolCall] = None
    timestamp: float = Field(default_factory=time.time)

class SessionInitRequest(BaseModel):
    repo_url: Optional[str] = None
    local_path: Optional[str] = None
    session_id: Optional[str] = None

class ApprovalActionRequest(BaseModel):
    tool_call_id: str
    approved: bool
    modified_arguments: Optional[Dict[str, Any]] = None
    feedback: Optional[str] = None

class SetupStep(BaseModel):
    id: str
    label: str
    status: str = "pending" # pending, running, completed, skipped, failed
    detail: Optional[str] = None

class SetupStatusResponse(BaseModel):
    session_id: str
    steps: List[SetupStep]
    completed: bool
    error: Optional[str] = None
    detected_stack: Optional[str] = None
    quarantined_secrets: List[str] = []

class LedgerEntry(BaseModel):
    category: str # "verified", "declared", "assumed"
    fact: str
    evidence: str
    timestamp: float = Field(default_factory=time.time)

class SessionState(BaseModel):
    session_id: str
    stage: StageEnum = StageEnum.INSPECT
    messages: List[ChatMessage] = []
    current_tool_call: Optional[ToolCall] = None
    repo_path: str = ""
    repo_url: Optional[str] = None
    detected_stack: Optional[str] = None
    quarantined_secrets: List[str] = []
    app_type: Optional[str] = None
    app_port: Optional[int] = None
    answers: Dict[str, str] = {}
    facts_ledger: List[LedgerEntry] = []
    exported_artifacts: Dict[str, str] = {}
    retry_count: int = 0
    step_count: int = 0
    is_active: bool = True
    created_at: float = Field(default_factory=time.time)
    last_activity: float = Field(default_factory=time.time)
