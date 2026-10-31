import React, { useState } from 'react';
import { FileCode, Play, ChevronDown, ChevronUp, Check, Copy, CheckCheck } from 'lucide-react';
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
    <div className="my-3.5 rounded-2xl border border-indigo-500/30 bg-gradient-to-b from-slate-900/90 to-slate-950/90 shadow-xl shadow-black/40 overflow-hidden transition-all duration-200">
      <div className="p-4 flex items-center justify-between border-b border-slate-800/80 bg-slate-900/40">
        <div className="flex items-center gap-3">
          <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shadow-inner">
            {isWrite ? <FileCode className="w-4 h-4" /> : <Play className="w-4 h-4" />}
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xs font-semibold text-slate-100 tracking-tight">
                {isWrite ? filePath : command}
              </span>
              <span className="text-[10px] font-mono text-indigo-400 bg-indigo-950/60 border border-indigo-800/40 px-1.5 py-0.5 rounded">
                {isWrite ? 'new file' : 'sandbox command'}
              </span>
            </div>
            <p className="text-[11px] text-slate-400 mt-0.5">
              {isWrite
                ? 'Review the proposed configuration before saving to workspace'
                : 'Execute this command inside the isolated sandbox'}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isWrite && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="px-2.5 py-1 text-xs text-slate-400 hover:text-slate-200 flex items-center gap-1 rounded-lg hover:bg-slate-800/60 transition"
            >
              <span>{expanded ? 'Collapse' : 'Preview'}</span>
              {expanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
            </button>
          )}

          <button
            onClick={() => onReject(toolCall.id)}
            disabled={loading}
            className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 rounded-lg transition"
          >
            Skip
          </button>

          <button
            onClick={() => onApprove(toolCall.id)}
            disabled={loading}
            className="px-4 py-1.5 bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 active:scale-95 text-white text-xs font-medium rounded-lg shadow-lg shadow-indigo-600/30 transition-all flex items-center gap-1.5"
          >
            <Check className="w-3.5 h-3.5" />
            <span>{isWrite ? 'Apply File' : 'Run in Sandbox'}</span>
          </button>
        </div>
      </div>

      {isWrite && expanded && (
        <div className="relative group bg-[#090d16] p-3.5">
          <button
            onClick={handleCopy}
            className="absolute top-3 right-3 p-1.5 rounded-md bg-slate-800/80 hover:bg-slate-700 text-slate-400 hover:text-slate-200 transition opacity-0 group-hover:opacity-100 flex items-center gap-1 text-[11px]"
            title="Copy content"
          >
            {copied ? <CheckCheck className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
            <span>{copied ? 'Copied' : 'Copy'}</span>
          </button>
          <pre className="font-mono text-xs text-slate-300 max-h-56 overflow-y-auto leading-relaxed selection:bg-indigo-500/30">
            {fileContent}
          </pre>
        </div>
      )}
    </div>
  );
};
