import React, { useState } from 'react';
import { 
  Download, 
  Trash2, 
  X, 
  Check, 
  FileCode, 
  BookOpen, 
  RotateCcw 
} from 'lucide-react';

interface ClosingModalProps {
  sessionId: string;
  artifacts: Record<string, string>;
  isOpen: boolean;
  onClose: () => void;
  onConfirmDelete: () => Promise<void>;
  onStartNew: () => void;
}

export const ClosingModal: React.FC<ClosingModalProps> = ({
  sessionId,
  artifacts,
  isOpen,
  onClose,
  onConfirmDelete,
  onStartNew,
}) => {
  const [deletedConfirmed, setDeletedConfirmed] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [downloaded, setDownloaded] = useState(false);

  if (!isOpen) return null;

  const handleDownloadBundle = () => {
    window.location.href = `/api/session/${sessionId}/download`;
    setDownloaded(true);
  };

  const handleDelete = async () => {
    try {
      setDeleting(true);
      await onConfirmDelete();
      setDeletedConfirmed(true);
    } catch (err) {
      console.error('Failed to delete workspace:', err);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm select-none font-mono text-xs">
      <div className="w-full max-w-lg bg-[#111318] border border-white/[0.08] rounded-xl shadow-2xl overflow-hidden text-slate-100 animate-in fade-in zoom-in-95 duration-100">
        
        {!deletedConfirmed ? (
          <div>
            {/* Header */}
            <div className="px-5 py-3.5 border-b border-white/[0.08] flex items-center justify-between bg-[#151922]">
              <h3 className="font-semibold text-white flex items-center gap-2">
                <Trash2 className="w-4 h-4 text-red-400" />
                <span>Teardown & Delete Session</span>
              </h3>
              <button
                onClick={onClose}
                className="p-1 text-slate-400 hover:text-white transition-colors rounded hover:bg-white/[0.04] cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Body */}
            <div className="p-5 space-y-4">
              <div className="space-y-1">
                <p className="font-semibold text-slate-200">
                  Ephemeral Container Destruction
                </p>
                <p className="text-slate-400 font-sans leading-relaxed text-xs">
                  Destroying this session deletes the isolated Docker container, internal volumes, and all temporary build artifacts. Download your generated Playbook bundle before continuing.
                </p>
              </div>

              {/* Artifacts Summary */}
              <div className="border border-white/[0.08] rounded-lg divide-y divide-white/[0.06] bg-[#0c0e14] overflow-hidden">
                <div className="p-2.5 flex items-center justify-between">
                  <span className="flex items-center gap-2 text-emerald-300">
                    <BookOpen className="w-3.5 h-3.5 text-emerald-400" />
                    PLAYBOOK.md
                  </span>
                  <span className="text-[10px] text-emerald-400 bg-emerald-500/10 border border-emerald-500/30 px-1.5 py-0.5 rounded">
                    verified runbook
                  </span>
                </div>
                {Object.keys(artifacts).filter(k => k !== 'PLAYBOOK.md').map((file) => (
                  <div
                    key={file}
                    className="p-2.5 flex items-center justify-between text-slate-300"
                  >
                    <span className="flex items-center gap-2">
                      <FileCode className="w-3.5 h-3.5 text-slate-500" />
                      {file}
                    </span>
                    <span className="text-[10px] text-zinc-500">manifest</span>
                  </div>
                ))}
              </div>

              {/* Download Bundle */}
              <button
                onClick={handleDownloadBundle}
                className={`w-full py-2 px-3 rounded-lg font-medium flex items-center justify-center gap-2 transition-colors cursor-pointer border ${
                  downloaded
                    ? 'bg-[#1e2433] text-emerald-400 border-emerald-500/30'
                    : 'bg-[#181d28] hover:bg-[#202736] text-white border-white/[0.12]'
                }`}
              >
                {downloaded ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-emerald-400" />
                    <span>Bundle downloaded (click to re-download)</span>
                  </>
                ) : (
                  <>
                    <Download className="w-3.5 h-3.5" />
                    <span>Download Playbook & Configs (.zip)</span>
                  </>
                )}
              </button>

              {/* Actions */}
              <div className="pt-2 border-t border-white/[0.06] flex items-center justify-end gap-2.5">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-3 py-1.5 rounded text-slate-400 hover:text-white hover:bg-white/[0.04] transition-colors cursor-pointer"
                >
                  Cancel
                </button>

                <button
                  type="button"
                  onClick={handleDelete}
                  disabled={deleting}
                  className="px-3.5 py-1.5 rounded bg-red-500/15 hover:bg-red-500/25 border border-red-500/30 text-red-400 text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer disabled:opacity-50"
                >
                  {deleting ? (
                    <>
                      <span className="inline-block h-2.5 w-2.5 animate-spin rounded-full border border-red-400 border-t-transparent" />
                      <span>Deleting...</span>
                    </>
                  ) : (
                    <>
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Confirm & Destroy</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        ) : (
          /* Confirmation */
          <div className="p-8 text-center space-y-4">
            <div className="w-10 h-10 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto text-emerald-400">
              <Check className="w-5 h-5" />
            </div>

            <div className="space-y-1">
              <h3 className="text-sm font-semibold text-white">
                Session Destroyed
              </h3>
              <p className="text-xs text-slate-400 font-sans max-w-sm mx-auto leading-relaxed">
                The container environment and temporary files have been permanently removed.
              </p>
            </div>

            <button
              onClick={onStartNew}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded bg-zinc-100 hover:bg-white text-zinc-950 text-xs font-mono font-medium transition-colors cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>New Session</span>
            </button>
          </div>
        )}

      </div>
    </div>
  );
};
