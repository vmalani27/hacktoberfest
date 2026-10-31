import React, { useState, useRef, useEffect } from 'react';
import { Bot, User, ArrowUp, Sparkles, Copy, Check } from 'lucide-react';
import { ChatMessage, ToolCall } from '../types';
import { ApprovalCard } from './ApprovalCard';
import { QuestionCard } from './QuestionCard';

interface ChatStreamProps {
  messages: ChatMessage[];
  currentToolCall?: ToolCall | null;
  onSendMessage: (text: string) => void;
  onApprove: (toolCallId: string, modifiedArgs?: Record<string, any>) => void;
  onReject: (toolCallId: string, feedback?: string) => void;
  onSubmitAnswer: (questionId: string, answer: string) => void;
  loading: boolean;
}

const QUICK_SUGGESTIONS = [
  { label: '🔍 Inspect repository', prompt: 'Inspect the repository and summarize its stack.' },
  { label: '📦 Create Dockerfile', prompt: 'Create an optimized Dockerfile for this project.' },
  { label: '🚀 Test in sandbox', prompt: 'Build and run the container in the sandbox to verify it works.' },
  { label: '💡 What ports are used?', prompt: 'What ports and environment variables does this service need?' },
];

export const ChatStream: React.FC<ChatStreamProps> = ({
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
    <div className="flex-1 flex flex-col h-full overflow-hidden bg-gradient-to-b from-slate-950 via-[#0a0f1d] to-slate-950">
      {/* Scrollable messages area */}
      <div className="flex-1 overflow-y-auto px-4 py-6">
        <div className="max-w-3xl mx-auto space-y-6">
          {messages.map((m, idx) => {
            const isUser = m.role === 'user';

            return (
              <div
                key={idx}
                className={`flex gap-3 text-sm group ${isUser ? 'justify-end' : 'justify-start'}`}
              >
                {!isUser && (
                  <div className="h-7 w-7 rounded-xl bg-gradient-to-br from-indigo-500/20 to-purple-500/20 border border-indigo-500/30 flex items-center justify-center shrink-0 text-indigo-400 mt-0.5 shadow-sm">
                    <Bot className="w-4 h-4" />
                  </div>
                )}

                <div className="relative max-w-[85%]">
                  <div
                    className={`rounded-2xl px-4 py-3 text-xs leading-relaxed ${
                      isUser
                        ? 'bg-gradient-to-r from-indigo-600 to-indigo-500 text-white font-medium shadow-md shadow-indigo-600/20 rounded-br-none'
                        : 'bg-slate-900/90 border border-slate-800/80 text-slate-200 shadow-sm rounded-bl-none backdrop-blur-sm'
                    }`}
                  >
                    <div className="whitespace-pre-wrap selection:bg-indigo-500/30">{m.content}</div>
                  </div>

                  {!isUser && (
                    <button
                      onClick={() => handleCopyMessage(m.content, idx)}
                      className="absolute -bottom-5 right-1 opacity-0 group-hover:opacity-100 transition-opacity p-1 text-slate-500 hover:text-slate-300 rounded text-[10px] flex items-center gap-1"
                      title="Copy response"
                    >
                      {copiedIdx === idx ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    </button>
                  )}
                </div>

                {isUser && (
                  <div className="h-7 w-7 rounded-xl bg-slate-800 border border-slate-700 flex items-center justify-center shrink-0 text-slate-300 mt-0.5">
                    <User className="w-4 h-4" />
                  </div>
                )}
              </div>
            );
          })}

          {/* Interactive Proposal or Question Card */}
          {currentToolCall && (
            <div className="pl-10">
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

          {/* Animated typing indicator */}
          {loading && (
            <div className="flex items-center gap-3 pl-10">
              <div className="h-7 w-7 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
                <Sparkles className="w-3.5 h-3.5 animate-spin text-indigo-400" />
              </div>
              <div className="bg-slate-900/80 border border-slate-800 px-3.5 py-2 rounded-2xl rounded-bl-none flex items-center gap-1.5 shadow-sm">
                <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:-0.3s]" />
                <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce [animation-delay:-0.15s]" />
                <span className="w-1.5 h-1.5 bg-indigo-400 rounded-full animate-bounce" />
                <span className="text-[11px] text-slate-400 ml-1.5">Thinking...</span>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input section with Quick Suggestions */}
      <div className="p-4 border-t border-slate-800/80 bg-slate-900/60 backdrop-blur-md">
        <div className="max-w-3xl mx-auto space-y-2.5">
          {/* Subtle Suggestion Chips */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-[11px]">
            {QUICK_SUGGESTIONS.map((sug) => (
              <button
                key={sug.label}
                onClick={() => onSendMessage(sug.prompt)}
                disabled={loading}
                className="whitespace-nowrap px-2.5 py-1 rounded-lg border border-slate-800 bg-slate-950/60 hover:bg-slate-800 hover:border-slate-700 text-slate-400 hover:text-slate-200 transition-all active:scale-95"
              >
                {sug.label}
              </button>
            ))}
          </div>

          {/* Chat input field */}
          <div className="flex items-center gap-2 bg-slate-950/90 border border-slate-800/90 rounded-2xl px-3.5 py-1.5 focus-within:border-indigo-500 focus-within:ring-2 focus-within:ring-indigo-500/20 transition-all shadow-inner">
            <input
              type="text"
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything or guide the assistant..."
              disabled={loading}
              className="flex-1 bg-transparent text-xs text-slate-200 placeholder-slate-500 focus:outline-none py-2"
            />
            <button
              onClick={handleSend}
              disabled={!inputText.trim() || loading}
              className="h-8 w-8 rounded-xl bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 disabled:opacity-30 disabled:hover:from-indigo-600 flex items-center justify-center text-white transition-all active:scale-95 shadow-md shadow-indigo-600/30"
            >
              <ArrowUp className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
