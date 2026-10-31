import React, { useEffect, useRef, useState } from 'react';
import { Terminal } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import '@xterm/xterm/css/xterm.css';
import { Terminal as TerminalIcon, RotateCcw, Maximize2, Minimize2, Circle, Play } from 'lucide-react';

interface TerminalViewProps {
  sessionId: string;
  onClose?: () => void;
}

export const TerminalView: React.FC<TerminalViewProps> = ({ sessionId }) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const terminalRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState<boolean>(false);
  const [isExpanded, setIsExpanded] = useState<boolean>(false);

  useEffect(() => {
    if (!containerRef.current) return;

    const term = new Terminal({
      cursorBlink: true,
      fontFamily: 'Menlo, Monaco, "Courier New", monospace',
      fontSize: 12,
      lineHeight: 1.25,
      theme: {
        background: '#070b14',
        foreground: '#e2e8f0',
        cursor: '#818cf8',
        selectionBackground: 'rgba(99, 102, 241, 0.35)',
        black: '#0f172a',
        red: '#f87171',
        green: '#4ade80',
        yellow: '#facc15',
        blue: '#60a5fa',
        magenta: '#c084fc',
        cyan: '#38bdf8',
        white: '#f1f5f9',
      },
      convertEol: true,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(containerRef.current);
    fitAddon.fit();

    terminalRef.current = term;
    fitAddonRef.current = fitAddon;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/terminal/${sessionId}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      setConnected(true);
      term.writeln('\x1b[32m✔ Connected to interactive container terminal.\x1b[0m\r\n');
      ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
    };

    ws.onmessage = (event) => {
      if (typeof event.data === 'string') {
        term.write(event.data);
      } else if (event.data instanceof ArrayBuffer) {
        term.write(new Uint8Array(event.data));
      }
    };

    ws.onclose = () => {
      setConnected(false);
      term.writeln('\r\n\x1b[33m⚡ Terminal session disconnected.\x1b[0m');
    };

    ws.onerror = () => {
      setConnected(false);
    };

    const onDataDispose = term.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(data);
      }
    });

    const resizeObserver = new ResizeObserver(() => {
      try {
        fitAddon.fit();
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'resize', cols: term.cols, rows: term.rows }));
        }
      } catch (e) {
        // ignore layout race
      }
    });

    resizeObserver.observe(containerRef.current);

    return () => {
      onDataDispose.dispose();
      resizeObserver.disconnect();
      ws.close();
      term.dispose();
    };
  }, [sessionId]);

  const sendQuickCommand = (cmd: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(cmd + '\n');
    }
  };

  const handleRestart = () => {
    if (wsRef.current) {
      wsRef.current.close();
    }
    if (terminalRef.current) {
      terminalRef.current.clear();
      terminalRef.current.writeln('\x1b[33mReconnecting to terminal...\x1b[0m');
    }
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/ws/terminal/${sessionId}`);
    wsRef.current = ws;
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      setConnected(true);
      if (terminalRef.current) {
        terminalRef.current.writeln('\x1b[32m✔ Reconnected.\x1b[0m\r\n');
        ws.send(JSON.stringify({
          type: 'resize',
          cols: terminalRef.current.cols,
          rows: terminalRef.current.rows,
        }));
      }
    };

    ws.onmessage = (event) => {
      if (terminalRef.current) {
        if (typeof event.data === 'string') {
          terminalRef.current.write(event.data);
        } else if (event.data instanceof ArrayBuffer) {
          terminalRef.current.write(new Uint8Array(event.data));
        }
      }
    };

    ws.onclose = () => setConnected(false);
  };

  return (
    <div
      className={`flex flex-col bg-[#070b14] border-t md:border-t-0 md:border-l border-slate-800/80 transition-all duration-300 shadow-2xl ${
        isExpanded ? 'w-full md:w-[680px]' : 'w-full md:w-[480px]'
      }`}
    >
      {/* Terminal Title Bar */}
      <div className="px-3.5 py-2 border-b border-slate-800/80 bg-slate-900/60 backdrop-blur-md flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <TerminalIcon className="w-3.5 h-3.5 text-indigo-400" />
          <span className="font-medium text-slate-200">Terminal</span>
          <div className="flex items-center gap-1.5 text-[11px] text-slate-400 ml-1.5">
            <Circle className={`w-2 h-2 ${connected ? 'text-emerald-400 fill-emerald-400 animate-pulse' : 'text-amber-400 fill-amber-400'}`} />
            <span className="font-mono text-[10px]">/workspace</span>
          </div>
        </div>

        {/* Quick action buttons & window controls */}
        <div className="flex items-center gap-1.5">
          <div className="hidden sm:flex items-center gap-1 mr-1 border-r border-slate-800 pr-2">
            <button
              onClick={() => sendQuickCommand('ls -la')}
              className="px-2 py-0.5 text-[10px] font-mono text-slate-400 hover:text-slate-200 bg-slate-800/70 hover:bg-slate-700/80 rounded transition active:scale-95"
            >
              ls
            </button>
            <button
              onClick={() => sendQuickCommand('docker ps')}
              className="px-2 py-0.5 text-[10px] font-mono text-slate-400 hover:text-slate-200 bg-slate-800/70 hover:bg-slate-700/80 rounded transition active:scale-95"
            >
              docker ps
            </button>
            <button
              onClick={() => sendQuickCommand('clear')}
              className="px-2 py-0.5 text-[10px] font-mono text-slate-400 hover:text-slate-200 bg-slate-800/70 hover:bg-slate-700/80 rounded transition active:scale-95"
            >
              clear
            </button>
          </div>

          <button
            onClick={handleRestart}
            title="Reconnect"
            className="p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded transition"
          >
            <RotateCcw className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            title={isExpanded ? 'Collapse width' : 'Expand width'}
            className="p-1 text-slate-400 hover:text-slate-200 hover:bg-slate-800 rounded transition"
          >
            {isExpanded ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* xterm canvas container */}
      <div className="flex-1 p-2.5 overflow-hidden" ref={containerRef} />
    </div>
  );
};
