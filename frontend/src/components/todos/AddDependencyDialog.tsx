import { useState, useMemo } from 'react';
import * as Dialog from '@radix-ui/react-dialog';
import { X, Search, Link2, Lock, ArrowRight } from 'lucide-react';
import { cn } from '../../lib/utils';
import { apiPost } from '../../lib/api';
import type { Todo } from './TodoList';

interface AddDependencyDialogProps {
  todoId: string;
  allTodos: Todo[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onCreated: () => void;
}

export function AddDependencyDialog({
  todoId,
  allTodos,
  open,
  onOpenChange,
  onCreated,
}: AddDependencyDialogProps) {
  const [search, setSearch] = useState('');
  const [depType, setDepType] = useState<'blocked_by' | 'related_to'>('blocked_by');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const currentTodo = allTodos.find((t) => t.id === todoId);

  // Filter out the current todo and match search
  const filteredTodos = useMemo(() => {
    const q = search.toLowerCase().trim();
    return allTodos
      .filter((t) => t.id !== todoId)
      .filter((t) => {
        if (!q) return true;
        return t.title.toLowerCase().includes(q) || t.id.includes(q);
      })
      .slice(0, 20);
  }, [allTodos, todoId, search]);

  async function handleSelect(dependsOnId: string) {
    setSaving(true);
    setError(null);
    try {
      await apiPost(`/todos/${todoId}/dependencies`, {
        depends_on: dependsOnId,
        dep_type: depType,
      });
      onCreated();
      onOpenChange(false);
      setSearch('');
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setError(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/50 z-40" />
        <Dialog.Content className="fixed top-[15%] left-1/2 -translate-x-1/2 w-[480px] max-h-[70vh] flex flex-col bg-card border border-border rounded-xl shadow-xl z-50">
          {/* Header */}
          <div className="flex items-center justify-between px-4 py-3 border-b border-border">
            <Dialog.Title className="text-sm font-semibold">
              Add Dependency
            </Dialog.Title>
            <Dialog.Close className="p-1 rounded hover:bg-accent/50 text-muted-foreground">
              <X className="h-4 w-4" />
            </Dialog.Close>
          </div>

          {/* Current todo context */}
          {currentTodo && (
            <div className="px-4 py-2 border-b border-border bg-muted/30">
              <span className="text-xs text-muted-foreground">For: </span>
              <span className="text-xs font-medium">{currentTodo.title}</span>
            </div>
          )}

          {/* Dependency type selector */}
          <div className="flex gap-2 px-4 pt-3">
            <button
              onClick={() => setDepType('blocked_by')}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md border transition-colors',
                depType === 'blocked_by'
                  ? 'border-red-500/50 bg-red-500/10 text-red-500'
                  : 'border-border text-muted-foreground hover:text-foreground',
              )}
            >
              <Lock className="h-3 w-3" />
              Blocked By
            </button>
            <button
              onClick={() => setDepType('related_to')}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-md border transition-colors',
                depType === 'related_to'
                  ? 'border-blue-500/50 bg-blue-500/10 text-blue-500'
                  : 'border-border text-muted-foreground hover:text-foreground',
              )}
            >
              <Link2 className="h-3 w-3" />
              Related To
            </button>
          </div>

          {/* Search */}
          <div className="px-4 pt-3 pb-2">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search todos..."
                className="w-full pl-8 pr-3 py-2 text-sm bg-background border border-border rounded-md focus:outline-none focus:ring-1 focus:ring-ring"
                autoFocus
              />
            </div>
          </div>

          {/* Error message */}
          {error && (
            <div className="mx-4 mb-2 px-3 py-2 text-xs text-red-500 bg-red-500/10 rounded-md">
              {error}
            </div>
          )}

          {/* Results list */}
          <div className="flex-1 overflow-y-auto px-4 pb-3">
            {filteredTodos.length === 0 ? (
              <div className="text-xs text-muted-foreground text-center py-6">
                {search ? 'No matching todos' : 'No other todos available'}
              </div>
            ) : (
              <div className="space-y-1">
                {filteredTodos.map((todo) => (
                  <button
                    key={todo.id}
                    onClick={() => void handleSelect(todo.id)}
                    disabled={saving}
                    className={cn(
                      'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors',
                      'hover:bg-accent/50 disabled:opacity-50',
                    )}
                  >
                    <span
                      className={cn(
                        'h-2 w-2 rounded-full shrink-0',
                        todo.status === 'done' ? 'bg-green-500' :
                        todo.status === 'in_progress' ? 'bg-amber-500' :
                        'bg-zinc-400',
                      )}
                    />
                    <span className="flex-1 text-sm truncate">{todo.title}</span>
                    <span className="text-[10px] text-muted-foreground capitalize">{todo.status}</span>
                    {depType === 'blocked_by' ? (
                      <Lock className="h-3 w-3 text-red-400 shrink-0" />
                    ) : (
                      <ArrowRight className="h-3 w-3 text-blue-400 shrink-0" />
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
