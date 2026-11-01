import React, { useState } from 'react';
import { ChevronDown, ChevronUp, Check, Copy, CheckCheck } from 'lucide-react';
import { ToolCall } from '../types';

interface ApprovalCardProps {
  toolCall: ToolCall;
  onApprove: (toolCallId: string, modifiedArgs?: Record<string, any>) => void;
  onReject: (toolCallId: string, feedback?: string) => void;
  loading: boolean;
}

export const ApprovalCard: React.FC<ApprovalCardProps> = ({
  toolCall,
  onApprove,
  onReject,
  loading,
}) => {
  const isWrite = toolCall.tool_name === 'write_file';
  const [expanded, setExpanded] = useState(true);
  const [copied, setCopied] = useState(false);

  const filePath = toolCall.arguments.file_path || 'Configuration File';
  const fileContent = toolCall.arguments.content || '';
  const command = toolCall.arguments.command || '';

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(isWrite ? fileContent : command);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="my-3 rounded-xl border border-white/[0.08] bg-[#111318] overflow-hidden shadow-sm font-mono text-xs select-none">
      <div className="p-3.5 flex items-center justify-between border-b border-white/[0.08] bg-[#151922]">
        <div className="space-y-0.5">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-white tracking-tight">
              {isWrite ? filePath : command}
            </span>
            <span className="text-[10px] font-mono border border-white/[0.08] bg-[#1e2433] px-1.5 py-0.5 rounded text-slate-300">
              {isWrite ? 'new file' : 'sandbox command'}
            </span>
          </div>
          <p className="text-[11px] text-slate-500 font-sans">
            {isWrite
              ? 'Review proposed container manifest before writing to workspace.'
              : 'Requires human approval before executing inside sandbox container.'}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {isWrite && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="px-2 py-1 text-xs text-slate-400 hover:text-white flex items-center gap-1 rounded hover:bg-white/[0.04] transition-colors cursor-pointer"
            >
              <span>{expanded ? 'Hide' : 'View'}</span>
              {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          )}

          <button
            onClick={() => onReject(toolCall.id)}
            disabled={loading}
            className="px-2.5 py-1 text-xs text-slate-400 hover:text-white hover:bg-white/[0.04] rounded transition-colors cursor-pointer disabled:opacity-50"
          >
            Skip
          </button>

          <button
            onClick={() => onApprove(toolCall.id)}
            disabled={loading}
            className="px-3 py-1 bg-zinc-100 hover:bg-white text-zinc-950 font-medium rounded transition-colors flex items-center gap-1.5 cursor-pointer disabled:opacity-50"
          >
            <Check className="w-3.5 h-3.5" />
            <span>{isWrite ? 'Apply' : 'Run in Sandbox'}</span>
          </button>
        </div>
      </div>

      {isWrite && expanded && (
        <div className="relative group bg-[#090a0f] p-3.5 border-t border-white/[0.04]">
          <button
            onClick={handleCopy}
            className="absolute top-2.5 right-2.5 px-2 py-1 rounded bg-[#181d28] hover:bg-[#202736] border border-white/[0.08] text-slate-400 hover:text-white transition-colors flex items-center gap-1 text-[10px]"
            title="Copy content"
          >
            {copied ? <CheckCheck className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
          <pre className="font-mono text-xs text-slate-300 max-h-60 overflow-y-auto leading-relaxed selection:bg-slate-700/50">
            {fileContent}
          </pre>
        </div>
      )}
    </div>
  );
};
