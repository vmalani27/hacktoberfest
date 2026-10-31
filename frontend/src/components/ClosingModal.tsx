import React, { useState } from 'react';
import { 
  Download, 
  Trash2, 
  X, 
  Check, 
  AlertCircle, 
  FileCode, 
  BookOpen, 
  ShieldCheck, 
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
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md antialiased">
      <div className="w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden text-slate-100 animate-in fade-in zoom-in-95 duration-150">
        
        {!deletedConfirmed ? (
          <div>
            {/* Header */}
            <div className="px-5 py-4 border-b border-slate-800 flex items-center justify-between">
              <h3 className="text-sm font-semibold text-slate-100 flex items-center gap-2">
                <Trash2 className="w-4 h-4 text-rose-400" />
                <span>Close & Delete Workspace</span>
              </h3>
              <button
                onClick={onClose}
                className="p-1 text-slate-400 hover:text-slate-200 transition-colors rounded-lg hover:bg-slate-800"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Content Body */}
            <div className="p-5 space-y-5">
              <div className="space-y-1.5">
                <p className="text-xs font-semibold text-slate-200">
                  Disposable Sandbox Teardown
                </p>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Closing this workspace permanently destroys the container environment and all temporary files. Make sure to download your generated configuration bundle and Playbook before confirming.
                </p>
              </div>

              {/* Artifacts Summary */}
              <div className="border border-slate-800 rounded-xl divide-y divide-slate-800 text-xs font-mono bg-slate-950/60 overflow-hidden">
                <div className="p-3 flex items-center justify-between">
                  <span className="flex items-center gap-2 text-indigo-300 font-medium">
                    <BookOpen className="w-4 h-4 text-indigo-400" />
                    PLAYBOOK.md
                  </span>
                  <span className="text-[10px] text-indigo-400 bg-indigo-950/60 border border-indigo-800/40 px-2 py-0.5 rounded-full">
                    11-Section Verified
                  </span>
                </div>
                {Object.keys(artifacts).filter(k => k !== 'PLAYBOOK.md').map((file) => (
                  <div
                    key={file}
                    className="p-3 flex items-center justify-between"
                  >
                    <span className="flex items-center gap-2 text-slate-300">
                      <FileCode className="w-4 h-4 text-slate-400" />
                      {file}
                    </span>
                    <span className="text-[10px] text-slate-500">Generated</span>
                  </div>
                ))}
              </div>

              {/* Download Bundle Button */}
              <button
                onClick={handleDownloadBundle}
                className={`w-full py-2.5 px-4 rounded-xl text-xs font-semibold flex items-center justify-center gap-2 transition-all cursor-pointer shadow-md ${
                  downloaded
                    ? 'bg-slate-800 text-emerald-300 border border-emerald-500/30'
                    : 'bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white shadow-emerald-600/20'
                }`}
              >
                {downloaded ? (
                  <>
                    <Check className="w-4 h-4 text-emerald-400" />
                    <span>Bundle Downloaded (Click to re-download)</span>
                  </>
                ) : (
                  <>
                    <Download className="w-4 h-4" />
                    <span>Download Workspace ZIP Bundle</span>
                  </>
                )}
              </button>

              {/* Confirm Delete Action */}
              <div className="pt-2 border-t border-slate-800 flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={onClose}
                  className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-800 transition-colors cursor-pointer"
                >
                  Cancel
                </button>

                <button
                  type="button"
                  onClick={handleDelete}
                  disabled={deleting}
                  className="px-4 py-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-xs font-semibold flex items-center gap-1.5 transition-all shadow-md shadow-rose-600/20 cursor-pointer disabled:opacity-50"
                >
                  {deleting ? (
                    <>
                      <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      <span>Deleting...</span>
                    </>
                  ) : (
                    <>
                      <Trash2 className="w-3.5 h-3.5" />
                      <span>Destroy & Teardown</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        ) : (
          /* Deleted confirmation screen */
          <div className="p-8 text-center space-y-4">
            <div className="w-12 h-12 rounded-full bg-emerald-950/60 border border-emerald-500/40 flex items-center justify-center mx-auto text-emerald-400 shadow-inner">
              <Check className="w-6 h-6" />
            </div>

            <div className="space-y-1">
              <h3 className="text-base font-semibold text-slate-100">
                Workspace Successfully Destroyed
              </h3>
              <p className="text-xs text-slate-400 max-w-sm mx-auto leading-relaxed">
                The container environment, temporary files, and Docker volumes have been completely removed.
              </p>
            </div>

            <button
              onClick={onStartNew}
              className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-semibold shadow-md shadow-indigo-600/20 transition-all cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Start New Workspace</span>
            </button>
          </div>
        )}

      </div>
    </div>
  );
};
