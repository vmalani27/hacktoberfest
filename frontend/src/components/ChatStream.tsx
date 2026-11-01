import React, { useState, useRef, useEffect } from 'react';
import { ArrowUp, Copy, Check } from 'lucide-react';
import { ChatMessage, ToolCall, SessionState } from '../types';
import { ApprovalCard } from './ApprovalCard';
import { QuestionCard } from './QuestionCard';

interface ChatStreamProps {
  session?: SessionState | null;
  messages: ChatMessage[];
  currentToolCall?: ToolCall | null;
  onSendMessage: (text: string) => void;
  onApprove: (toolCallId: string, modifiedArgs?: Record<string, any>) => void;
  onReject: (toolCallId: string, feedback?: string) => void;
  onSubmitAnswer: (questionId: string, answer: string) => void;
  loading: boolean;
  onToggleTerminal?: () => void;
  onToggleFiles?: () => void;
  isTerminalOpen?: boolean;
}

const QUICK_SUGGESTIONS = [
  { label: 'Inspect stack', prompt: 'Inspect the repository structure and detect required runtime dependencies.' },
  { label: 'Generate Dockerfile', prompt: 'Create an optimized Dockerfile for this project.' },
  { label: 'Verify in sandbox', prompt: 'Build and run the container in the sandbox to verify it works.' },
  { label: 'Check ports & env', prompt: 'What ports and environment variables does this service expose?' },
];

export const ChatStream: React.FC<ChatStreamProps> = ({
  session,
  messages,
  currentToolCall,
  onSendMessage,
  onApprove,
  onReject,
  onSubmitAnswer,
  loading,
}) => {
  const [inputText, setInputText] = useState('');
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, currentToolCall, loading]);

  const handleSend = () => {
    if (!inputText.trim() || loading) return;
    onSendMessage(inputText.trim());
    setInputText('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSend();
    }
  };

  const handleCopyMessage = (text: string, idx: number) => {
    navigator.clipboard.writeText(text);
    setCopiedIdx(idx);
    setTimeout(() => setCopiedIdx(null), 2000);
  };

  return (
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-[#090a0f] text-slate-100">
      {/* Scrollable messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto space-y-5">
          {messages.map((m, idx) => {
            const isUser = m.role === 'user';

            return (
              <div
                key={idx}
                className={`flex gap-3 text-xs group ${isUser ? 'justify-end' : 'justify-start'}`}
              >
                {!isUser && (
                  <div className="h-6 w-6 rounded border border-white/[0.08] bg-[#161a24] flex items-center justify-center shrink-0 text-slate-400 font-mono text-[10px] mt-0.5">
                    ai
                  </div>
                )}

                <div className="relative max-w-[85%]">
                  <div
                    className={`rounded-lg px-4 py-3 leading-relaxed ${
                      isUser
                        ? 'bg-[#181d28] border border-white/[0.12] text-white'
                        : 'bg-[#111318] border border-white/[0.08] text-slate-200'
                    }`}
                  >
                    <div className="whitespace-pre-wrap font-sans selection:bg-slate-700/50">{m.content}</div>
                  </div>

                  {!isUser && (
                    <button
                      onClick={() => handleCopyMessage(m.content, idx)}
                      className="absolute -bottom-4 right-1 opacity-0 group-hover:opacity-100 transition-opacity p-0.5 text-zinc-500 hover:text-zinc-300 rounded text-[10px] flex items-center gap-1 font-mono"
                      title="Copy response"
                    >
                      {copiedIdx === idx ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    </button>
                  )}
                </div>

                {isUser && (
                  <div className="h-6 w-6 rounded border border-white/[0.08] bg-[#1e2433] flex items-center justify-center shrink-0 text-slate-300 font-mono text-[10px] mt-0.5">
                    you
                  </div>
                )}
              </div>
            );
          })}

          {/* Interactive Question or Approval Card */}
          {currentToolCall && (
            <div className="pl-9">
              {currentToolCall.tool_name === 'ask_user' ? (
                <QuestionCard
                  questionId={currentToolCall.arguments.question_id || 'q'}
                  question={currentToolCall.arguments.question}
                  options={currentToolCall.arguments.options}
                  onSubmitAnswer={onSubmitAnswer}
                  loading={loading}
                />
              ) : (
                <ApprovalCard
                  toolCall={currentToolCall}
                  onApprove={onApprove}
                  onReject={onReject}
                  loading={loading}
                />
              )}
            </div>
          )}

          {/* Loading status indicator */}
          {loading && (
            <div className="flex items-center gap-2 pl-9 font-mono text-xs text-zinc-400">
              <span className="inline-block h-3 w-3 animate-spin rounded-full border-[1.5px] border-zinc-400 border-t-transparent" />
              <span>Analyzing workspace...</span>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input section with clean suggestion chips */}
      <div className="p-3 border-t border-white/[0.08] bg-[#0c0e14]">
        <div className="max-w-3xl mx-auto space-y-2">
          {/* Suggestion Chips */}
          {!currentToolCall && (
            <div className="flex items-center gap-1.5 overflow-x-auto pb-0.5 font-mono text-[11px]">
              {QUICK_SUGGESTIONS.map((sug) => (
                <button
                  key={sug.label}
                  onClick={() => onSendMessage(sug.prompt)}
                  disabled={loading}
                  className="whitespace-nowrap px-2.5 py-1 rounded border border-white/[0.08] bg-[#12151c] hover:bg-[#181d28] text-slate-400 hover:text-white transition-colors cursor-pointer"
                >
                  &gt; {sug.label}
                </button>
              ))}
            </div>
          )}

          {/* Chat input form */}
          <div className="flex items-center gap-2 bg-[#111318] border border-white/[0.08] focus-within:border-white/20 rounded-lg px-3 py-1.5 transition-colors">
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Send message or deployment instruction..."
              disabled={loading}
              className="flex-1 bg-transparent text-xs text-white placeholder-slate-600 focus:outline-none font-mono py-1"
            />
            <button
              onClick={handleSend}
              disabled={!inputText.trim() || loading}
              className="px-2.5 py-1 rounded bg-zinc-100 hover:bg-white text-zinc-950 disabled:bg-[#181d28] disabled:text-zinc-600 flex items-center gap-1 text-xs font-mono font-medium transition-colors cursor-pointer disabled:cursor-not-allowed"
            >
              <span>Send</span>
              <ArrowUp className="w-3 h-3" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
