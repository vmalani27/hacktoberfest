import React, { useState } from 'react';
import { 
  ArrowRight, 
  AlertCircle, 
  CornerDownLeft, 
  FolderGit2, 
  Sparkles, 
  ShieldCheck, 
  Terminal, 
  FileCheck2, 
  Box, 
  Zap, 
  Bug
} from 'lucide-react';

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
    if (!trimmed) return 'Please paste a repository URL.';
    if (trimmed.startsWith('git@')) {
      return 'SSH URLs require private keys. Please use a public HTTPS repository URL.';
    }
    if (!trimmed.startsWith('https://')) {
      return 'Only HTTPS repository links are supported. Public repositories only for now.';
    }
    try {
      const parsed = new URL(trimmed);
      if (parsed.username || parsed.password) {
        return 'Do not include personal access tokens or credentials in the URL. Public repositories only for now.';
      }
      const parts = parsed.pathname.replace(/^\/|\/$/g, '').replace(/\.git$/, '').split('/');
      if (parts.length < 2 || !parts[0] || !parts[1]) {
        return 'Enter a recognizable repository path (e.g., https://github.com/owner/repo)';
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

  const handleSelectSample = (sampleType: 'node' | 'python' | 'broken') => {
    setInputError(null);
    if (sampleType === 'node') {
      onStartSession('https://github.com/expressjs/express', 'fixtures/sample-node-app');
    } else if (sampleType === 'python') {
      onStartSession('https://github.com/tiangolo/fastapi', 'fixtures/sample-python-app');
    } else {
      onStartSession('https://github.com/broken-app/syntax-error', 'fixtures/broken-app');
    }
  };

  const displayError = inputError || externalError;

  return (
    <div className="flex-1 flex flex-col justify-start items-center px-4 sm:px-6 py-10 md:py-14 bg-slate-950 text-slate-100 overflow-y-auto relative selection:bg-indigo-500/30">
      {/* Subtle top ambient glow */}
      <div className="absolute top-0 inset-x-0 h-96 bg-[radial-gradient(ellipse_80%_60%_at_50%_-20%,rgba(99,102,241,0.2),rgba(255,255,255,0))] pointer-events-none" />

      <div className="w-full max-w-3xl space-y-10 relative z-10">
        
        {/* Hero Section */}
        <div className="text-center space-y-4">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-950/70 border border-indigo-800/40 text-xs font-medium text-indigo-300 shadow-sm backdrop-blur-sm">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            <span>AI-Assisted Containerization & Verification</span>
          </div>

          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight text-white leading-tight">
            Turn any repository into a <br className="hidden sm:inline" />
            <span className="bg-gradient-to-r from-indigo-400 via-purple-300 to-indigo-200 bg-clip-text text-transparent">
              verified container
            </span>
          </h1>

          <p className="text-sm sm:text-base text-slate-400 max-w-xl mx-auto leading-relaxed">
            Inspect source code, generate production Dockerfiles, test builds in an isolated sandbox, and compile a verified playbook with zero setup.
          </p>
        </div>

        {/* Repository URL Input Form */}
        <div className="bg-slate-900/80 border border-slate-800 rounded-2xl p-3 sm:p-4 shadow-xl backdrop-blur-md">
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="flex items-center justify-between px-1 text-xs">
              <label htmlFor="repo-input" className="text-slate-300 font-medium flex items-center gap-1.5">
                <FolderGit2 className="w-3.5 h-3.5 text-indigo-400" />
                <span>Git Repository URL</span>
              </label>
              <span className="text-[11px] text-slate-500 font-mono">
                Public HTTPS repositories only
              </span>
            </div>

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
                  placeholder="https://github.com/username/repository"
                  disabled={loading}
                  autoFocus
                  spellCheck={false}
                  autoComplete="off"
                  className="w-full bg-slate-950/70 border border-slate-700/80 hover:border-slate-600 focus:border-indigo-500 rounded-xl pl-4 pr-10 py-3 text-sm text-slate-100 placeholder-slate-500 font-mono focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all disabled:opacity-50"
                />
              </div>

              <button
                type="submit"
                disabled={loading || !repoUrl.trim()}
                className="w-full sm:w-auto px-5 py-3 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white disabled:from-slate-800 disabled:to-slate-800 disabled:text-slate-500 rounded-xl text-sm font-semibold flex items-center justify-center gap-2 shadow-lg shadow-indigo-600/20 transition-all duration-150 cursor-pointer disabled:cursor-not-allowed shrink-0"
              >
                {loading ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span>Launching...</span>
                  </>
                ) : (
                  <>
                    <span>Start Deploy</span>
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </div>

            {displayError && (
              <div className="p-2.5 rounded-lg bg-rose-950/40 border border-rose-800/50 flex items-center gap-2 text-xs text-rose-300">
                <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />
                <span>{displayError}</span>
              </div>
            )}
          </form>
        </div>

        {/* Quick Launch Sample Fixtures */}
        <div className="space-y-3">
          <div className="flex items-center justify-between text-xs px-1">
            <span className="font-medium text-slate-400 uppercase tracking-wider text-[11px]">
              Or launch a pre-built sample fixture
            </span>
            <span className="text-slate-500 text-[11px]">One-click instant sandbox boot</span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {/* Sample 1: Node.js */}
            <button
              type="button"
              onClick={() => handleSelectSample('node')}
              disabled={loading}
              className="text-left p-4 rounded-xl bg-slate-900/60 hover:bg-slate-900 border border-slate-800/80 hover:border-indigo-500/50 hover:shadow-lg hover:shadow-indigo-500/5 transition-all group cursor-pointer disabled:opacity-50"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="w-8 h-8 rounded-lg bg-emerald-950/60 border border-emerald-800/40 flex items-center justify-center text-emerald-400 group-hover:scale-105 transition-transform">
                  <Box className="w-4 h-4" />
                </div>
                <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/40 px-2 py-0.5 rounded border border-emerald-800/30">
                  Port 3000
                </span>
              </div>
              <h3 className="font-semibold text-sm text-slate-200 group-hover:text-white flex items-center gap-1.5">
                Node.js Express
                <ArrowRight className="w-3.5 h-3.5 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-indigo-400" />
              </h3>
              <p className="text-xs text-slate-400 mt-1 leading-normal">
                REST service with package.json dependencies and health check endpoint.
              </p>
            </button>

            {/* Sample 2: Python FastAPI */}
            <button
              type="button"
              onClick={() => handleSelectSample('python')}
              disabled={loading}
              className="text-left p-4 rounded-xl bg-slate-900/60 hover:bg-slate-900 border border-slate-800/80 hover:border-indigo-500/50 hover:shadow-lg hover:shadow-indigo-500/5 transition-all group cursor-pointer disabled:opacity-50"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="w-8 h-8 rounded-lg bg-indigo-950/60 border border-indigo-800/40 flex items-center justify-center text-indigo-400 group-hover:scale-105 transition-transform">
                  <Zap className="w-4 h-4" />
                </div>
                <span className="text-[10px] font-mono text-indigo-400 bg-indigo-950/40 px-2 py-0.5 rounded border border-indigo-800/30">
                  Port 8000
                </span>
              </div>
              <h3 className="font-semibold text-sm text-slate-200 group-hover:text-white flex items-center gap-1.5">
                Python FastAPI
                <ArrowRight className="w-3.5 h-3.5 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-indigo-400" />
              </h3>
              <p className="text-xs text-slate-400 mt-1 leading-normal">
                Async web API with requirements.txt, Uvicorn, and OpenAPI schema.
              </p>
            </button>

            {/* Sample 3: Broken App */}
            <button
              type="button"
              onClick={() => handleSelectSample('broken')}
              disabled={loading}
              className="text-left p-4 rounded-xl bg-slate-900/60 hover:bg-slate-900 border border-slate-800/80 hover:border-rose-500/50 hover:shadow-lg hover:shadow-rose-500/5 transition-all group cursor-pointer disabled:opacity-50"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="w-8 h-8 rounded-lg bg-rose-950/60 border border-rose-800/40 flex items-center justify-center text-rose-400 group-hover:scale-105 transition-transform">
                  <Bug className="w-4 h-4" />
                </div>
                <span className="text-[10px] font-mono text-rose-400 bg-rose-950/40 px-2 py-0.5 rounded border border-rose-800/30">
                  Stop Rule
                </span>
              </div>
              <h3 className="font-semibold text-sm text-slate-200 group-hover:text-white flex items-center gap-1.5">
                Syntax Error App
                <ArrowRight className="w-3.5 h-3.5 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all text-rose-400" />
              </h3>
              <p className="text-xs text-slate-400 mt-1 leading-normal">
                Tests safety rails, error diagnostics, and human-in-the-loop review.
              </p>
            </button>
          </div>
        </div>

        {/* Platform Feature Pillars */}
        <div className="border-t border-slate-800/80 pt-8 space-y-4">
          <div className="text-[11px] font-mono tracking-wider uppercase text-slate-400 font-medium">
            Core Architecture & Capabilities
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/60 space-y-2">
              <div className="flex items-center gap-2 text-slate-200 font-medium text-xs">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>Isolated DinD Sandbox</span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Builds and test runs execute in an isolated container sandbox with zero reach into your host system.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/60 space-y-2">
              <div className="flex items-center gap-2 text-slate-200 font-medium text-xs">
                <Terminal className="w-4 h-4 text-indigo-400" />
                <span>Port Probing & Web Shell</span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Live port discovery with reverse-proxy browser preview and fully interactive embedded PTY terminal.
              </p>
            </div>

            <div className="p-4 rounded-xl bg-slate-900/40 border border-slate-800/60 space-y-2">
              <div className="flex items-center gap-2 text-slate-200 font-medium text-xs">
                <FileCheck2 className="w-4 h-4 text-purple-400" />
                <span>Verified 11-Tier Playbook</span>
              </div>
              <p className="text-xs text-slate-400 leading-relaxed">
                Grounded in a strict 3-tier facts ledger (<code className="text-[11px] text-indigo-300">[Verified]</code>, <code className="text-[11px] text-purple-300">[Declared]</code>, <code className="text-[11px] text-slate-400">[Assumed]</code>) with PDF export.
              </p>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};
