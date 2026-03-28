import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch, apiPost, apiDelete, apiPatch } from '../../lib/api';
import { Clock, Webhook, FolderSearch, Trash2, Play, AlertCircle, Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';

export interface TriggerLogEntry {
  status: 'success' | 'failed';
  message?: string;
  fired_at: string;
}

export interface Trigger {
  id: string;
  name: string;
  trigger_type: 'cron' | 'webhook' | 'file_watch';
  enabled: boolean;
  config: Record<string, unknown>;
  action_type: 'spawn_agent' | 'create_todo' | 'notify' | 'run_command';
  action_config: Record<string, unknown>;
  last_fired_at: string | null;
  fire_count: number;
  last_log?: TriggerLogEntry | null;
  created_at: string;
  updated_at: string;
}

const typeIcons: Record<Trigger['trigger_type'], typeof Clock> = {
  cron: Clock,
  webhook: Webhook,
  file_watch: FolderSearch,
};

const typeBadgeColors: Record<Trigger['trigger_type'], string> = {
  cron: 'bg-blue-500/15 text-blue-400',
  webhook: 'bg-purple-500/15 text-purple-400',
  file_watch: 'bg-amber-500/15 text-amber-400',
};

interface TriggerListProps {
  onEdit?: (trigger: Trigger) => void;
}

export function TriggerList({ onEdit }: TriggerListProps) {
  const queryClient = useQueryClient();
  const [testResults, setTestResults] = useState<Record<string, { status: 'loading' | 'success' | 'error'; message?: string }>>({});

  const { data: triggers = [], isLoading } = useQuery<Trigger[]>({
    queryKey: ['triggers'],
    queryFn: () => apiFetch<Trigger[]>('/triggers'),
  });

  const toggleMut = useMutation({
    mutationFn: (t: Trigger) =>
      apiPatch<Trigger>(`/triggers/${t.id}`, { enabled: !t.enabled }),
    onMutate: async (t) => {
      await queryClient.cancelQueries({ queryKey: ['triggers'] });
      const previous = queryClient.getQueryData<Trigger[]>(['triggers']);
      queryClient.setQueryData<Trigger[]>(['triggers'], (old) =>
        old?.map((tr) => (tr.id === t.id ? { ...tr, enabled: !tr.enabled } : tr)) ?? [],
      );
      return { previous };
    },
    onError: (_err, _t, context) => {
      if (context?.previous) {
        queryClient.setQueryData(['triggers'], context.previous);
      }
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ['triggers'] }),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => apiDelete(`/triggers/${id}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['triggers'] }),
  });

  const handleTest = async (triggerId: string) => {
    setTestResults((prev) => ({ ...prev, [triggerId]: { status: 'loading' } }));
    try {
      const result = await apiPost<{ status: string; message?: string }>(`/triggers/${triggerId}/test`, {});
      setTestResults((prev) => ({
        ...prev,
        [triggerId]: { status: 'success', message: result.message ?? 'Test passed' },
      }));
    } catch (err) {
      setTestResults((prev) => ({
        ...prev,
        [triggerId]: { status: 'error', message: err instanceof Error ? err.message : 'Test failed' },
      }));
    }
    // Auto-clear result after 5s
    setTimeout(() => {
      setTestResults((prev) => {
        const next = { ...prev };
        delete next[triggerId];
        return next;
      });
    }, 5000);
  };

  if (isLoading) {
    return <p className="text-xs text-muted-foreground py-4">Loading triggers...</p>;
  }

  if (triggers.length === 0) {
    return (
      <p className="text-xs text-muted-foreground py-4">
        No triggers configured. Create one below.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {triggers.map((trigger) => {
        const Icon = typeIcons[trigger.trigger_type];
        const lastLogFailed = trigger.last_log?.status === 'failed';
        const testResult = testResults[trigger.id];
        return (
          <div key={trigger.id} className="space-y-0">
            <div
              className={cn(
                'flex items-center gap-3 px-3 py-2.5 rounded-lg border bg-card hover:bg-accent/30 transition-colors',
                lastLogFailed ? 'border-red-500/40' : 'border-border',
              )}
            >
              {/* Error dot + Icon + name */}
              <button
                type="button"
                onClick={() => onEdit?.(trigger)}
                className="flex items-center gap-3 flex-1 min-w-0 text-left"
              >
                <div className="relative shrink-0">
                  <Icon size={16} className="text-muted-foreground" />
                  {lastLogFailed && (
                    <span className="absolute -top-1 -right-1 h-2.5 w-2.5 rounded-full bg-red-500 ring-2 ring-card" />
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-foreground truncate">
                    {trigger.name}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    {trigger.last_fired_at
                      ? `Last fired ${new Date(trigger.last_fired_at).toLocaleString()} (${trigger.fire_count}x)`
                      : 'Never fired'}
                  </p>
                </div>
              </button>

              {/* Type badge */}
              <span
                className={cn(
                  'text-[10px] font-semibold uppercase px-1.5 py-0.5 rounded',
                  typeBadgeColors[trigger.trigger_type],
                )}
              >
                {trigger.trigger_type.replace('_', ' ')}
              </span>

              {/* Test button */}
              <button
                type="button"
                onClick={() => handleTest(trigger.id)}
                disabled={testResult?.status === 'loading'}
                className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium rounded-md bg-muted text-muted-foreground hover:bg-muted/80 hover:text-foreground transition-colors shrink-0 disabled:opacity-50"
                aria-label="Test trigger"
              >
                {testResult?.status === 'loading' ? (
                  <Loader2 size={12} className="animate-spin" />
                ) : (
                  <Play size={12} />
                )}
                Test
              </button>

              {/* Enabled toggle */}
              <button
                type="button"
                onClick={() => toggleMut.mutate(trigger)}
                className={cn(
                  'relative inline-flex h-5 w-9 items-center rounded-full transition-colors shrink-0',
                  trigger.enabled ? 'bg-accent' : 'bg-border',
                )}
                aria-label={trigger.enabled ? 'Disable trigger' : 'Enable trigger'}
              >
                <span
                  className={cn(
                    'inline-block h-3.5 w-3.5 transform rounded-full bg-card transition-transform',
                    trigger.enabled ? 'translate-x-[18px]' : 'translate-x-0.5',
                  )}
                />
              </button>

              {/* Delete */}
              <button
                type="button"
                onClick={() => deleteMut.mutate(trigger.id)}
                className="text-muted-foreground hover:text-destructive transition-colors shrink-0"
                aria-label="Delete trigger"
              >
                <Trash2 size={14} />
              </button>
            </div>

            {/* Error message from last failed log */}
            {lastLogFailed && trigger.last_log?.message && (
              <div className="flex items-start gap-2 px-3 py-1.5 ml-4 text-xs text-red-400">
                <AlertCircle size={12} className="shrink-0 mt-0.5" />
                <span>{trigger.last_log.message}</span>
              </div>
            )}

            {/* Inline test result */}
            {testResult && testResult.status !== 'loading' && (
              <div
                className={cn(
                  'flex items-start gap-2 px-3 py-1.5 ml-4 text-xs',
                  testResult.status === 'success' ? 'text-emerald-400' : 'text-red-400',
                )}
              >
                {testResult.status === 'success' ? (
                  <span className="shrink-0">&#10003;</span>
                ) : (
                  <AlertCircle size={12} className="shrink-0 mt-0.5" />
                )}
                <span>{testResult.message}</span>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
