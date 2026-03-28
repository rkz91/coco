/**
 * DependencyGraph — Visual representation of todo dependency chains.
 * Uses CSS flexbox layout (no external libraries).
 * Displayed as a collapsible section on TodosPage.
 */

import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ChevronDown, ChevronRight, Lock, ArrowRight, Link2, Loader2 } from 'lucide-react';
import { apiFetch } from '../../lib/api';
import { cn } from '../../lib/utils';
import type { Todo } from './TodoList';

interface Dependency {
  id: string;
  todo_id: string;
  depends_on: string;
  dep_type: 'blocked_by' | 'related_to';
  created_at: string;
}

interface DependencyGraphProps {
  todos: Todo[];
}

interface ChainNode {
  id: string;
  title: string;
  status: string;
  blockedBy: string[];
  blocking: string[];
  related: string[];
}

function statusDot(status: string): string {
  switch (status) {
    case 'done': return 'bg-green-500';
    case 'in_progress': return 'bg-amber-500';
    case 'todo': return 'bg-blue-500';
    case 'archived': return 'bg-zinc-400';
    default: return 'bg-zinc-400';
  }
}

function DependencyChain({ rootId, nodes, todoMap }: {
  rootId: string;
  nodes: Map<string, ChainNode>;
  todoMap: Map<string, Todo>;
}) {
  const root = nodes.get(rootId);
  if (!root) return null;

  const todo = todoMap.get(rootId);
  const isBlocked = root.blockedBy.length > 0;

  return (
    <div className="flex items-stretch gap-0">
      {/* Blockers (left side) */}
      {root.blockedBy.length > 0 && (
        <div className="flex flex-col gap-1 items-end justify-center mr-0">
          {root.blockedBy.map((blockerId) => {
            const blocker = todoMap.get(blockerId);
            if (!blocker) return null;
            return (
              <div
                key={blockerId}
                className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-red-500/5 border border-red-500/20 text-xs"
              >
                <span className={cn('h-1.5 w-1.5 rounded-full shrink-0', statusDot(blocker.status))} />
                <span className="truncate max-w-[140px] text-muted-foreground">
                  {blocker.title}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Arrow from blockers */}
      {root.blockedBy.length > 0 && (
        <div className="flex items-center px-1">
          <div className="w-6 h-px bg-red-500/40" />
          <Lock className="h-3 w-3 text-red-500/60 shrink-0" />
          <div className="w-2 h-px bg-red-500/40" />
        </div>
      )}

      {/* Center: the todo itself */}
      <div
        className={cn(
          'flex items-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium min-w-[160px] max-w-[200px]',
          isBlocked
            ? 'border-red-500/30 bg-red-500/5'
            : 'border-border bg-card',
        )}
      >
        <span className={cn('h-2 w-2 rounded-full shrink-0', statusDot(todo?.status ?? ''))} />
        <span className="truncate">{root.title}</span>
      </div>

      {/* Arrow to things it blocks */}
      {root.blocking.length > 0 && (
        <div className="flex items-center px-1">
          <div className="w-2 h-px bg-blue-500/40" />
          <ArrowRight className="h-3 w-3 text-blue-500/60 shrink-0" />
          <div className="w-4 h-px bg-blue-500/40" />
        </div>
      )}

      {/* Things this blocks (right side) */}
      {root.blocking.length > 0 && (
        <div className="flex flex-col gap-1 items-start justify-center ml-0">
          {root.blocking.map((blockedId) => {
            const blocked = todoMap.get(blockedId);
            if (!blocked) return null;
            return (
              <div
                key={blockedId}
                className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-blue-500/5 border border-blue-500/20 text-xs"
              >
                <span className={cn('h-1.5 w-1.5 rounded-full shrink-0', statusDot(blocked.status))} />
                <span className="truncate max-w-[140px] text-muted-foreground">
                  {blocked.title}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Related (right-most, with link icon) */}
      {root.related.length > 0 && (
        <>
          <div className="flex items-center px-1">
            <div className="w-3 h-px bg-zinc-400/40" />
            <Link2 className="h-3 w-3 text-zinc-400 shrink-0" />
            <div className="w-3 h-px bg-zinc-400/40" />
          </div>
          <div className="flex flex-col gap-1 items-start justify-center">
            {root.related.map((relId) => {
              const rel = todoMap.get(relId);
              if (!rel) return null;
              return (
                <div
                  key={relId}
                  className="flex items-center gap-1.5 px-2 py-1 rounded-md bg-muted/50 border border-border text-xs"
                >
                  <span className={cn('h-1.5 w-1.5 rounded-full shrink-0', statusDot(rel.status))} />
                  <span className="truncate max-w-[140px] text-muted-foreground">
                    {rel.title}
                  </span>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}

export function DependencyGraph({ todos }: DependencyGraphProps) {
  const [expanded, setExpanded] = useState(false);

  const { data: allDeps = [], isLoading } = useQuery<Dependency[]>({
    queryKey: ['todo-dependencies-all'],
    queryFn: () => apiFetch<Dependency[]>('/todos/all-dependencies'),
    enabled: expanded,
    refetchInterval: 30000,
  });

  // Build graph data
  const { nodes, rootIds, todoMap } = useMemo(() => {
    const tMap = new Map<string, Todo>();
    for (const t of todos) {
      tMap.set(t.id, t);
    }

    const nodeMap = new Map<string, ChainNode>();

    // Only build nodes for todos that have dependencies
    const involvedIds = new Set<string>();
    for (const dep of allDeps) {
      involvedIds.add(dep.todo_id);
      involvedIds.add(dep.depends_on);
    }

    for (const id of involvedIds) {
      const todo = tMap.get(id);
      nodeMap.set(id, {
        id,
        title: todo?.title ?? '(unknown)',
        status: todo?.status ?? '',
        blockedBy: [],
        blocking: [],
        related: [],
      });
    }

    for (const dep of allDeps) {
      const fromNode = nodeMap.get(dep.todo_id);
      const toNode = nodeMap.get(dep.depends_on);
      if (!fromNode || !toNode) continue;

      if (dep.dep_type === 'blocked_by') {
        fromNode.blockedBy.push(dep.depends_on);
        toNode.blocking.push(dep.todo_id);
      } else {
        fromNode.related.push(dep.depends_on);
        // Don't double-add for bidirectional
        if (!toNode.related.includes(dep.todo_id)) {
          toNode.related.push(dep.todo_id);
        }
      }
    }

    // Root nodes: todos that have deps but are not exclusively blocked (show all involved)
    // Show each node that has at least one relationship
    const roots: string[] = [];
    for (const [id, node] of nodeMap) {
      // Show nodes that block something or are blocked by something
      if (node.blockedBy.length > 0 || node.blocking.length > 0 || node.related.length > 0) {
        // Only show as root if it's a "top-level" blocker (not blocked by anything) or has its own blockers
        // To avoid duplication, only show nodes that are blockers OR are blocked (but not shown as children)
        if (node.blockedBy.length > 0 || (node.blocking.length > 0 && node.blockedBy.length === 0)) {
          roots.push(id);
        }
      }
    }

    // If some nodes only have related_to links, add them too
    for (const [id, node] of nodeMap) {
      if (node.related.length > 0 && !roots.includes(id) && node.blockedBy.length === 0 && node.blocking.length === 0) {
        roots.push(id);
      }
    }

    return { nodes: nodeMap, rootIds: roots, todoMap: tMap };
  }, [todos, allDeps]);

  // Don't show section if no todos have dependencies
  const hasDeps = todos.some((t) => (t.blocked_by_count ?? 0) > 0 || (t.blocking_count ?? 0) > 0);

  if (!hasDeps && !expanded) return null;

  return (
    <div className="border border-border rounded-xl bg-card/50 overflow-hidden">
      {/* Collapsible header */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-4 py-2.5 text-sm font-medium text-foreground hover:bg-accent/30 transition-colors"
      >
        {expanded ? (
          <ChevronDown className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        )}
        <Lock className="h-3.5 w-3.5 text-muted-foreground" />
        Dependency Graph
        {hasDeps && (
          <span className="text-xs text-muted-foreground bg-muted/50 rounded-full px-2 py-0.5">
            {allDeps.length || '...'} links
          </span>
        )}
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="px-4 pb-4 pt-1 border-t border-border">
          {isLoading ? (
            <div className="flex items-center gap-2 py-4 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading dependencies...
            </div>
          ) : rootIds.length === 0 ? (
            <div className="text-sm text-muted-foreground py-4 text-center">
              No dependencies configured yet.
            </div>
          ) : (
            <div className="space-y-3 overflow-x-auto">
              {/* Legend */}
              <div className="flex items-center gap-4 text-[10px] text-muted-foreground pb-1 border-b border-border/50">
                <span className="flex items-center gap-1">
                  <Lock className="h-2.5 w-2.5 text-red-500" /> blocked by
                </span>
                <span className="flex items-center gap-1">
                  <ArrowRight className="h-2.5 w-2.5 text-blue-500" /> blocking
                </span>
                <span className="flex items-center gap-1">
                  <Link2 className="h-2.5 w-2.5 text-zinc-400" /> related
                </span>
                <span className="flex items-center gap-1.5 ml-auto">
                  <span className="h-1.5 w-1.5 rounded-full bg-green-500" /> done
                  <span className="h-1.5 w-1.5 rounded-full bg-amber-500" /> in progress
                  <span className="h-1.5 w-1.5 rounded-full bg-blue-500" /> todo
                  <span className="h-1.5 w-1.5 rounded-full bg-zinc-400" /> other
                </span>
              </div>

              {/* Chains */}
              {rootIds.map((rootId) => (
                <DependencyChain
                  key={rootId}
                  rootId={rootId}
                  nodes={nodes}
                  todoMap={todoMap}
                />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
