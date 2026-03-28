/**
 * BoardView — Generic kanban-style columnar layout.
 * Renders items grouped by state in columns. No drag-and-drop, just
 * transition buttons on each card.
 */

import { cn } from '../../lib/utils';
import {
  STATE_LABELS,
  STATE_COLORS,
} from '../../lib/state-machine';
import { TransitionButtons } from './TransitionButtons';
import { Lock } from 'lucide-react';

interface BoardItem {
  id: string;
  title: string;
  status: string;
  priority: string;
  owner?: string | null;
  agent_id?: string | null;
  due_date?: string | null;
  blocked_by_count?: number;
  blocking_count?: number;
}

interface BoardViewProps<T extends BoardItem> {
  items: T[];
  states: readonly string[];
  kind: 'todo' | 'task';
  onTransition: (id: string, toState: string) => void;
  isPending?: boolean;
  onSelect?: (item: T) => void;
}

const PRIORITY_DOT: Record<string, string> = {
  high: 'bg-red-500',
  medium: 'bg-amber-500',
  low: 'bg-zinc-400',
};

export function BoardView<T extends BoardItem>({
  items,
  states,
  kind,
  onTransition,
  isPending = false,
  onSelect,
}: BoardViewProps<T>) {
  // Group items by status
  const grouped = new Map<string, T[]>();
  for (const state of states) {
    grouped.set(state, []);
  }
  for (const item of items) {
    const bucket = grouped.get(item.status);
    if (bucket) {
      bucket.push(item);
    } else {
      // Legacy/unknown status — put in first column
      grouped.get(states[0])?.push(item);
    }
  }

  return (
    <div className="flex gap-3 overflow-x-auto pb-4 h-full">
      {states.map((state) => {
        const stateItems = grouped.get(state) ?? [];
        const colors = STATE_COLORS[state];

        return (
          <div
            key={state}
            className="flex flex-col min-w-[260px] max-w-[320px] flex-1 bg-muted/30 rounded-xl border border-border/50"
          >
            {/* Column header */}
            <div className="flex items-center gap-2 px-3 py-2.5 border-b border-border/50">
              <span
                className={cn(
                  'h-2.5 w-2.5 rounded-full shrink-0',
                  colors?.dot ?? 'bg-muted-foreground',
                )}
              />
              <span className="text-xs font-semibold text-foreground uppercase tracking-wide">
                {STATE_LABELS[state] ?? state}
              </span>
              <span className="ml-auto text-[10px] font-medium text-muted-foreground bg-muted/50 rounded-full px-1.5 py-0.5">
                {stateItems.length}
              </span>
            </div>

            {/* Cards */}
            <div className="flex-1 overflow-y-auto p-2 space-y-2">
              {stateItems.length === 0 ? (
                <div className="text-xs text-muted-foreground text-center py-6 opacity-50">
                  No items
                </div>
              ) : (
                stateItems.map((item) => {
                  const isBlocked = (item.blocked_by_count ?? 0) > 0;
                  return (
                    <div
                      key={item.id}
                      onClick={() => onSelect?.(item)}
                      className={cn(
                        'relative bg-card border rounded-lg p-3 space-y-2 transition-all',
                        'hover:shadow-sm hover:border-border/80',
                        onSelect && 'cursor-pointer',
                        isBlocked ? 'border-red-500/30' : 'border-border',
                      )}
                    >
                      {/* Lock icon overlay for blocked todos */}
                      {isBlocked && (
                        <div className="absolute top-1.5 right-1.5 flex items-center gap-1 px-1.5 py-0.5 rounded bg-red-500/10" title={`Blocked by ${item.blocked_by_count} todo(s)`}>
                          <Lock className="h-3 w-3 text-red-500" />
                          <span className="text-[9px] font-semibold text-red-500">{item.blocked_by_count}</span>
                        </div>
                      )}

                      {/* Title + priority dot */}
                      <div className="flex items-start gap-2">
                        <span
                          className={cn(
                            'h-2 w-2 rounded-full mt-1 shrink-0',
                            PRIORITY_DOT[item.priority] ?? 'bg-zinc-400',
                          )}
                          title={`${item.priority} priority`}
                        />
                        <span className={cn('text-sm text-foreground line-clamp-2', isBlocked && 'pr-8')}>{item.title}</span>
                      </div>

                      {/* Dependency badges */}
                      {((item.blocked_by_count ?? 0) > 0 || (item.blocking_count ?? 0) > 0) && (
                        <div className="flex items-center gap-1.5">
                          {(item.blocking_count ?? 0) > 0 && (
                            <span className="flex items-center gap-0.5 text-[9px] font-medium text-blue-500 bg-blue-500/10 px-1.5 py-0.5 rounded">
                              Blocking {item.blocking_count}
                            </span>
                          )}
                        </div>
                      )}

                      {/* Meta row */}
                      <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
                        {item.owner && <span>{item.owner}</span>}
                        {item.due_date && (
                          <span>
                            {new Date(item.due_date).toLocaleDateString(undefined, {
                              month: 'short',
                              day: 'numeric',
                            })}
                          </span>
                        )}
                      </div>

                      {/* Transition buttons */}
                      <TransitionButtons
                        currentState={item.status}
                        kind={kind}
                        onTransition={(toState) => onTransition(item.id, toState)}
                        isPending={isPending}
                        size="sm"
                      />
                    </div>
                  );
                })
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
