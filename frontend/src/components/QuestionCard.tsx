import React from 'react';
import { HelpCircle, Database, Check } from 'lucide-react';

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
    <div className="my-3.5 rounded-2xl border border-indigo-500/25 bg-gradient-to-b from-indigo-950/20 to-slate-950/40 p-4 shadow-lg shadow-black/20 backdrop-blur-sm">
      <div className="flex items-start gap-3">
        <div className="h-8 w-8 rounded-xl bg-indigo-500/10 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0">
          <HelpCircle className="w-4 h-4" />
        </div>
        <div className="space-y-3 flex-1">
          <p className="text-xs font-medium text-slate-100 leading-relaxed">
            {question || 'Does this application require a database or companion service?'}
          </p>

          <div className="flex flex-wrap gap-2 pt-1">
            {options.map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => onSubmitAnswer(questionId, opt)}
                disabled={loading}
                className="group text-xs px-3.5 py-2 rounded-xl border border-slate-700/80 bg-slate-900/80 hover:bg-gradient-to-r hover:from-indigo-600 hover:to-indigo-500 hover:border-indigo-400 hover:text-white text-slate-300 transition-all active:scale-95 shadow-sm flex items-center gap-1.5"
              >
                <Database className="w-3.5 h-3.5 text-indigo-400 group-hover:text-white transition-colors" />
                <span>{opt}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
