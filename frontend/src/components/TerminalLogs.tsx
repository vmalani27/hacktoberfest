import React from 'react';
import { Terminal as TerminalIcon, CheckCircle, XCircle } from 'lucide-react';
import { ToolCall } from '../types';

interface TerminalLogsProps {
  toolCalls: ToolCall[];
}

export const TerminalLogs: React.FC<TerminalLogsProps> = ({ toolCalls }) => {
  const executedCalls = toolCalls.filter(
    (tc) => tc.tool_name === 'run_command' && (tc.output || tc.error || tc.exit_code !== undefined)
  );

  return (
    <div className="flex flex-col h-full bg-slate-950 font-mono">
      <div className="px-4 py-2 border-b border-slate-800 bg-slate-900/90 flex items-center justify-between text-xs text-slate-400">
        <div className="flex items-center gap-2">
          <TerminalIcon className="w-3.5 h-3.5 text-indigo-400" />
          <span className="font-semibold text-slate-200">Sandbox Execution Logs</span>
        </div>
        <span className="text-[11px] text-slate-500">
          {executedCalls.length} commands logged
        </span>
      </div>

      <div className="flex-1 p-3 overflow-y-auto space-y-4 text-xs">
        {executedCalls.length === 0 ? (
          <div className="h-full flex flex-col items-center justify-center text-slate-600">
            <TerminalIcon className="w-8 h-8 mb-2 stroke-1" />
            <p className="text-[11px]">No commands executed in the sandbox yet.</p>
          </div>
        ) : (
          executedCalls.map((tc) => (
            <div
              key={tc.id}
              className="rounded border border-slate-800 bg-slate-900/50 p-2.5 space-y-2"
            >
              <div className="flex items-center justify-between text-[11px]">
                <div className="flex items-center gap-1.5 text-slate-300">
                  <span className="text-indigo-400 font-bold">$</span>
                  <span className="font-semibold">{tc.arguments.command}</span>
                </div>
                <div className="flex items-center gap-2">
                  {tc.duration_ms !== undefined && (
                    <span className="text-slate-500">{tc.duration_ms}ms</span>
                  )}
                  {tc.exit_code === 0 ? (
                    <span className="flex items-center gap-1 text-emerald-400 text-[10px] bg-emerald-950/60 px-1.5 py-0.5 rounded border border-emerald-800/40">
                      <CheckCircle className="w-3 h-3" /> exit 0
                    </span>
                  ) : (
                    <span className="flex items-center gap-1 text-rose-400 text-[10px] bg-rose-950/60 px-1.5 py-0.5 rounded border border-rose-800/40">
                      <XCircle className="w-3 h-3" /> exit {tc.exit_code ?? 1}
                    </span>
                  )}
                </div>
              </div>

              {tc.output && (
                <pre className="text-slate-300 whitespace-pre-wrap bg-black/40 p-2 rounded text-[11px] max-h-36 overflow-y-auto">
                  {tc.output}
                </pre>
              )}

              {tc.error && (
                <pre className="text-rose-400 whitespace-pre-wrap bg-rose-950/30 border border-rose-900/50 p-2 rounded text-[11px] max-h-36 overflow-y-auto">
                  {tc.error}
                </pre>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};
