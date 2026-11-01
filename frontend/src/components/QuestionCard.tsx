import React from 'react';
import { HelpCircle } from 'lucide-react';

interface QuestionCardProps {
  questionId: string;
  question: string;
  options?: string[];
  onSubmitAnswer: (questionId: string, answer: string) => void;
  loading: boolean;
}

export const QuestionCard: React.FC<QuestionCardProps> = ({
  questionId,
  question,
  options = ['Standalone (No database)', 'PostgreSQL', 'Redis', 'MongoDB'],
  onSubmitAnswer,
  loading,
}) => {
  return (
    <div className="my-3 rounded-xl border border-white/[0.08] bg-[#111318] p-4 shadow-sm select-none">
      <div className="flex items-start gap-3">
        <div className="h-6 w-6 rounded border border-white/[0.08] bg-[#161a24] flex items-center justify-center text-slate-400 shrink-0 font-mono text-xs mt-0.5">
          ?
        </div>
        <div className="space-y-3 flex-1">
          <div>
            <span className="font-mono text-[10px] uppercase tracking-wider text-slate-500">Decision Required</span>
            <p className="text-xs font-medium text-white mt-0.5 leading-relaxed font-sans">
              {question || 'Does this application require a companion database or backend service?'}
            </p>
          </div>

          <div className="flex flex-wrap gap-2 pt-1 font-mono text-xs">
            {options.map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => onSubmitAnswer(questionId, opt)}
                disabled={loading}
                className="px-3 py-1.5 rounded border border-white/[0.08] bg-[#151922] hover:bg-[#1e2433] hover:border-white/[0.18] text-slate-300 hover:text-white transition-colors cursor-pointer disabled:opacity-50"
              >
                &gt; {opt}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
