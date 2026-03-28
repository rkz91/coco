import { cn } from '../../lib/utils';
import type { AgentStatus } from '../../hooks/useAgentSSE';

interface AgentStatusBarProps {
  running: number;
  paused: number;
  idle: number;
  total: number;
  /** Optional live agent map from useAgentSSE — overrides the numeric counts when provided */
  liveAgents?: Map<string, AgentStatus>;
}

const dotColors: Record<string, string> = {
  running: 'bg-emerald-500',
  paused: 'bg-amber-500',
  idle: 'bg-muted-foreground/40',
};

export function AgentStatusBar({ running, paused, idle, total, liveAgents }: AgentStatusBarProps) {
  // If live SSE data is provided, derive counts from it
  let effectiveRunning = running;
  let effectivePaused = paused;
  let effectiveIdle = idle;
  let effectiveTotal = total;

  if (liveAgents && liveAgents.size > 0) {
    effectiveRunning = 0;
    effectivePaused = 0;
    effectiveIdle = 0;
    for (const agent of liveAgents.values()) {
      if (agent.status === 'running') effectiveRunning++;
      else if (agent.status === 'paused') effectivePaused++;
      else if (agent.status === 'idle') effectiveIdle++;
    }
    effectiveTotal = liveAgents.size;
  }

  const segments = [
    { label: 'running', count: effectiveRunning },
    { label: 'paused', count: effectivePaused },
    { label: 'idle', count: effectiveIdle },
  ];

  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <p className="text-sm font-medium text-muted-foreground uppercase tracking-wide mb-3">Agents</p>
      <div className="flex items-center gap-4 text-sm">
        <span className="text-foreground font-medium">{effectiveTotal} agent{effectiveTotal !== 1 ? 's' : ''}</span>
        {segments.map(({ label, count }) =>
          count > 0 ? (
            <span key={label} className="flex items-center gap-1.5 text-muted-foreground">
              <span className="relative flex h-2 w-2">
                {label === 'running' && (
                  <span className={cn('animate-ping absolute inline-flex h-full w-full rounded-full opacity-75', dotColors[label])} />
                )}
                <span className={cn('relative inline-flex rounded-full h-2 w-2', dotColors[label])} />
              </span>
              {count} {label}
            </span>
          ) : null,
        )}
        {effectiveTotal === 0 && <span className="text-muted-foreground">No agents</span>}
      </div>
    </div>
  );
}
