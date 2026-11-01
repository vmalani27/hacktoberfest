import React from 'react';
import { 
  Check, 
  AlertCircle, 
  ShieldCheck,
  RotateCcw
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
    <div className="flex-1 flex flex-col justify-center items-center px-4 sm:px-6 py-12 bg-[#090a0f] text-slate-100 select-none">
      <div className="w-full max-w-2xl space-y-6">
        
        {/* Header */}
        <div>
          <h2 className="text-xl font-bold tracking-tight text-white">
            Provisioning Sandbox
          </h2>
          <p className="text-xs text-[#94a3b8] mt-1 font-mono">
            Booting Docker-in-Docker runtime and preparing isolated workspace...
          </p>
        </div>

        {/* Technical Boot Checklist (ProvisioningBoot style) */}
        <div className="rounded-xl border border-white/[0.08] bg-[#111318] p-5 shadow-sm font-mono text-xs divide-y divide-white/[0.06]">
          {steps.map((step, idx) => {
            const isSecretStep = step.id === 'step-3';
            const isDone = step.status === 'completed';
            const isRunning = step.status === 'running';
            const isFailed = step.status === 'failed';

            return (
              <div 
                key={step.id || idx}
                className={`py-3 flex items-start gap-3 transition-colors ${
                  isRunning 
                    ? 'text-white' 
                    : isDone 
                      ? 'text-slate-300' 
                      : isFailed
                        ? 'text-red-400'
                        : 'text-zinc-600'
                }`}
              >
                <div className="mt-0.5 shrink-0 font-mono text-xs">
                  {isDone ? (
                    <span className="text-emerald-400 font-semibold">[OK]</span>
                  ) : isRunning ? (
                    <span className="text-amber-300 inline-flex items-center gap-1">
                      <span className="inline-block h-2 w-2 animate-spin rounded-full border border-amber-300 border-t-transparent" />
                      <span>[..]</span>
                    </span>
                  ) : isFailed ? (
                    <span className="text-red-400 font-semibold">[ERR]</span>
                  ) : (
                    <span className="text-zinc-600">[--]</span>
                  )}
                </div>

                <div className="flex-1 min-w-0 space-y-0.5">
                  <div className="flex items-center justify-between">
                    <span className={`font-mono text-xs ${isRunning ? 'text-white font-medium' : isDone ? 'text-slate-200' : 'text-zinc-500'}`}>
                      {step.label}
                    </span>
                    {isDone && (
                      <span className="text-[10px] text-zinc-500 font-mono">done</span>
                    )}
                  </div>

                  {step.detail && (
                    <p className="text-[11px] text-zinc-500 font-sans leading-relaxed">
                      {step.detail}
                    </p>
                  )}

                  {isSecretStep && quarantinedSecrets.length > 0 && (
                    <div className="mt-1.5 flex items-center gap-1.5 text-[11px] text-amber-300/90 font-mono bg-amber-500/10 border border-amber-500/20 px-2 py-1 rounded">
                      <ShieldCheck className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                      <span>Quarantined {quarantinedSecrets.length} file(s): {quarantinedSecrets.join(', ')}</span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        {/* Runtime Stack Detected */}
        {detectedStack && (
          <div className="flex items-center justify-between px-4 py-2.5 rounded-lg border border-white/[0.08] bg-[#151922] font-mono text-xs">
            <span className="text-slate-400">DETECTED_RUNTIME:</span>
            <span className="text-emerald-300 font-medium">{detectedStack}</span>
          </div>
        )}

        {/* Error reporting */}
        {error && (
          <div className="p-4 rounded-xl border border-red-500/20 bg-red-500/10 space-y-3 font-mono text-xs">
            <div className="flex items-start gap-2.5 text-red-400">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="space-y-1">
                <span className="font-semibold">Setup failed:</span>
                <p className="text-[11px] text-red-300/90 break-all">{error}</p>
              </div>
            </div>

            {onRetry && (
              <button
                onClick={onRetry}
                className="w-full py-2 px-3 rounded bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/30 text-xs font-mono flex items-center justify-center gap-1.5 transition-colors cursor-pointer"
              >
                <RotateCcw className="w-3.5 h-3.5" />
                <span>Return to repository selection</span>
              </button>
            )}
          </div>
        )}

      </div>
    </div>
  );
};
