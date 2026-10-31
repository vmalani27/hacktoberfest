import React, { useState } from 'react';
import { 
  GitBranch, 
  ExternalLink, 
  ShieldCheck, 
  Server, 
  Terminal, 
  FileCode, 
  CheckCircle2, 
  ChevronDown, 
  ChevronUp, 
  Copy, 
  Check, 
  Cpu, 
  Lock,
  Layers,
  Sparkles
} from 'lucide-react';
import { SessionState } from '../types';

interface WorkspaceCardProps {
  session?: SessionState | null;
  onToggleTerminal?: () => void;
  onToggleFiles?: () => void;
  isTerminalOpen?: boolean;
}

export const WorkspaceCard: React.FC<WorkspaceCardProps> = ({
  session,
  onToggleTerminal,
  onToggleFiles,
  isTerminalOpen = false,
}) => {
  const [expanded, setExpanded] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState(false);

  if (!session) return null;

  const repoName = session.repo_url 
    ? session.repo_url.replace(/\/+$/, '').split('/').slice(-2).join('/') 
    : 'Local Workspace';

  const artifactsCount = Object.keys(session.exported_artifacts || {}).length;
  const quarantinedCount = session.quarantined_secrets?.length || 0;
  const isStateless = session.answers?.db_type?.toLowerCase().includes('stateless');

  const handleCopyUrl = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (session.repo_url) {
      navigator.clipboard.writeText(session.repo_url);
      setCopiedUrl(true);
      setTimeout(() => setCopiedUrl(false), 2000);
    }
  };

  return (
    <div className="bg-slate-900/90 border border-slate-800/90 rounded-2xl overflow-hidden shadow-xl backdrop-blur-md transition-all">
      {/* Top Banner Row */}
      <div className="px-5 py-4 flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/60 bg-gradient-to-r from-indigo-950/30 via-slate-900/40 to-slate-950/60">
        <div className="flex items-center gap-3 min-w-0">
          <div className="h-10 w-10 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-600/20 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0 shadow-sm">
            <Cpu className="w-5 h-5 text-indigo-400" />
          </div>

          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-sm text-slate-100 truncate tracking-tight">
                {repoName}
              </span>
              {session.repo_url && (
                <a
                  href={session.repo_url}
                  target="_blank"
                  rel="noreferrer"
                  className="text-slate-400 hover:text-indigo-400 transition-colors p-0.5"
                  title="Open on GitHub"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              )}
              {session.repo_url && (
                <button
                  onClick={handleCopyUrl}
                  className="text-slate-400 hover:text-slate-200 transition-colors p-0.5"
                  title="Copy Git URL"
                >
                  {copiedUrl ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
              )}
            </div>

            <div className="flex items-center gap-2 text-[11px] text-slate-400 mt-0.5">
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-emerald-400 font-medium">Sandbox Ready</span>
              </span>
              <span className="text-slate-600">•</span>
              <span className="text-slate-400">Isolated Runtime</span>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2">
          {onToggleTerminal && (
            <button
              onClick={onToggleTerminal}
              className={`px-3 py-1.5 rounded-xl text-xs font-medium border flex items-center gap-1.5 transition-all ${
                isTerminalOpen
                  ? 'bg-indigo-600/20 border-indigo-500/50 text-indigo-300 shadow-sm'
                  : 'bg-slate-800/80 hover:bg-slate-800 border-slate-700/80 text-slate-300'
              }`}
            >
              <Terminal className="w-3.5 h-3.5" />
              <span>Terminal</span>
            </button>
          )}

          {onToggleFiles && (
            <button
              onClick={onToggleFiles}
              className="px-3 py-1.5 rounded-xl text-xs font-medium bg-slate-800/80 hover:bg-slate-800 border border-slate-700/80 text-slate-300 flex items-center gap-1.5 transition-all"
            >
              <FileCode className="w-3.5 h-3.5 text-indigo-400" />
              <span>Files</span>
              <span className="ml-0.5 px-1.5 py-0.2 bg-indigo-500/20 text-indigo-300 rounded-full text-[10px] font-semibold">
                {artifactsCount}
              </span>
            </button>
          )}

          <button
            onClick={() => setExpanded(!expanded)}
            className="p-1.5 rounded-xl hover:bg-slate-800 text-slate-400 hover:text-slate-200 transition-colors"
            title={expanded ? 'Hide details' : 'Show details'}
          >
            {expanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Interactive Metadata Chips Row */}
      <div className="px-5 py-3 bg-slate-950/40 flex flex-wrap items-center gap-2 text-xs">
        {/* Framework Stack */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 font-medium">
          <Layers className="w-3.5 h-3.5 text-indigo-400" />
          <span>{session.detected_stack || 'Detecting stack...'}</span>
        </div>

        {/* Port */}
        {session.app_port && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-cyan-500/10 border border-cyan-500/20 text-cyan-300 font-medium">
            <Server className="w-3.5 h-3.5 text-cyan-400" />
            <span>Port {session.app_port}</span>
          </div>
        )}

        {/* Architecture / Database */}
        {session.answers?.db_type && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-purple-500/10 border border-purple-500/20 text-purple-300 font-medium">
            <Sparkles className="w-3.5 h-3.5 text-purple-400" />
            <span>{session.answers.db_type}</span>
          </div>
        )}

        {/* Privacy Boundary Badge */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 font-medium ml-auto">
          <Lock className="w-3.5 h-3.5 text-emerald-400" />
          <span>{quarantinedCount === 0 ? '0 Secrets Exposed' : `${quarantinedCount} Secrets Quarantined`}</span>
        </div>
      </div>

      {/* Collapsible Inspector Drawer */}
      {expanded && (
        <div className="px-5 py-4 border-t border-slate-800/70 bg-slate-950/80 text-xs text-slate-300 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            <div className="p-3 rounded-xl bg-slate-900 border border-slate-800/80">
              <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
                Sandbox Mode
              </div>
              <div className="text-slate-200 font-medium">Docker-in-Docker (dind)</div>
              <div className="text-[11px] text-slate-500 mt-0.5">Zero host filesystem mounts</div>
            </div>

            <div className="p-3 rounded-xl bg-slate-900 border border-slate-800/80">
              <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
                Artifacts Status
              </div>
              <div className="text-slate-200 font-medium">
                {artifactsCount === 0 ? 'Generating...' : `${artifactsCount} Created`}
              </div>
              <div className="text-[11px] text-slate-500 mt-0.5">Dockerfile, Compose, .env</div>
            </div>

            <div className="p-3 rounded-xl bg-slate-900 border border-slate-800/80">
              <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
                Safety Guarantee
              </div>
              <div className="text-emerald-400 font-medium flex items-center gap-1">
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>Stop Rule Active</span>
              </div>
              <div className="text-[11px] text-slate-500 mt-0.5">Halts on app code errors</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
