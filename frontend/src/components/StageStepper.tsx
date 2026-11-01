import React from 'react';
import { Check, AlertCircle } from 'lucide-react';
import { Stage } from '../types';

interface StageStepperProps {
  currentStage: Stage;
}

const STAGES: { key: Stage; label: string }[] = [
  { key: 'INSPECT', label: '1. Inspect' },
  { key: 'INTERVIEW', label: '2. Interview' },
  { key: 'PLAN', label: '3. Plan' },
  { key: 'EXECUTE', label: '4. Execute' },
  { key: 'VERIFY', label: '5. Verify' },
  { key: 'EXPORT', label: '6. Export' },
];

export const StageStepper: React.FC<StageStepperProps> = ({ currentStage }) => {
  const getStageIndex = (stage: Stage): number => {
    const idx = STAGES.findIndex((s) => s.key === stage);
    if (idx !== -1) return idx;
    if (stage === 'COMPLETED') return STAGES.length;
    return 0;
  };

  const currentIndex = getStageIndex(currentStage);
  const isFailed = currentStage === 'FAILED';

  return (
    <div className="h-[36px] shrink-0 w-full bg-[#0c0e14] border-b border-white/[0.08] px-4 flex items-center overflow-x-auto select-none font-mono text-xs">
      <div className="flex items-center justify-between w-full max-w-4xl mx-auto min-w-[580px]">
        {STAGES.map((s, idx) => {
          const isDone = idx < currentIndex;
          const isActive = idx === currentIndex && !isFailed;
          const isCurrentFailed = idx === currentIndex && isFailed;

          return (
            <React.Fragment key={s.key}>
              <div className="flex items-center gap-1.5">
                {isDone ? (
                  <Check className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
                ) : isCurrentFailed ? (
                  <AlertCircle className="w-3.5 h-3.5 text-red-400 shrink-0" />
                ) : isActive ? (
                  <span className="w-1.5 h-1.5 rounded-full bg-sky-400 animate-pulse shrink-0" />
                ) : (
                  <span className="w-1.5 h-1.5 rounded-full bg-zinc-700 shrink-0" />
                )}

                <span
                  className={`text-[11px] whitespace-nowrap ${
                    isActive
                      ? 'text-white font-semibold'
                      : isDone
                      ? 'text-slate-300'
                      : isCurrentFailed
                      ? 'text-red-400 font-semibold'
                      : 'text-zinc-500'
                  }`}
                >
                  {s.label}
                </span>
              </div>

              {idx < STAGES.length - 1 && (
                <span className="text-zinc-700 text-[10px] select-none">/</span>
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};
