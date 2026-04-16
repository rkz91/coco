import { useEffect, useState } from 'react';
import DOMPurify from 'dompurify';
import { Copy, Check, Maximize2, X, Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';

interface MermaidDiagramProps {
  code: string;
  className?: string;
}

/** Theme mapping: CoCo CSS variables → beautiful-mermaid options */
const THEME_OPTIONS = {
  bg: 'var(--background)',
  fg: 'var(--foreground)',
  accent: 'var(--accent)',
  muted: 'var(--muted-foreground)',
  surface: 'var(--card)',
  border: 'var(--border)',
  transparent: true,
} as const;

/**
 * Lazy-load beautiful-mermaid to keep elkjs (~1.5MB) out of the main bundle.
 * Only loaded when a mermaid diagram is actually rendered.
 */
let renderFn: ((code: string, opts: typeof THEME_OPTIONS) => string) | null = null;
let loadPromise: Promise<void> | null = null;

function loadRenderer(): Promise<void> {
  if (renderFn) return Promise.resolve();
  if (loadPromise) return loadPromise;
  loadPromise = import('beautiful-mermaid').then((mod) => {
    renderFn = mod.renderMermaidSVG;
  });
  return loadPromise;
}

export function MermaidDiagram({ code, className }: MermaidDiagramProps) {
  const [copied, setCopied] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<Error | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    loadRenderer()
      .then(() => {
        if (cancelled) return;
        try {
          const result = renderFn!(code, THEME_OPTIONS);
          setSvg(result);
        } catch (err) {
          setError(err instanceof Error ? err : new Error(String(err)));
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [code]);

  const sanitizedSvg = svg
    ? DOMPurify.sanitize(svg, { USE_PROFILES: { svg: true, svgFilters: true } })
    : '';

  const handleCopy = () => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  if (loading) {
    return (
      <div className={cn('my-2 rounded-xl border border-border bg-card p-6 flex items-center justify-center', className)}>
        <Loader2 size={16} className="animate-spin text-muted-foreground" />
        <span className="ml-2 text-xs text-muted-foreground">Rendering diagram...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className={cn('my-2 rounded-xl border border-border bg-card overflow-hidden', className)}>
        <div className="flex items-center gap-2 px-3 py-1.5 bg-destructive/10 border-b border-border">
          <span className="text-[10px] font-medium text-destructive">Diagram parsing failed</span>
        </div>
        <pre className="p-3 text-xs font-mono text-foreground/80 overflow-x-auto whitespace-pre-wrap">
          {code}
        </pre>
      </div>
    );
  }

  return (
    <>
      <div className={cn('relative group/mermaid my-2 rounded-xl border border-border bg-card overflow-hidden', className)}>
        {/* Action buttons */}
        <div className="absolute top-2 right-2 flex items-center gap-1 opacity-0 group-hover/mermaid:opacity-100 transition-opacity z-10">
          <button
            onClick={handleCopy}
            className="p-1.5 rounded-lg bg-card/80 backdrop-blur border border-border text-muted-foreground hover:text-foreground hover:bg-accent/20 transition-colors"
            title="Copy mermaid source"
          >
            {copied ? <Check size={12} /> : <Copy size={12} />}
          </button>
          <button
            onClick={() => setFullscreen(true)}
            className="p-1.5 rounded-lg bg-card/80 backdrop-blur border border-border text-muted-foreground hover:text-foreground hover:bg-accent/20 transition-colors"
            title="Fullscreen"
          >
            <Maximize2 size={12} />
          </button>
        </div>

        {/* Diagram */}
        <div
          className="mermaid-diagram p-4 overflow-x-auto"
          dangerouslySetInnerHTML={{ __html: sanitizedSvg }}
        />
      </div>

      {/* Fullscreen dialog */}
      {fullscreen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={() => setFullscreen(false)}
          onKeyDown={(e) => { if (e.key === 'Escape') setFullscreen(false); }}
          role="dialog"
          aria-modal="true"
          tabIndex={-1}
          ref={(el) => el?.focus()}
        >
          <div
            className="relative max-w-5xl max-h-[90vh] w-full m-4 bg-card rounded-2xl border border-border shadow-xl overflow-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={() => setFullscreen(false)}
              className="absolute top-3 right-3 p-1.5 rounded-lg bg-card border border-border text-muted-foreground hover:text-foreground hover:bg-accent/20 transition-colors z-10"
            >
              <X size={14} />
            </button>
            <div
              className="mermaid-diagram p-8"
              dangerouslySetInnerHTML={{ __html: sanitizedSvg }}
            />
          </div>
        </div>
      )}
    </>
  );
}
