import React from 'react';
import { 
  Bot, 
  FolderGit2, 
  FileText, 
  Terminal, 
  Download, 
  RotateCcw,
  ExternalLink,
  Globe,
  Trash2,
  ShieldCheck,
  Cpu
} from 'lucide-react';

interface HeaderProps {
  viewMode?: 'START' | 'SETTING_UP' | 'CHAT';
  repoName?: string;
  detectedStack?: string;
  filesCount?: number;
  openPorts?: { port: number; url: string; label: string }[];
  showTerminal?: boolean;
  onToggleTerminal?: () => void;
  onToggleFiles?: () => void;
  onDownload?: () => void;
  onCloseWorkspace?: () => void;
  onReset?: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  viewMode = 'CHAT',
  repoName,
  detectedStack,
  filesCount = 0,
  openPorts = [],
  showTerminal = false,
  onToggleTerminal,
  onToggleFiles,
  onDownload,
  onCloseWorkspace,
  onReset,
}) => {
  return (
    <header className="border-b border-slate-800/80 bg-slate-900/70 backdrop-blur-xl px-4 md:px-6 py-2.5 flex items-center justify-between sticky top-0 z-30 shadow-sm shrink-0">
      {/* Left branding & Repo indicator */}
      <div className="flex items-center gap-3">
        <div className="relative group">
          <div className="absolute -inset-0.5 bg-gradient-to-r from-indigo-500 to-purple-500 rounded-xl blur opacity-30 group-hover:opacity-60 transition duration-300" />
          <div className="relative h-9 w-9 rounded-xl bg-slate-900 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shadow-inner">
            <Bot className="w-5 h-5 text-indigo-400 group-hover:scale-110 transition-transform" />
          </div>
        </div>

        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-semibold text-slate-100 text-sm tracking-tight">Deploy Assistant</h1>
            
            {viewMode === 'START' && (
              <span className="flex items-center gap-1.5 text-[10px] font-medium text-emerald-400 bg-emerald-950/60 border border-emerald-800/40 px-2 py-0.5 rounded-full">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Sandbox Ready
              </span>
            )}

            {viewMode === 'SETTING_UP' && (
              <span className="flex items-center gap-1.5 text-[10px] font-medium text-amber-300 bg-amber-950/60 border border-amber-800/40 px-2 py-0.5 rounded-full">
                <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-spin" />
                Provisioning
              </span>
            )}

            {viewMode === 'CHAT' && (
              <span className="flex items-center gap-1.5 text-[10px] font-medium text-emerald-400 bg-emerald-950/60 border border-emerald-800/40 px-2 py-0.5 rounded-full">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Active
              </span>
            )}

            {detectedStack && viewMode === 'CHAT' && (
              <span className="hidden sm:inline-flex text-[10px] font-medium text-indigo-300 bg-indigo-950/50 border border-indigo-800/40 px-2 py-0.5 rounded-full">
                {detectedStack}
              </span>
            )}
          </div>

          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            {viewMode === 'START' ? (
              <span className="text-[11px] text-slate-400">
                Containerize, run, and verify repositories in Docker sandbox
              </span>
            ) : (
              <>
                <FolderGit2 className="w-3.5 h-3.5 text-indigo-400 shrink-0" />
                <span className="font-mono text-[11px] text-slate-300 truncate max-w-xs">
                  {repoName || 'workspace'}
                </span>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-2">
        {viewMode === 'START' && (
          <div className="flex items-center gap-2">
            <span className="hidden md:flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-medium text-slate-400 bg-slate-800/50 border border-slate-800 rounded-md">
              <ShieldCheck className="w-3.5 h-3.5 text-indigo-400" />
              Isolated DinD
            </span>
            <span className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-medium text-slate-400 bg-slate-800/50 border border-slate-800 rounded-md">
              <Cpu className="w-3.5 h-3.5 text-purple-400" />
              Bedrock Nova Pro
            </span>
          </div>
        )}

        {viewMode === 'CHAT' && (
          <>
            {/* Live App Preview Link when port detected */}
            {openPorts && openPorts.length > 0 && (
              <a
                href={openPorts[0].url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-1.5 px-3 py-1.5 bg-gradient-to-r from-emerald-600 to-teal-500 hover:from-emerald-500 hover:to-teal-400 text-white text-xs font-semibold rounded-lg shadow-md shadow-emerald-600/30 transition-all active:scale-95 animate-pulse"
                title={`Open live app listening on port ${openPorts[0].port}`}
              >
                <Globe className="w-3.5 h-3.5" />
                <span>Open App ({openPorts[0].port})</span>
                <ExternalLink className="w-3 h-3 ml-0.5 opacity-80" />
              </a>
            )}

            {onToggleTerminal && (
              <button
                onClick={onToggleTerminal}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-lg border transition-all active:scale-95 ${
                  showTerminal
                    ? 'bg-indigo-600 text-white border-indigo-500 shadow-md shadow-indigo-600/20'
                    : 'bg-slate-800/80 hover:bg-slate-700 text-slate-300 border-slate-700/80 hover:border-slate-600'
                }`}
                title="Toggle interactive terminal view"
              >
                <Terminal className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Terminal</span>
              </button>
            )}

            {filesCount > 0 && onToggleFiles && (
              <button
                onClick={onToggleFiles}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800/80 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg border border-slate-700/80 transition-all active:scale-95 shadow-sm"
                title="Inspect generated deployment files"
              >
                <FileText className="w-3.5 h-3.5 text-indigo-400" />
                <span>Files ({filesCount})</span>
              </button>
            )}

            {onDownload && (
              <button
                onClick={onDownload}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800/80 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg border border-slate-700/80 transition-all active:scale-95 shadow-sm"
                title="Download verified files and runbook bundle"
              >
                <Download className="w-3.5 h-3.5 text-emerald-400" />
                <span className="hidden sm:inline">Download</span>
              </button>
            )}

            {onCloseWorkspace && (
              <button
                onClick={onCloseWorkspace}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-rose-950/40 hover:bg-rose-900/50 text-rose-300 hover:text-white text-xs font-medium rounded-lg border border-rose-800/50 transition-all active:scale-95 shadow-sm"
                title="Close session and delete temporary sandbox"
              >
                <Trash2 className="w-3.5 h-3.5 text-rose-400" />
                <span className="hidden sm:inline">Close</span>
              </button>
            )}

            {onReset && (
              <button
                onClick={onReset}
                title="Restart Conversation"
                className="p-1.5 text-slate-400 hover:text-slate-200 hover:bg-slate-800/80 rounded-lg border border-transparent hover:border-slate-700/60 transition-all active:scale-95"
              >
                <RotateCcw className="w-4 h-4" />
              </button>
            )}
          </>
        )}
      </div>
    </header>
  );
};
