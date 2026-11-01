import React, { useState } from 'react';
import { X, Copy, Check, Download, FileCode, Printer, BookOpen } from 'lucide-react';

interface ExportPanelProps {
  artifacts: Record<string, string>;
  onClose: () => void;
}

export const ExportPanel: React.FC<ExportPanelProps> = ({ artifacts, onClose }) => {
  const fileNames = Object.keys(artifacts);
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
    <aside className="w-full md:w-[460px] border-l border-white/[0.08] bg-[#111318] flex flex-col h-full shadow-2xl z-20 font-mono text-xs select-none">
      <div className="h-11 px-4 border-b border-white/[0.08] flex items-center justify-between bg-[#151922]">
        <div className="flex items-center gap-2">
          {activeFile === 'PLAYBOOK.md' ? (
            <BookOpen className="w-4 h-4 text-emerald-400" />
          ) : (
            <FileCode className="w-4 h-4 text-sky-400" />
          )}
          <span className="font-semibold text-white tracking-tight uppercase text-[11px]">
            Playbook & Deliverables
          </span>
        </div>
        <button
          onClick={onClose}
          className="p-1 text-slate-400 hover:text-white rounded hover:bg-white/[0.04] transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {fileNames.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-6 text-center text-slate-500">
          <BookOpen className="w-8 h-8 text-zinc-600 mb-2 stroke-1" />
          <p className="text-xs text-slate-400 font-sans">No deliverables generated yet.</p>
          <p className="text-[11px] text-zinc-600 mt-1 font-sans">
            As commands are verified, the playbook and configs will populate here.
          </p>
        </div>
      ) : (
        <>
          <div className="flex border-b border-white/[0.08] bg-[#0c0e14] px-2 py-1.5 gap-1.5 overflow-x-auto">
            {fileNames.map((fname) => (
              <button
                key={fname}
                onClick={() => setSelectedFile(fname)}
                className={`px-2.5 py-1 text-xs font-mono rounded transition-colors flex items-center gap-1.5 cursor-pointer ${
                  activeFile === fname
                    ? 'bg-[#1e2433] text-white border border-white/[0.12] font-semibold'
                    : 'text-slate-400 hover:text-white hover:bg-white/[0.04]'
                }`}
              >
                {fname === 'PLAYBOOK.md' && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />}
                <span>{fname}</span>
              </button>
            ))}
          </div>

          <div className="flex-1 p-3 overflow-auto bg-[#090a0f]">
            <pre className="p-3 bg-[#111318] rounded-lg border border-white/[0.08] font-mono text-xs text-slate-200 h-full overflow-auto leading-relaxed whitespace-pre-wrap selection:bg-slate-700/50">
              {activeContent}
            </pre>
          </div>

          <div className="p-3 border-t border-white/[0.08] bg-[#151922] flex items-center justify-between gap-2">
            <span className="text-[10px] text-zinc-500 font-mono">
              {activeFile === 'PLAYBOOK.md' ? 'Grounded in [Verified] tags' : 'Ready to export'}
            </span>

            <div className="flex items-center gap-2">
              <button
                onClick={handlePrint}
                title="Print or export as PDF"
                className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono bg-[#181d28] hover:bg-[#202736] text-slate-300 hover:text-white rounded border border-white/[0.08] transition-colors cursor-pointer"
              >
                <Printer className="w-3.5 h-3.5" />
                <span>PDF / Print</span>
              </button>
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 px-2.5 py-1 text-xs font-mono bg-[#181d28] hover:bg-[#202736] text-slate-300 hover:text-white rounded border border-white/[0.08] transition-colors cursor-pointer"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                <span>{copied ? 'Copied' : 'Copy'}</span>
              </button>
              <button
                onClick={handleDownload}
                className="flex items-center gap-1.5 px-3 py-1 text-xs font-mono bg-zinc-100 hover:bg-white text-zinc-950 font-medium rounded transition-colors cursor-pointer"
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
