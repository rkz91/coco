import { useQuery } from '@tanstack/react-query';
import { Zap } from 'lucide-react';
import { apiFetch } from '../../lib/api';
import { cn } from '../../lib/utils';

interface ActionStats {
  staged: number;
  approved: number;
  rejected: number;
  total: number;
}

interface ActionBadgeProps {
  className?: string;
  onClick?: () => void;
}

/**
 * Small badge showing count of pending (staged) actions.
 * Designed to be placed on content list items or as an inline indicator.
 */
export function ActionBadge({ className, onClick }: ActionBadgeProps) {
  const { data: stats } = useQuery({
    queryKey: ['action-stats'],
    queryFn: () => apiFetch<ActionStats>('/actions/stats'),
    staleTime: 15_000,
  });

  const count = stats?.staged ?? 0;
  if (count === 0) return null;

  return (
    <button
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-medium',
        'bg-warning/10 text-warning hover:bg-warning/20 transition-colors',
        className,
      )}
      title={`${count} pending action${count !== 1 ? 's' : ''}`}
    >
      <Zap size={10} />
      {count}
    </button>
  );
}
