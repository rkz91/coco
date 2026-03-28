import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { apiFetch, apiPost } from '../../lib/api';

interface Replay {
  id: string;
  agent_id: string;
  title: string;
  duration: number | null;
  event_count: number | null;
  cost: number | null;
  files_changed: number | null;
  share_token: string | null;
  html_path: string | null;
  created_at: string;
}

interface ReplayListResponse {
  items: Replay[];
  count: number;
}

interface ReplayListProps {
  agentId: string;
}

function formatDuration(seconds: number | null): string {
  if (!seconds) return '--';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  const h = Math.floor(m / 60);
  const rm = m % 60;
  if (h) return `${h}h ${rm}m`;
  if (m) return `${m}m ${s}s`;
  return `${s}s`;
}

function formatCost(cost: number | null): string {
  if (!cost) return '$0.00';
  return `$${cost.toFixed(4)}`;
}

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit',
    });
  } catch {
    return iso;
  }
}

export function ReplayList({ agentId }: ReplayListProps) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery<ReplayListResponse>({
    queryKey: ['replays', agentId],
    queryFn: () => apiFetch(`/replays/?agent_id=${agentId}`),
  });

  const generateMutation = useMutation({
    mutationFn: () => apiPost<Replay>('/replays/', { agent_id: agentId }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['replays', agentId] });
    },
  });

  const copyShareLink = (token: string) => {
    const url = `${window.location.origin}/api/replays/share/${token}`;
    navigator.clipboard.writeText(url);
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <div className="h-6 w-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  const replays = data?.items ?? [];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-text2">Replays ({replays.length})</h3>
        <button
          onClick={() => generateMutation.mutate()}
          disabled={generateMutation.isPending}
          className="px-3 py-1.5 text-xs font-medium bg-accent text-white rounded-md hover:bg-accent/80 transition disabled:opacity-50"
        >
          {generateMutation.isPending ? 'Generating...' : 'Generate Replay'}
        </button>
      </div>

      {generateMutation.isError && (
        <p className="text-xs text-red-400">
          Failed to generate replay. Make sure the agent has output data.
        </p>
      )}

      {replays.length === 0 ? (
        <p className="text-xs text-text3 py-8 text-center">
          No replays yet. Run the agent first, then generate a replay.
        </p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
          {replays.map((replay) => (
            <div
              key={replay.id}
              className="bg-bg2 border border-border rounded-lg p-4 hover:border-accent/40 transition cursor-pointer group"
              onClick={() => navigate(`/replays/${replay.id}`)}
            >
              <div className="flex items-start justify-between mb-2">
                <h4 className="text-sm font-medium text-text truncate flex-1">
                  {replay.title}
                </h4>
              </div>

              <div className="text-xs text-text2 mb-3">
                {formatDate(replay.created_at)}
              </div>

              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>
                  <span className="text-text3">Duration</span>
                  <div className="text-text font-medium">{formatDuration(replay.duration)}</div>
                </div>
                <div>
                  <span className="text-text3">Events</span>
                  <div className="text-text font-medium">{replay.event_count ?? 0}</div>
                </div>
                <div>
                  <span className="text-text3">Cost</span>
                  <div className="text-text font-medium">{formatCost(replay.cost)}</div>
                </div>
                <div>
                  <span className="text-text3">Files</span>
                  <div className="text-text font-medium">{replay.files_changed ?? 0}</div>
                </div>
              </div>

              <div className="flex gap-2 mt-3 opacity-0 group-hover:opacity-100 transition">
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    navigate(`/replays/${replay.id}`);
                  }}
                  className="px-2 py-1 text-xs bg-accent/10 text-accent rounded hover:bg-accent/20 transition"
                >
                  View
                </button>
                {replay.share_token && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      copyShareLink(replay.share_token!);
                    }}
                    className="px-2 py-1 text-xs bg-green-500/10 text-green-400 rounded hover:bg-green-500/20 transition"
                  >
                    Share
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
