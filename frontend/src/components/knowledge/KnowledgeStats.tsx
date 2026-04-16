import { useQuery } from '@tanstack/react-query';
import { Database, FileText, Users, Search, Loader2 } from 'lucide-react';
import { apiFetch } from '../../lib/api';
import { cn } from '../../lib/utils';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface StatsResponse {
  available: boolean;
  articles: {
    total: number;
    by_type: Record<string, number>;
  };
  entities: {
    total: number;
    by_type: Record<string, number>;
  };
  projects: {
    total: number;
    with_articles: number;
  };
  fts_coverage: {
    articles_in_fts: number;
    total_articles: number;
  };
  message?: string;
  error?: string;
}

// ---------------------------------------------------------------------------
// Color maps — matches WikiFilterBar ARTICLE_TYPES
// ---------------------------------------------------------------------------

const ARTICLE_TYPE_COLORS: Record<string, { bar: string; label: string }> = {
  entity:          { bar: 'bg-muted-foreground/50', label: 'Entity' },
  product:         { bar: 'bg-teal-500',            label: 'Product' },
  meeting:         { bar: 'bg-blue-500',            label: 'Meeting' },
  cross_project:   { bar: 'bg-purple-500',          label: 'Cross-Project' },
  decision_log:    { bar: 'bg-amber-500',           label: 'Decision' },
  memory_note:     { bar: 'bg-emerald-500',         label: 'Memory' },
  project_summary: { bar: 'bg-cyan-500',            label: 'Summary' },
  digest:          { bar: 'bg-rose-500',             label: 'Digest' },
  action_items:    { bar: 'bg-orange-500',           label: 'Actions' },
  relationship:    { bar: 'bg-pink-500',             label: 'Relationship' },
  graph_insight:   { bar: 'bg-sky-500',              label: 'Graph Insight' },
};

const ENTITY_TYPE_COLORS: Record<string, { bar: string; label: string }> = {
  person:   { bar: 'bg-blue-500',    label: 'Person' },
  document: { bar: 'bg-amber-500',   label: 'Document' },
  team:     { bar: 'bg-emerald-500', label: 'Team' },
  role:     { bar: 'bg-purple-500',  label: 'Role' },
  system:   { bar: 'bg-cyan-500',    label: 'System' },
  module:   { bar: 'bg-orange-500',  label: 'Module' },
  product:  { bar: 'bg-teal-500',    label: 'Product' },
  org_unit: { bar: 'bg-pink-500',    label: 'Org Unit' },
};

// ---------------------------------------------------------------------------
// Breakdown bar — horizontal stacked segments
// ---------------------------------------------------------------------------

function BreakdownBar({
  items,
  total,
  colorMap,
}: {
  items: Record<string, number>;
  total: number;
  colorMap: Record<string, { bar: string; label: string }>;
}) {
  if (total === 0) return null;

  // Sort by count descending
  const sorted = Object.entries(items).sort(([, a], [, b]) => b - a);

  return (
    <div className="space-y-2">
      {/* Stacked bar */}
      <div className="flex h-2 rounded-full overflow-hidden bg-muted/30">
        {sorted.map(([type, count]) => {
          const pct = (count / total) * 100;
          if (pct < 0.3) return null; // skip tiny slivers
          const color = colorMap[type]?.bar ?? 'bg-muted-foreground/30';
          return (
            <div
              key={type}
              className={cn('h-full transition-all', color)}
              style={{ width: `${pct}%` }}
              title={`${colorMap[type]?.label ?? type}: ${count.toLocaleString()} (${pct.toFixed(1)}%)`}
            />
          );
        })}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-x-3 gap-y-1">
        {sorted.map(([type, count]) => {
          const meta = colorMap[type];
          const barColor = meta?.bar ?? 'bg-muted-foreground/30';
          const label = meta?.label ?? type;
          return (
            <div key={type} className="flex items-center gap-1.5">
              <span className={cn('w-2 h-2 rounded-full shrink-0', barColor)} />
              <span className="text-[11px] text-muted-foreground">
                {label}
              </span>
              <span className="text-[11px] font-medium text-foreground tabular-nums">
                {count.toLocaleString()}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

function StatCard({
  icon: Icon,
  title,
  value,
  subtitle,
  children,
}: {
  icon: React.ElementType;
  title: string;
  value: string | number;
  subtitle?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="bg-card border border-border rounded-xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex items-center justify-center w-6 h-6 rounded-md bg-accent/10 text-accent">
            <Icon className="h-3.5 w-3.5" />
          </div>
          <h3 className="text-xs font-semibold text-muted-foreground tracking-wide uppercase">
            {title}
          </h3>
        </div>
        <span className="text-xl font-bold text-foreground tabular-nums">
          {typeof value === 'number' ? value.toLocaleString() : value}
        </span>
      </div>
      {subtitle && (
        <p className="text-[11px] text-muted-foreground">{subtitle}</p>
      )}
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Skeleton
// ---------------------------------------------------------------------------

function StatsSkeleton() {
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 animate-pulse">
      {[1, 2, 3, 4].map((i) => (
        <div key={i} className="bg-card border border-border rounded-xl p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 bg-muted rounded-md" />
              <div className="h-3 w-20 bg-muted rounded" />
            </div>
            <div className="h-6 w-16 bg-muted rounded" />
          </div>
          <div className="h-2 w-full bg-muted rounded-full" />
          <div className="flex gap-3">
            <div className="h-3 w-16 bg-muted rounded" />
            <div className="h-3 w-16 bg-muted rounded" />
            <div className="h-3 w-16 bg-muted rounded" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function KnowledgeStats() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['knowledge-stats-full'],
    queryFn: () => apiFetch<StatsResponse>('/knowledge/stats/full'),
    staleTime: 5 * 60 * 1000,
  });

  if (isLoading) {
    return (
      <div className="space-y-2">
        <h3 className="text-xs font-semibold text-muted-foreground tracking-wide uppercase">
          Knowledge Overview
        </h3>
        <StatsSkeleton />
      </div>
    );
  }

  if (error || !data?.available) {
    return (
      <div className="bg-card border border-border rounded-xl p-4 flex items-center justify-center text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
        Knowledge stats unavailable
      </div>
    );
  }

  const ftsPct =
    data.fts_coverage.total_articles > 0
      ? Math.round(
          (data.fts_coverage.articles_in_fts / data.fts_coverage.total_articles) * 100,
        )
      : 0;

  return (
    <div className="space-y-2">
      <h3 className="text-xs font-semibold text-muted-foreground tracking-wide uppercase">
        Knowledge Overview
      </h3>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {/* Articles */}
        <StatCard
          icon={FileText}
          title="Articles"
          value={data.articles.total}
          subtitle={`${Object.keys(data.articles.by_type).length} types across all projects`}
        >
          <BreakdownBar
            items={data.articles.by_type}
            total={data.articles.total}
            colorMap={ARTICLE_TYPE_COLORS}
          />
        </StatCard>

        {/* Entities */}
        <StatCard
          icon={Users}
          title="Entities"
          value={data.entities.total}
          subtitle={`${Object.keys(data.entities.by_type).length} types tracked`}
        >
          <BreakdownBar
            items={data.entities.by_type}
            total={data.entities.total}
            colorMap={ENTITY_TYPE_COLORS}
          />
        </StatCard>

        {/* Project coverage */}
        <StatCard
          icon={Database}
          title="Projects"
          value={data.projects.total}
          subtitle={`${data.projects.with_articles} with articles`}
        >
          <div className="space-y-1">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-muted-foreground">Coverage</span>
              <span className="font-medium text-foreground tabular-nums">
                {data.projects.total > 0
                  ? Math.round((data.projects.with_articles / data.projects.total) * 100)
                  : 0}
                %
              </span>
            </div>
            <div className="h-1.5 rounded-full bg-muted/30 overflow-hidden">
              <div
                className="h-full rounded-full bg-accent transition-all"
                style={{
                  width: `${data.projects.total > 0 ? (data.projects.with_articles / data.projects.total) * 100 : 0}%`,
                }}
              />
            </div>
          </div>
        </StatCard>

        {/* FTS coverage */}
        <StatCard
          icon={Search}
          title="Search Index"
          value={`${ftsPct}%`}
          subtitle={`${data.fts_coverage.articles_in_fts.toLocaleString()} of ${data.fts_coverage.total_articles.toLocaleString()} articles indexed`}
        >
          <div className="space-y-1">
            <div className="flex items-center justify-between text-[11px]">
              <span className="text-muted-foreground">FTS5 Coverage</span>
              <span className="font-medium text-foreground tabular-nums">{ftsPct}%</span>
            </div>
            <div className="h-1.5 rounded-full bg-muted/30 overflow-hidden">
              <div
                className={cn(
                  'h-full rounded-full transition-all',
                  ftsPct >= 90 ? 'bg-emerald-500' : ftsPct >= 70 ? 'bg-amber-500' : 'bg-red-500',
                )}
                style={{ width: `${ftsPct}%` }}
              />
            </div>
          </div>
        </StatCard>
      </div>
    </div>
  );
}
