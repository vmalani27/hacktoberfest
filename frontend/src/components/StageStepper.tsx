import React from 'react';
import { CheckCircle2, Circle, AlertCircle, ArrowRight } from 'lucide-react';
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
    <div className="w-full bg-slate-900 border-b border-slate-800 px-6 py-2.5 overflow-x-auto">
      <div className="flex items-center justify-between max-w-5xl mx-auto min-w-[620px]">
        {STAGES.map((s, idx) => {
          const isDone = idx < currentIndex;
          const isActive = idx === currentIndex && !isFailed;
          const isCurrentFailed = idx === currentIndex && isFailed;

          return (
            <React.Fragment key={s.key}>
              <div className="flex items-center gap-2">
                {isDone ? (
                  <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
                ) : isCurrentFailed ? (
                  <AlertCircle className="w-4 h-4 text-rose-500 shrink-0" />
                ) : isActive ? (
                  <div className="w-4 h-4 rounded-full border-2 border-indigo-400 flex items-center justify-center shrink-0">
                    <div className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-ping" />
                  </div>
                ) : (
                  <Circle className="w-4 h-4 text-slate-600 shrink-0" />
                )}

                <span
                  className={`text-xs font-medium whitespace-nowrap ${
                    isActive
                      ? 'text-indigo-400 font-semibold'
                      : isDone
                      ? 'text-slate-300'
                      : isCurrentFailed
                      ? 'text-rose-400'
                      : 'text-slate-500'
                  }`}
                >
                  {s.label}
                </span>
              </div>

              {idx < STAGES.length - 1 && (
                <ArrowRight className="w-3.5 h-3.5 text-slate-700 mx-2 shrink-0" />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
};
