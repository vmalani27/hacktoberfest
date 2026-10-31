export type Stage = 
  | 'INSPECT'
  | 'INTERVIEW'
  | 'PLAN'
  | 'EXECUTE'
  | 'VERIFY'
  | 'EXPORT'
  | 'FAILED'
  | 'COMPLETED';

export type ToolStatus = 
  | 'PENDING_APPROVAL'
  | 'APPROVED'
  | 'REJECTED'
  | 'EXECUTING'
  | 'COMPLETED'
  | 'FAILED';

export interface ToolCall {
  id: string;
  tool_name: string;
  arguments: Record<string, any>;
  status: ToolStatus;
  requires_approval: boolean;
  output?: string;
  error?: string;
  exit_code?: number;
  duration_ms?: number;
  created_at?: number;
}

export interface ChatMessage {
  role: 'user' | 'assistant' | 'system' | 'tool';
  content: string;
  tool_call?: ToolCall;
  timestamp?: number;
}

export interface SetupStep {
  id: string;
  label: string;
  status: 'pending' | 'running' | 'completed' | 'skipped' | 'failed';
  detail?: string;
}

export interface SetupStatusResponse {
  session_id: string;
  steps: SetupStep[];
  completed: boolean;
  error?: string;
  detected_stack?: string;
  quarantined_secrets?: string[];
}

export interface SessionState {
  session_id: string;
  stage: Stage;
  messages: ChatMessage[];
  current_tool_call?: ToolCall | null;
  repo_path: string;
  repo_url?: string;
  detected_stack?: string;
  quarantined_secrets?: string[];
  app_type?: string;
  app_port?: number;
  answers: Record<string, string>;
  exported_artifacts: Record<string, string>;
  retry_count: number;
  step_count: number;
  is_active: boolean;
}
