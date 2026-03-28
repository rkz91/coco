import { useNavigate } from 'react-router-dom';

interface ReplayPreviewProps {
  replay: {
    id: string;
    title: string;
    duration: number | null;
    event_count: number | null;
    cost: number | null;
    files_changed: number | null;
    created_at: string;
  };
}

function formatDuration(seconds: number | null): string {
  if (!seconds) return '--';
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  if (m) return `${m}m ${s}s`;
  return `${s}s`;
}

export function ReplayPreview({ replay }: ReplayPreviewProps) {
  const navigate = useNavigate();

  return (
    <div
      onClick={() => navigate(`/replays/${replay.id}`)}
      className="flex items-center gap-3 px-3 py-2 bg-bg2 border border-border rounded-lg hover:border-accent/40 cursor-pointer transition group"
    >
      {/* Play icon */}
      <div className="w-8 h-8 rounded-full bg-accent/10 flex items-center justify-center flex-shrink-0 group-hover:bg-accent/20 transition">
        <svg width="12" height="14" viewBox="0 0 12 14" fill="currentColor" className="text-accent ml-0.5">
          <path d="M0 0l12 7-12 7z" />
        </svg>
      </div>

      <div className="flex-1 min-w-0">
        <div className="text-sm text-text truncate">{replay.title}</div>
        <div className="flex gap-3 text-xs text-text3 mt-0.5">
          <span>{formatDuration(replay.duration)}</span>
          <span>{replay.event_count ?? 0} events</span>
          {replay.cost ? <span>${replay.cost.toFixed(4)}</span> : null}
          <span>{replay.files_changed ?? 0} files</span>
        </div>
      </div>

      <span className="text-xs text-text3 opacity-0 group-hover:opacity-100 transition">
        View &rarr;
      </span>
    </div>
  );
}
