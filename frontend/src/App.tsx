import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { ChatStream } from './components/ChatStream';
import { ExportPanel } from './components/ExportPanel';
import { TerminalView } from './components/TerminalView';
import { StartScreen } from './components/StartScreen';
import { SetupScreen } from './components/SetupScreen';
import { ClosingModal } from './components/ClosingModal';
import { StageStepper } from './components/StageStepper';
import { SessionState, SetupStep, SetupStatusResponse } from './types';

type ViewMode = 'START' | 'SETTING_UP' | 'CHAT';

export const App: React.FC = () => {
  const [viewMode, setViewMode] = useState<ViewMode>('START');
  const [sessionId, setSessionId] = useState<string>('');
  const [session, setSession] = useState<SessionState | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [setupError, setSetupError] = useState<string | null>(null);
  const [setupSteps, setSetupSteps] = useState<SetupStep[]>([]);
  const [quarantinedSecrets, setQuarantinedSecrets] = useState<string[]>([]);
  const [detectedStack, setDetectedStack] = useState<string | undefined>();
  
  const [openPorts, setOpenPorts] = useState<{ port: number; url: string; label: string }[]>([]);
  const [showFilesPanel, setShowFilesPanel] = useState<boolean>(false);
  const [showTerminal, setShowTerminal] = useState<boolean>(true);
  const [showClosingModal, setShowClosingModal] = useState<boolean>(false);

  // Poll setup status when in SETTING_UP mode
  useEffect(() => {
    if (viewMode !== 'SETTING_UP' || !sessionId) return;

    let isMounted = true;
    const interval = setInterval(async () => {
      try {
        const res = await fetch(`/api/session/${sessionId}/setup-status`);
        if (!res.ok) return;
        const data: SetupStatusResponse = await res.json();
        if (!isMounted) return;

        if (data.steps && data.steps.length > 0) {
          setSetupSteps(data.steps);
        }
        if (data.detected_stack) {
          setDetectedStack(data.detected_stack);
        }
        if (data.quarantined_secrets) {
          setQuarantinedSecrets(data.quarantined_secrets);
        }

        if (data.error) {
          setSetupError(data.error);
          clearInterval(interval);
        } else if (data.completed) {
          clearInterval(interval);
          const sRes = await fetch(`/api/session/${sessionId}`);
          if (sRes.ok) {
            const sData = await sRes.json();
            setSession(sData);
            setTimeout(() => {
              if (isMounted) setViewMode('CHAT');
            }, 600);
          }
        }
      } catch (err) {
        console.error('Setup poll error:', err);
      }
    }, 700);

    return () => {
      isMounted = false;
      clearInterval(interval);
    };
  }, [viewMode, sessionId]);

  // Poll open ports periodically when in CHAT mode
  useEffect(() => {
    if (viewMode !== 'CHAT') return;
    const pollPorts = async () => {
      try {
        const res = await fetch('/api/sandbox/ports');
        if (res.ok) {
          const ports = await res.json();
          setOpenPorts(ports);
        }
      } catch (e) {
        // ignore
      }
    };
    pollPorts();
    const interval = setInterval(pollPorts, 3000);
    return () => clearInterval(interval);
  }, [viewMode]);

  const handleStartSession = async (repoUrl: string, localPath?: string) => {
    try {
      setLoading(true);
      setSetupError(null);
      const newSessionId = 'sess-' + Math.random().toString(36).substring(2, 9);
      setSessionId(newSessionId);

      setSetupSteps([
        { id: 'step-1', label: 'Opening a fresh workspace…', status: 'running', detail: 'Preparing an isolated, disposable sandbox container.' },
        { id: 'step-2', label: 'Downloading your project from GitHub…', status: 'pending', detail: 'Cloning with shallow depth (--depth 1).' },
        { id: 'step-3', label: 'Setting aside files that might hold secrets…', status: 'pending', detail: 'Scanning for secrets and sensitive credential files.' },
        { id: 'step-4', label: 'Taking a look at what\'s inside…', status: 'pending', detail: 'Inspecting package manifests and application architecture.' },
        { id: 'step-5', label: 'Ready.', status: 'pending', detail: 'Preparing hand-off to chat assistant.' }
      ]);
      setViewMode('SETTING_UP');

      const res = await fetch('/api/session/init', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: newSessionId,
          repo_url: repoUrl,
          local_path: localPath
        })
      });

      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to initialize workspace');
      }

      const sessionData = await res.json();
      setSession(sessionData);
      setDetectedStack(sessionData.detected_stack);
      setQuarantinedSecrets(sessionData.quarantined_secrets || []);

      setTimeout(() => {
        setViewMode('CHAT');
      }, 700);
    } catch (err: any) {
      console.error('Session init error:', err);
      setSetupError(err.message || 'Failed to start session');
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async (text: string) => {
    if (!sessionId) return;
    try {
      setLoading(true);
      const res = await fetch(`/api/session/${sessionId}/message`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text })
      });
      if (res.ok) {
        const updated = await res.json();
        setSession(updated);
      }
    } catch (err) {
      console.error('Failed to send message:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (toolCallId: string, modifiedArgs?: Record<string, any>) => {
    if (!sessionId) return;
    try {
      setLoading(true);
      const res = await fetch(`/api/session/${sessionId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tool_call_id: toolCallId,
          approved: true,
          modified_arguments: modifiedArgs
        })
      });
      if (res.ok) {
        const updated = await res.json();
        setSession(updated);
      }
    } catch (err) {
      console.error('Approval failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async (toolCallId: string, feedback?: string) => {
    if (!sessionId) return;
    try {
      setLoading(true);
      const res = await fetch(`/api/session/${sessionId}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tool_call_id: toolCallId,
          approved: false,
          feedback
        })
      });
      if (res.ok) {
        const updated = await res.json();
        setSession(updated);
      }
    } catch (err) {
      console.error('Reject failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitAnswer = async (questionId: string, answer: string) => {
    if (!sessionId) return;
    try {
      setLoading(true);
      const res = await fetch(`/api/session/${sessionId}/answer`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question_id: questionId,
          answer
        })
      });
      if (res.ok) {
        const updated = await res.json();
        setSession(updated);
      }
    } catch (err) {
      console.error('Failed to submit answer:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteWorkspace = async () => {
    if (!sessionId) return;
    const res = await fetch(`/api/session/${sessionId}`, {
      method: 'DELETE'
    });
    if (!res.ok) {
      throw new Error('Failed to delete workspace');
    }
  };

  const handleResetToStart = () => {
    setShowClosingModal(false);
    setSession(null);
    setSessionId('');
    setViewMode('START');
    setSetupError(null);
  };

  const fileCount = Object.keys(session?.exported_artifacts || {}).length;
  const repoBasename = session?.repo_url 
    ? session.repo_url.split('/').pop()?.replace(/\.git$/, '') 
    : session?.repo_path?.split(/[\\/]/).pop() || 'repository';

  return (
    <div className="flex flex-col h-screen bg-slate-950 text-slate-100 font-sans selection:bg-indigo-500/30 overflow-hidden">
      
      {/* Persistent Global Studio Header with Per-Repo Metadata */}
      <Header
        viewMode={viewMode}
        repoName={repoBasename}
        repoUrl={session?.repo_url}
        detectedStack={session?.detected_stack || detectedStack}
        appPort={session?.app_port}
        quarantinedCount={session?.quarantined_secrets?.length || 0}
        filesCount={fileCount}
        openPorts={openPorts}
        showTerminal={showTerminal}
        onToggleTerminal={() => setShowTerminal(!showTerminal)}
        onToggleFiles={() => setShowFilesPanel(!showFilesPanel)}
        onDownload={() => setShowClosingModal(true)}
        onCloseWorkspace={() => setShowClosingModal(true)}
      />

      {/* 1. START SCREEN */}
      {viewMode === 'START' && (
        <StartScreen
          onStartSession={handleStartSession}
          loading={loading}
          error={setupError}
        />
      )}

      {/* 2. LIVE SETUP SCREEN */}
      {viewMode === 'SETTING_UP' && (
        <SetupScreen
          steps={setupSteps}
          detectedStack={detectedStack}
          quarantinedSecrets={quarantinedSecrets}
          error={setupError}
          onRetry={handleResetToStart}
        />
      )}

      {/* 3. CHAT & INTERACTIVE WORKSPACE */}
      {viewMode === 'CHAT' && (
        <>
          <StageStepper currentStage={session?.stage || 'INSPECT'} />

          <main className="flex-1 flex overflow-hidden relative">
            {/* Chat Assistant Stream */}
            <div className="flex-1 flex flex-col min-w-0">
              <ChatStream
                session={session}
                messages={session?.messages || []}
                currentToolCall={session?.current_tool_call}
                onSendMessage={handleSendMessage}
                onApprove={handleApprove}
                onReject={handleReject}
                onSubmitAnswer={handleSubmitAnswer}
                loading={loading}
                onToggleTerminal={() => setShowTerminal(!showTerminal)}
                onToggleFiles={() => setShowFilesPanel(!showFilesPanel)}
                isTerminalOpen={showTerminal}
              />
            </div>

            {/* Interactive Sandbox Terminal */}
            {showTerminal && (
              <TerminalView sessionId={sessionId} />
            )}

            {/* Exported Files Drawer */}
            {showFilesPanel && (
              <ExportPanel
                artifacts={session?.exported_artifacts || {}}
                onClose={() => setShowFilesPanel(false)}
              />
            )}
          </main>
        </>
      )}

      {/* 4. CLOSING & TEARDOWN MODAL */}
      <ClosingModal
        sessionId={sessionId}
        artifacts={session?.exported_artifacts || {}}
        isOpen={showClosingModal}
        onClose={() => setShowClosingModal(false)}
        onConfirmDelete={handleDeleteWorkspace}
        onStartNew={handleResetToStart}
      />

    </div>
  );
};

export default App;
