import React from 'react';
import { 
  Terminal as TerminalIcon, 
  FileText, 
  Download, 
  Trash2, 
  RotateCcw,
  ExternalLink,
  ShieldCheck,
  FolderGit2
} from 'lucide-react';

interface HeaderProps {
  viewMode?: 'START' | 'SETTING_UP' | 'CHAT';
  repoName?: string;
  repoUrl?: string;
  detectedStack?: string;
  appPort?: number;
  quarantinedCount?: number;
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
  repoUrl,
  detectedStack,
  appPort,
  quarantinedCount = 0,
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
    <header className="h-[44px] shrink-0 w-full border-b border-white/[0.08] bg-[#090a0f] px-4 flex items-center justify-between z-50 select-none">
      {/* Left: Brand & Status */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2">
          <span className="font-bold text-sm tracking-tight text-white">
            Deploy Assistant
          </span>
          <span className="text-zinc-600 font-mono text-xs">/</span>
        </div>

        {viewMode === 'START' && (
          <div className="flex items-center gap-2">
            <div className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            <span className="text-[11px] font-mono text-slate-400">
              sandbox ready
            </span>
          </div>
        )}

        {viewMode === 'SETTING_UP' && (
          <div className="flex items-center gap-2">
            <span className="inline-block h-2 w-2 animate-spin rounded-full border border-amber-400 border-t-transparent" />
            <span className="text-[11px] font-mono text-amber-300">
              provisioning {repoName || 'workspace'}...
            </span>
          </div>
        )}

        {viewMode === 'CHAT' && (
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
              </span>
              <span className="text-[11px] font-mono text-emerald-300 truncate max-w-[140px]">
                {repoName || 'workspace'}
              </span>
            </div>

            {detectedStack && (
              <span className="hidden sm:inline-flex text-[11px] font-mono text-slate-400 border border-white/[0.08] bg-[#12151c] px-2 py-0.5 rounded">
                {detectedStack}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-2">
        {viewMode === 'START' && (
          <div className="flex items-center gap-2 font-mono text-[11px] text-slate-500">
            <span className="flex items-center gap-1">
              <ShieldCheck className="w-3.5 h-3.5 text-slate-400" />
              <span>dind isolated</span>
            </span>
            <span>•</span>
            <span>facts-ledger v1</span>
          </div>
        )}

        {viewMode === 'CHAT' && (
          <>
            {/* Live Web Preview Link */}
            {openPorts && openPorts.length > 0 && (
              <div className="flex items-center gap-1.5 mr-1">
                {openPorts.map((p) => (
                  <a
                    key={p.port}
                    href={p.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 rounded border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-1 text-xs font-mono text-emerald-400 hover:bg-emerald-500/20 hover:text-emerald-300 transition-colors"
                    title={`Port ${p.port} listening. Click to open preview.`}
                  >
                    <span className="relative flex h-1.5 w-1.5">
                      <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                      <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-500" />
                    </span>
                    <span>Preview :{p.port}</span>
                    <ExternalLink className="w-3 h-3 opacity-70" />
                  </a>
                ))}
              </div>
            )}

            {/* Terminal Toggle */}
            {onToggleTerminal && (
              <button
                type="button"
                onClick={onToggleTerminal}
                className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-mono transition-colors cursor-pointer ${
                  showTerminal
                    ? 'border border-sky-500/40 bg-sky-500/15 text-sky-200'
                    : 'border border-white/[0.08] bg-[#161a24]/80 hover:bg-[#1f2533] text-slate-300 hover:text-white'
                }`}
                title="Toggle interactive container terminal"
              >
                <TerminalIcon className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Terminal</span>
              </button>
            )}

            {/* Playbook / Files Drawer */}
            {onToggleFiles && (
              <button
                type="button"
                onClick={onToggleFiles}
                className="flex items-center gap-1.5 rounded border border-white/[0.08] bg-[#161a24]/80 hover:bg-[#1f2533] text-slate-300 hover:text-white px-2.5 py-1 text-xs font-mono transition-colors cursor-pointer"
                title="Inspect generated Playbook and container manifests"
              >
                <FileText className="w-3.5 h-3.5 text-slate-400" />
                <span>Playbook ({filesCount})</span>
              </button>
            )}

            {/* Teardown / Destroy Session */}
            {onCloseWorkspace && (
              <button
                type="button"
                onClick={onCloseWorkspace}
                className="flex items-center gap-1.5 rounded border border-red-500/20 bg-red-500/10 hover:bg-red-500/20 text-red-400 px-2.5 py-1 text-xs font-mono transition-colors cursor-pointer ml-1"
                title="Destroy sandbox session and purge container files"
              >
                <Trash2 className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Destroy Session</span>
              </button>
            )}
          </>
        )}
      </div>
    </header>
  );
};
