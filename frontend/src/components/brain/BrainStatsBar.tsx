import { useQuery } from '@tanstack/react-query';
import { Scale, Calendar, CheckSquare, Loader2 } from 'lucide-react';
import { apiFetch } from '../../lib/api';
import type { BrainStats } from '../../types/brain';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type BrainTab = 'decisions' | 'events' | 'tasks';

interface BrainStatsBarProps {
  onTabChange: (tab: BrainTab) => void;
  activeTab?: BrainTab;
}

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

function StatCard({
  icon: Icon,
  label,
  value,
  subtitle,
  active,
  onClick,
}: {
  icon: React.ElementType;
  label: string;
  value: number;
  subtitle?: string;
  active?: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`bg-card border rounded-lg p-4 text-left transition-colors cursor-pointer ${
        active
          ? 'border-accent ring-1 ring-accent/30'
          : 'border-border hover:border-muted-foreground/30'
      }`}
    >
      <div className="flex items-center gap-2 mb-1">
        <div className="flex items-center justify-center w-6 h-6 rounded-md bg-accent/10 text-accent">
          <Icon className="h-3.5 w-3.5" />
        </div>
        <span className="text-xs font-semibold text-muted-foreground tracking-wide uppercase">
          {label}
        </span>
      </div>
      <p className="text-xl font-bold text-foreground tabular-nums">
        {value.toLocaleString()}
      </p>
      {subtitle && (
        <p className="text-[11px] text-muted-foreground mt-0.5">{subtitle}</p>
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function StatsSkeleton() {
  return (
    <div className="grid grid-cols-3 gap-3 animate-pulse">
      {[1, 2, 3].map((i) => (
        <div key={i} className="bg-card border border-border rounded-lg p-4">
          <div className="flex items-center gap-2 mb-2">
            <div className="w-6 h-6 bg-muted rounded-md" />
            <div className="h-3 w-16 bg-muted rounded" />
          </div>
          <div className="h-6 w-12 bg-muted rounded" />
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function BrainStatsBar({ onTabChange, activeTab }: BrainStatsBarProps) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['brain-stats'],
    queryFn: () => apiFetch<BrainStats>('/brain/stats'),
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) return <StatsSkeleton />;

  if (error || !data?.available) {
    return (
      <div className="bg-card border border-border rounded-lg p-4 flex items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
        Brain stats unavailable
      </div>
    );
  }

  return (
    <div className="grid grid-cols-3 gap-3">
      <StatCard
        icon={Scale}
        label="Decisions"
        value={data.decisions}
        active={activeTab === 'decisions'}
        onClick={() => onTabChange('decisions')}
      />
      <StatCard
        icon={Calendar}
        label="Events"
        value={data.events}
        active={activeTab === 'events'}
        onClick={() => onTabChange('events')}
      />
      <StatCard
        icon={CheckSquare}
        label="Tasks"
        value={data.tasks.total}
        subtitle={`${data.tasks.open} open, ${data.tasks.done} done`}
        active={activeTab === 'tasks'}
        onClick={() => onTabChange('tasks')}
      />
    </div>
  );
}
