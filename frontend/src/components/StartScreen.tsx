import React, { useState } from 'react';
import { AlertCircle } from 'lucide-react';

interface StartScreenProps {
  onStartSession: (repoUrl: string, localPath?: string) => void;
  loading: boolean;
  error?: string | null;
}

export const StartScreen: React.FC<StartScreenProps> = ({
  onStartSession,
  loading,
  error: externalError,
}) => {
  const [repoUrl, setRepoUrl] = useState('');
  const [inputError, setInputError] = useState<string | null>(null);

  const validateUrl = (url: string): string | null => {
    const trimmed = url.trim();
    if (!trimmed) return 'Please enter a repository URL.';
    if (trimmed.startsWith('git@')) {
      return 'SSH URLs require private keys. Please use a public HTTPS repository URL.';
    }
    if (!trimmed.startsWith('https://')) {
      return 'Only HTTPS repository URLs are supported.';
    }
    try {
      const parsed = new URL(trimmed);
      if (parsed.username || parsed.password) {
        return 'Do not include credentials in the repository URL.';
      }
      const parts = parsed.pathname.replace(/^\/|\/$/g, '').replace(/\.git$/, '').split('/');
      if (parts.length < 2 || !parts[0] || !parts[1]) {
        return 'Enter a valid repository path (e.g. https://github.com/owner/repo)';
      }
    } catch {
      return 'Please enter a valid HTTPS URL.';
    }
    return null;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const err = validateUrl(repoUrl);
    if (err) {
      setInputError(err);
      return;
    }
    setInputError(null);
    onStartSession(repoUrl.trim());
  };

  const displayError = inputError || externalError;

  return (
    <div className="flex-1 flex flex-col justify-start items-center px-4 sm:px-6 py-12 bg-[#090a0f] text-slate-100 overflow-y-auto select-none">
      <div className="w-full max-w-3xl space-y-6">
        
        {/* Title Header */}
        <div>
          <h1 className="text-2xl font-bold text-white tracking-tight">
            Repository Deployment
          </h1>
          <p className="text-xs text-[#94a3b8] mt-1 font-mono">
            Inspect source code, generate container configurations, and verify execution in an isolated Docker sandbox.
          </p>
        </div>

        {/* Input Card */}
        <div className="bg-[#111318] border border-white/[0.08] rounded-xl p-5 shadow-sm space-y-3">
          <div className="flex items-center justify-between text-xs">
            <span className="font-mono text-xs font-semibold uppercase tracking-wider text-slate-400">
              Git Repository URL
            </span>
            <span className="font-mono text-[11px] text-slate-500">
              HTTPS Public Repositories
            </span>
          </div>

          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="flex flex-col sm:flex-row items-center gap-2">
              <div className="relative flex-1 w-full">
                <input
                  id="repo-input"
                  type="text"
                  value={repoUrl}
                  onChange={(e) => {
                    setRepoUrl(e.target.value);
                    if (inputError) setInputError(null);
                  }}
                  placeholder="https://github.com/owner/repository"
                  disabled={loading}
                  autoFocus
                  spellCheck={false}
                  autoComplete="off"
                  className="w-full bg-[#0c0e14] border border-white/[0.08] hover:border-white/[0.14] focus:border-white/20 rounded-lg pl-3.5 pr-4 py-2.5 text-xs text-white placeholder-slate-600 font-mono focus:outline-none transition-colors disabled:opacity-50"
                />
              </div>

              <button
                type="submit"
                disabled={loading || !repoUrl.trim()}
                className="w-full sm:w-auto px-4 py-2.5 bg-zinc-100 hover:bg-white text-zinc-950 disabled:bg-[#161a24] disabled:text-slate-500 rounded-lg text-xs font-mono font-medium flex items-center justify-center gap-2 transition-colors cursor-pointer disabled:cursor-not-allowed shrink-0"
              >
                {loading ? (
                  <>
                    <span className="w-3 h-3 border-2 border-zinc-400 border-t-zinc-950 rounded-full animate-spin" />
                    <span>Provisioning...</span>
                  </>
                ) : (
                  <>
                    <span>Initialize</span>
                    <span>&gt;_</span>
                  </>
                )}
              </button>
            </div>

            {displayError && (
              <div className="p-2.5 rounded border border-red-500/20 bg-red-500/10 flex items-center gap-2 text-xs font-mono text-red-400">
                <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                <span>{displayError}</span>
              </div>
            )}
          </form>
        </div>

        {/* Execution Specifications */}
        <div className="rounded-xl border border-white/[0.08] bg-[#111318] p-5 space-y-3 font-mono text-xs">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
            Sandbox & Verification Specifications
          </span>

          <ul className="space-y-2.5 pt-1">
            <li className="flex items-start gap-2.5">
              <span className="text-xs font-semibold text-zinc-400 mt-0.5">&gt;</span>
              <span className="text-zinc-300 font-sans">
                <strong className="text-white font-medium">Sandbox Isolation:</strong> Container builds and test commands execute entirely inside a privileged Docker-in-Docker container. The host filesystem and credentials are never accessed.
              </span>
            </li>

            <li className="flex items-start gap-2.5">
              <span className="text-xs font-semibold text-zinc-400 mt-0.5">&gt;</span>
              <span className="text-zinc-300 font-sans">
                <strong className="text-white font-medium">Port Probing & Proxy:</strong> Background daemon identifies active listening ports and routes traffic to a local reverse proxy for live browser preview.
              </span>
            </li>

            <li className="flex items-start gap-2.5">
              <span className="text-xs font-semibold text-zinc-400 mt-0.5">&gt;</span>
              <span className="text-zinc-300 font-sans">
                <strong className="text-white font-medium">Facts Ledger Playbook:</strong> Generates an 11-section <code className="text-sky-300 font-mono text-[11px]">PLAYBOOK.md</code> strictly grounded in verified container evidence (<code className="text-emerald-300 font-mono text-[11px]">[Verified]</code>, <code className="text-sky-300 font-mono text-[11px]">[Declared]</code>, <code className="text-slate-400 font-mono text-[11px]">[Assumed]</code>).
              </span>
            </li>
          </ul>
        </div>

      </div>
    </div>
  );
};
