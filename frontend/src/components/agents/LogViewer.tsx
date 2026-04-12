import { useEffect, useMemo, useRef } from 'react';
import { hasMermaidBlocks } from '../../lib/mermaid';
import { RichContent } from '../shared/RichContent';

interface LogViewerProps {
  logs: string[];
}

export function LogViewer({ logs }: LogViewerProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs.length]);

  const fullText = useMemo(() => logs.join('\n'), [logs]);
  const hasMermaid = useMemo(() => hasMermaidBlocks(fullText), [fullText]);

  return (
    <div className="rounded-xl bg-card border border-border overflow-hidden">
      <div className="max-h-[500px] overflow-y-auto p-4 font-mono text-sm leading-relaxed">
        {logs.length === 0 ? (
          <p className="text-muted-foreground italic">No output yet...</p>
        ) : hasMermaid ? (
          <RichContent text={fullText} mono />
        ) : (
          logs.map((line, i) => (
            <div key={i} className="text-foreground whitespace-pre-wrap break-all">
              {line}
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
