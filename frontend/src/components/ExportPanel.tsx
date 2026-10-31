import React, { useState } from 'react';
import { X, Copy, Check, Download, FileCode, Printer, BookOpen } from 'lucide-react';

interface ExportPanelProps {
  artifacts: Record<string, string>;
  onClose: () => void;
}

export const ExportPanel: React.FC<ExportPanelProps> = ({ artifacts, onClose }) => {
  const fileNames = Object.keys(artifacts);
  // Default to PLAYBOOK.md if available, otherwise first file
  const defaultFile = fileNames.includes('PLAYBOOK.md') ? 'PLAYBOOK.md' : fileNames[0] || '';
  const [selectedFile, setSelectedFile] = useState<string>(defaultFile);
  const [copied, setCopied] = useState(false);

  const activeFile = (fileNames.includes(selectedFile) ? selectedFile : defaultFile);
  const activeContent = artifacts[activeFile] || '';

  const handleCopy = () => {
    navigator.clipboard.writeText(activeContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDownload = () => {
    const element = document.createElement('a');
    const file = new Blob([activeContent], { type: 'text/markdown;charset=utf-8' });
    element.href = URL.createObjectURL(file);
    element.download = activeFile;
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

  const handlePrint = () => {
    const printWindow = window.open('', '_blank');
    if (printWindow) {
      printWindow.document.write(`
        <html>
          <head>
            <title>${activeFile} - Deployment Playbook</title>
            <style>
              body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; padding: 40px; line-height: 1.6; color: #1e293b; max-width: 900px; margin: auto; }
              pre { background: #f1f5f9; padding: 16px; border-radius: 8px; overflow-x: auto; font-family: monospace; font-size: 13px; }
              table { width: 100%; border-collapse: collapse; margin: 16px 0; }
              th, td { border: 1px solid #cbd5e1; padding: 8px 12px; text-align: left; font-size: 13px; }
              th { background: #f8fafc; }
              h1, h2, h3 { color: #0f172a; }
            </style>
          </head>
          <body>
            <pre style="white-space: pre-wrap;">${activeContent.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</pre>
          </body>
        </html>
      `);
      printWindow.document.close();
      printWindow.focus();
      printWindow.print();
    }
  };

  return (
    <aside className="w-full md:w-[460px] border-l border-slate-800 bg-slate-900 flex flex-col h-full shadow-2xl z-20">
      <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/40">
        <div className="flex items-center gap-2">
          {activeFile === 'PLAYBOOK.md' ? (
            <BookOpen className="w-4 h-4 text-emerald-400" />
          ) : (
            <FileCode className="w-4 h-4 text-indigo-400" />
          )}
          <h2 className="text-xs font-semibold text-slate-100 uppercase tracking-wider">
            Verified Deliverables
          </h2>
        </div>
        <button
          onClick={onClose}
          className="p-1 text-slate-400 hover:text-slate-200 rounded hover:bg-slate-800 transition"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {fileNames.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-slate-500">
          <BookOpen className="w-8 h-8 text-slate-600 mb-2 stroke-1" />
          <p className="text-xs font-medium text-slate-400">Playbook and deployment files</p>
          <p className="text-[11px] text-slate-600 mt-1">
            As your container is tested, the verified playbook and configurations will compile here.
          </p>
        </div>
      ) : (
        <>
          <div className="flex border-b border-slate-800 bg-slate-950/60 px-2 py-1.5 gap-1.5 overflow-x-auto">
            {fileNames.map((fname) => (
              <button
                key={fname}
                onClick={() => setSelectedFile(fname)}
                className={`px-3 py-1 text-xs font-mono rounded-lg transition-all flex items-center gap-1.5 ${
                  activeFile === fname
                    ? fname === 'PLAYBOOK.md'
                      ? 'bg-emerald-950/80 text-emerald-400 border border-emerald-800/60 font-semibold'
                      : 'bg-slate-800 text-indigo-400 border border-slate-700 font-medium'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                }`}
              >
                {fname === 'PLAYBOOK.md' && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />}
                <span>{fname}</span>
              </button>
            ))}
          </div>

          <div className="flex-1 p-3 overflow-auto bg-[#070b14]">
            <pre className="p-3 bg-slate-950 rounded-xl border border-slate-800/80 font-mono text-xs text-slate-200 h-full overflow-auto leading-relaxed whitespace-pre-wrap selection:bg-indigo-500/30">
              {activeContent}
            </pre>
          </div>

          <div className="p-3 border-t border-slate-800 bg-slate-950 flex items-center justify-between gap-2">
            <span className="text-[11px] text-slate-500">
              {activeFile === 'PLAYBOOK.md' ? 'Grounded with [Verified] tags' : 'Ready to deploy'}
            </span>

            <div className="flex items-center gap-2">
              <button
                onClick={handlePrint}
                title="Print or Save as PDF"
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-700 transition"
              >
                <Printer className="w-3.5 h-3.5" />
                <span>PDF / Print</span>
              </button>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg border border-slate-700 transition"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
              <button
                onClick={handleDownload}
                className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg shadow-md transition"
              >
                <Download className="w-3.5 h-3.5" />
                <span>Download</span>
              </button>
            </div>
          </div>
        </>
      )}
    </aside>
  );
};
