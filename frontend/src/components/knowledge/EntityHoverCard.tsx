import { useState, useRef, useCallback, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import * as Popover from '@radix-ui/react-popover';
import { Network, ExternalLink, Loader2 } from 'lucide-react';
import { apiFetch } from '../../lib/api';
import { cn } from '../../lib/utils';

// ── Types ──────────────────────────────────────────────────────────────

interface GraphNeighbor {
  id: string;
  label: string;
  meta_type: string;
  relation: string;
  confidence: string;
}

interface NodeDetail {
  id: string;
  label: string;
  meta_type: string;
  degree: number;
  neighbors: GraphNeighbor[];
  [key: string]: unknown;
}

interface EntityHoverCardProps {
  entityGid: string;
  entityName: string;
  entityType: string;
  onEntityClick: (gid: string) => void;
  children: React.ReactNode;
}

// ── Type badge colors (matches WikiFilterBar entity types) ─────────────

const ENTITY_TYPE_COLORS: Record<string, string> = {
  person: 'bg-blue-500/20 text-blue-400',
  team: 'bg-purple-500/20 text-purple-400',
  system: 'bg-emerald-500/20 text-emerald-400',
  document: 'bg-amber-500/20 text-amber-400',
  role: 'bg-cyan-500/20 text-cyan-400',
  module: 'bg-orange-500/20 text-orange-400',
  org_unit: 'bg-pink-500/20 text-pink-400',
  project: 'bg-sky-500/20 text-sky-400',
};

function entityTypeBadgeClass(type: string): string {
  return ENTITY_TYPE_COLORS[type] ?? 'bg-muted-foreground/20 text-foreground';
}

// ── Component ──────────────────────────────────────────────────────────

export function EntityHoverCard({
  entityGid,
  entityName,
  entityType,
  onEntityClick,
  children,
}: EntityHoverCardProps) {
  const [isHovering, setIsHovering] = useState(false);
  const [shouldFetch, setShouldFetch] = useState(false);
  const hoverTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const leaveTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch node detail only after 300ms hover delay, cached for 5 min
  const { data: nodeDetail, isLoading } = useQuery({
    queryKey: ['graph-node-hover', entityGid],
    queryFn: () => apiFetch<NodeDetail>(`/graph/node/${encodeURIComponent(entityGid)}`),
    enabled: shouldFetch,
    staleTime: 5 * 60 * 1000,
  });

  const handleMouseEnter = useCallback(() => {
    // Cancel any pending leave
    if (leaveTimerRef.current) {
      clearTimeout(leaveTimerRef.current);
      leaveTimerRef.current = null;
    }
    hoverTimerRef.current = setTimeout(() => {
      setShouldFetch(true);
      setIsHovering(true);
    }, 300);
  }, []);

  const handleMouseLeave = useCallback(() => {
    if (hoverTimerRef.current) {
      clearTimeout(hoverTimerRef.current);
      hoverTimerRef.current = null;
    }
    // Small delay before closing to allow moving to the popover
    leaveTimerRef.current = setTimeout(() => {
      setIsHovering(false);
    }, 150);
  }, []);

  // Cleanup timers on unmount
  useEffect(() => {
    return () => {
      if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
      if (leaveTimerRef.current) clearTimeout(leaveTimerRef.current);
    };
  }, []);

  const topNeighbors = nodeDetail?.neighbors?.slice(0, 5) ?? [];

  return (
    <Popover.Root open={isHovering} onOpenChange={setIsHovering}>
      <Popover.Trigger asChild>
        <span
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
        >
          {children}
        </span>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          side="top"
          sideOffset={5}
          align="center"
          className="z-50 w-72 rounded-lg border border-border bg-card shadow-xl p-3 animate-in fade-in-0 zoom-in-95 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95"
          onMouseEnter={() => {
            // Keep popover open when hovering over it
            if (leaveTimerRef.current) {
              clearTimeout(leaveTimerRef.current);
              leaveTimerRef.current = null;
            }
          }}
          onMouseLeave={handleMouseLeave}
          onOpenAutoFocus={(e) => e.preventDefault()}
        >
          {/* Header */}
          <div className="flex items-start justify-between gap-2 mb-2">
            <div className="min-w-0">
              <h4 className="text-sm font-semibold text-foreground truncate">
                {entityName}
              </h4>
              <span
                className={cn(
                  'inline-block mt-0.5 px-1.5 py-0.5 rounded-full text-[10px] font-medium',
                  entityTypeBadgeClass(entityType),
                )}
              >
                {entityType}
              </span>
            </div>
            {nodeDetail && (
              <span className="text-[10px] text-muted-foreground whitespace-nowrap shrink-0">
                {nodeDetail.degree} connections
              </span>
            )}
          </div>

          {/* Loading */}
          {isLoading && (
            <div className="flex items-center justify-center py-3">
              <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
            </div>
          )}

          {/* Neighbors */}
          {topNeighbors.length > 0 && (
            <div className="mb-2">
              <p className="text-[10px] text-muted-foreground uppercase tracking-wider mb-1">
                Neighbors
              </p>
              <div className="space-y-0.5">
                {topNeighbors.map((n) => (
                  <button
                    key={n.id}
                    onClick={() => {
                      setIsHovering(false);
                      onEntityClick(n.id);
                    }}
                    className="w-full text-left flex items-center gap-1.5 px-1.5 py-0.5 rounded hover:bg-accent/10 transition-colors"
                  >
                    <span
                      className={cn(
                        'px-1 py-0 rounded text-[9px] font-medium shrink-0',
                        entityTypeBadgeClass(n.meta_type),
                      )}
                    >
                      {n.meta_type}
                    </span>
                    <span className="text-xs text-foreground truncate">{n.label}</span>
                    <span className="text-[9px] text-muted-foreground ml-auto shrink-0">
                      {n.relation}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="flex items-center gap-1.5 pt-2 border-t border-border">
            <button
              onClick={() => {
                setIsHovering(false);
                onEntityClick(entityGid);
              }}
              className="flex-1 flex items-center justify-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
            >
              <ExternalLink className="h-3 w-3" />
              Open Article
            </button>
            <button
              onClick={() => {
                setIsHovering(false);
                window.location.href = `/graph?focus=${encodeURIComponent(entityGid)}`;
              }}
              className="flex-1 flex items-center justify-center gap-1 px-2 py-1 rounded-md text-[11px] font-medium bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
            >
              <Network className="h-3 w-3" />
              View in Graph
            </button>
          </div>

          <Popover.Arrow className="fill-border" />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
