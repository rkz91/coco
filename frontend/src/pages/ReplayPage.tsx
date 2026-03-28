import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { apiFetch, apiDelete } from '../lib/api';

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

export default function ReplayPage() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: replay, isLoading, error } = useQuery<Replay>({
    queryKey: ['replay', id],
    queryFn: () => apiFetch(`/replays/${id}`),
    enabled: !!id,
  });

  const deleteMutation = useMutation({
    mutationFn: () => apiDelete(`/replays/${id}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['replays'] });
      navigate(-1);
    },
  });

  const copyShareLink = () => {
    if (!replay?.share_token) return;
    const url = `${window.location.origin}/api/replays/share/${replay.share_token}`;
    navigator.clipboard.writeText(url).then(() => {
      alert('Share link copied to clipboard!');
    });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="h-8 w-8 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (error || !replay) {
    return (
      <div className="p-6">
        <p className="text-red-400">Replay not found.</p>
        <button onClick={() => navigate(-1)} className="text-accent mt-2 hover:underline">
          Go back
        </button>
      </div>
    );
  }

  const iframeUrl = `/api/replays/share/${replay.share_token}`;

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-border bg-bg2">
        <button
          onClick={() => navigate(-1)}
          className="text-sm text-text2 hover:text-text transition"
        >
          &larr; Back
        </button>
        <div className="flex-1" />
        <span className="text-xs text-text2">{replay.title}</span>
        <div className="flex-1" />
        {replay.share_token && (
          <button
            onClick={copyShareLink}
            className="px-3 py-1 text-xs bg-accent/10 text-accent rounded-md hover:bg-accent/20 transition"
          >
            Copy Share Link
          </button>
        )}
        <button
          onClick={() => {
            if (confirm('Delete this replay?')) deleteMutation.mutate();
          }}
          className="px-3 py-1 text-xs bg-red-500/10 text-red-400 rounded-md hover:bg-red-500/20 transition"
        >
          Delete
        </button>
      </div>

      {/* Replay iframe */}
      <div className="flex-1 relative">
        <iframe
          src={iframeUrl}
          title={replay.title}
          className="absolute inset-0 w-full h-full border-0"
          sandbox="allow-scripts"
        />
      </div>
    </div>
  );
}
