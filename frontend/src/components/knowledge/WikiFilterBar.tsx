import { X } from 'lucide-react';
import { cn } from '../../lib/utils';

const ARTICLE_TYPES = [
  { value: 'entity', label: 'Entity', color: 'bg-muted-foreground/20 text-foreground' },
  { value: 'product', label: 'Product', color: 'bg-teal-500/20 text-teal-400' },
  { value: 'meeting', label: 'Meeting', color: 'bg-blue-500/20 text-blue-400' },
  { value: 'cross_project', label: 'Cross-Project', color: 'bg-purple-500/20 text-purple-400' },
  { value: 'decision_log', label: 'Decision', color: 'bg-amber-500/20 text-amber-400' },
  { value: 'memory_note', label: 'Memory', color: 'bg-emerald-500/20 text-emerald-400' },
  { value: 'project_summary', label: 'Summary', color: 'bg-cyan-500/20 text-cyan-400' },
  { value: 'digest', label: 'Digest', color: 'bg-rose-500/20 text-rose-400' },
  { value: 'action_items', label: 'Actions', color: 'bg-orange-500/20 text-orange-400' },
  { value: 'relationship', label: 'Relationship', color: 'bg-pink-500/20 text-pink-400' },
  { value: 'graph_insight', label: 'Graph Insight', color: 'bg-sky-500/20 text-sky-400' },
];

const ENTITY_TYPES = [
  { value: '', label: 'All Types' },
  { value: 'person', label: 'Person' },
  { value: 'team', label: 'Team' },
  { value: 'system', label: 'System' },
  { value: 'product', label: 'Product' },
  { value: 'document', label: 'Document' },
  { value: 'role', label: 'Role' },
  { value: 'module', label: 'Module' },
  { value: 'org_unit', label: 'Org Unit' },
];

export interface WikiFilters {
  articleType: string;
  entityType: string;
  minConfidence: number;
  project?: string;
}

interface WikiFilterBarProps {
  filters: WikiFilters;
  onChange: (filters: WikiFilters) => void;
}

export function WikiFilterBar({ filters, onChange }: WikiFilterBarProps) {
  const activeCount =
    (filters.articleType ? 1 : 0) +
    (filters.entityType ? 1 : 0) +
    (filters.minConfidence > 0 ? 1 : 0) +
    (filters.project ? 1 : 0);

  const clearAll = () => onChange({ articleType: '', entityType: '', minConfidence: 0, project: '' });

  return (
    <div className="px-4 py-2 border-b border-border space-y-2">
      {/* Article type pills */}
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-[10px] text-muted-foreground mr-1">Type:</span>
        {ARTICLE_TYPES.map((t) => (
          <button
            key={t.value}
            aria-pressed={filters.articleType === t.value}
            onClick={() =>
              onChange({
                ...filters,
                articleType: filters.articleType === t.value ? '' : t.value,
              })
            }
            className={cn(
              'px-2 py-0.5 rounded-full text-[11px] font-medium transition-colors',
              filters.articleType === t.value
                ? t.color
                : 'bg-transparent text-muted-foreground/60 hover:text-muted-foreground',
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Active program filter pill */}
      {filters.project && (
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-muted-foreground mr-1">Program:</span>
          <button
            onClick={() => onChange({ ...filters, project: '' })}
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-accent/15 text-accent transition-colors"
          >
            {filters.project}
            <X className="h-3 w-3" />
          </button>
        </div>
      )}

      {/* Entity type + confidence row */}
      <div className="flex items-center gap-3">
        <select
          value={filters.entityType}
          onChange={(e) => onChange({ ...filters, entityType: e.target.value })}
          className="bg-card border border-border rounded-lg px-2 py-1 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-accent/20"
        >
          {ENTITY_TYPES.map((t) => (
            <option key={t.value} value={t.value}>{t.label}</option>
          ))}
        </select>

        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-muted-foreground">Min:</span>
          <input
            type="range"
            min={0}
            max={100}
            step={5}
            value={filters.minConfidence}
            onChange={(e) => onChange({ ...filters, minConfidence: Number(e.target.value) })}
            className="w-20 h-1 accent-accent"
          />
          <span className="text-[10px] text-muted-foreground w-8">
            {filters.minConfidence > 0 ? `${filters.minConfidence}%` : 'Any'}
          </span>
        </div>

        {activeCount > 0 && (
          <button
            onClick={clearAll}
            className="ml-auto flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="h-3 w-3" />
            Clear ({activeCount})
          </button>
        )}
      </div>
    </div>
  );
}

/** Get the badge color class for an article type */
export function articleTypeBadge(articleType: string): { label: string; className: string } {
  const found = ARTICLE_TYPES.find((t) => t.value === articleType);
  return found
    ? { label: found.label, className: found.color }
    : { label: articleType, className: 'bg-muted-foreground/20 text-foreground' };
}
