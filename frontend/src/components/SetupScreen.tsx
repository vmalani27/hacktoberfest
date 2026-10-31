import React from 'react';
import { 
  Check, 
  Loader2, 
  AlertCircle, 
  ShieldCheck,
  RotateCcw,
  Sparkles,
  Layers
} from 'lucide-react';
import { SetupStep } from '../types';

interface SetupScreenProps {
  steps: SetupStep[];
  repoUrl?: string;
  detectedStack?: string;
  quarantinedSecrets?: string[];
  error?: string | null;
  onRetry?: () => void;
}

export const SetupScreen: React.FC<SetupScreenProps> = ({
  steps,
  detectedStack,
  quarantinedSecrets = [],
  error,
  onRetry,
}) => {
  return (
    <div className="flex-1 flex flex-col justify-center items-center px-4 sm:px-6 py-12 bg-slate-950 text-slate-100 relative selection:bg-indigo-500/30 overflow-y-auto">
      {/* Ambient glow */}
      <div className="absolute top-0 inset-x-0 h-80 bg-[radial-gradient(ellipse_70%_60%_at_50%_-10%,rgba(99,102,241,0.18),rgba(255,255,255,0))] pointer-events-none" />

      <div className="w-full max-w-xl space-y-6 relative z-10">
        
        {/* Header card */}
        <div className="text-center space-y-2">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-amber-950/60 border border-amber-800/40 text-xs font-medium text-amber-300">
            <span className="w-2 h-2 rounded-full bg-amber-400 animate-pulse" />
            <span>Workspace Provisioning</span>
          </div>

          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
            Initializing Isolated Sandbox
          </h2>

          <p className="text-xs sm:text-sm text-slate-400 max-w-md mx-auto leading-relaxed">
            Preparing your disposable sandbox container, cloning source files, and running security checks.
          </p>
        </div>

        {/* Steps List Card */}
        <div className="border border-slate-800 rounded-2xl bg-slate-900/80 shadow-xl backdrop-blur-md divide-y divide-slate-800/80 overflow-hidden">
          {steps.map((step, idx) => {
            const isSecretStep = step.id === 'step-3';
            const isDone = step.status === 'completed';
            const isRunning = step.status === 'running';
            const isFailed = step.status === 'failed';

            return (
              <div 
                key={step.id || idx}
                className={`p-4 flex items-start gap-3.5 transition-all duration-200 ${
                  isRunning 
                    ? 'bg-indigo-950/20' 
                    : isDone 
                      ? 'bg-transparent' 
                      : 'opacity-40 bg-slate-950/20'
                }`}
              >
                <div className="mt-0.5 shrink-0">
                  {isDone ? (
                    <div className="w-5 h-5 rounded-full bg-emerald-950 border border-emerald-500/50 flex items-center justify-center shadow-sm">
                      <Check className="w-3 h-3 text-emerald-400" />
                    </div>
                  ) : isRunning ? (
                    <div className="w-5 h-5 rounded-full bg-indigo-950 border border-indigo-500/50 flex items-center justify-center shadow-sm">
                      <Loader2 className="w-3 h-3 text-indigo-400 animate-spin" />
                    </div>
                  ) : isFailed ? (
                    <div className="w-5 h-5 rounded-full bg-rose-950 border border-rose-500/50 flex items-center justify-center shadow-sm">
                      <AlertCircle className="w-3 h-3 text-rose-400" />
                    </div>
                  ) : (
                    <div className="w-5 h-5 rounded-full border border-slate-700 bg-slate-800/50" />
                  )}
                </div>

                <div className="flex-1 min-w-0 space-y-1">
                  <div className="flex items-center justify-between">
                    <p className={`text-xs font-medium ${
                      isRunning ? 'text-indigo-200' : isDone ? 'text-slate-200' : 'text-slate-400'
                    }`}>
                      {step.label}
                    </p>
                    {isDone && (
                      <span className="text-[10px] font-mono text-emerald-400/80 uppercase">
                        Ready
                      </span>
                    )}
                    {isRunning && (
                      <span className="text-[10px] font-mono text-indigo-400 uppercase animate-pulse">
                        Working...
                      </span>
                    )}
                  </div>

                  {step.detail && (
                    <p className="text-[11px] text-slate-400 leading-relaxed font-sans">
                      {step.detail}
                    </p>
                  )}

                  {isSecretStep && quarantinedSecrets.length > 0 && (
                    <div className="pt-2 flex items-center gap-1.5 text-xs text-amber-300 font-mono bg-amber-950/40 border border-amber-800/40 px-2.5 py-1.5 rounded-lg">
                      <ShieldCheck className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                      <span>Quarantined {quarantinedSecrets.length} file(s): {quarantinedSecrets.join(', ')}</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Stack notification card if detected */}
        {detectedStack && (
          <div className="p-3.5 rounded-xl bg-slate-900/60 border border-slate-800 flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-indigo-400" />
              <span className="text-slate-300">Detected Runtime:</span>
            </div>
            <span className="font-semibold text-indigo-300 bg-indigo-950/60 border border-indigo-800/40 px-2.5 py-0.5 rounded-full">
              {detectedStack}
            </span>
          </div>
        )}

        {/* Error notification and retry button */}
        {error && (
          <div className="p-4 rounded-xl bg-rose-950/50 border border-rose-800/60 space-y-3 shadow-lg">
            <div className="flex items-start gap-2.5 text-xs text-rose-300">
              <AlertCircle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <p className="font-semibold text-rose-200">Failed to initialize workspace</p>
                <p className="font-mono text-[11px] leading-relaxed break-all opacity-90">{error}</p>
              </div>
            </div>

            {onRetry && (
              <button
                onClick={onRetry}
                className="w-full py-2 px-3 rounded-lg bg-rose-900/60 hover:bg-rose-900 border border-rose-700/60 text-xs font-semibold text-rose-100 flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Return to Home</span>
              </button>
            )}
          </div>
        )}

      </div>
    </div>
  );
};
