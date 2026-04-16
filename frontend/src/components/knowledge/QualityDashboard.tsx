import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { apiFetch } from '../../lib/api';
import { cn } from '../../lib/utils';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface OverallStats {
  total_articles: number;
  avg_confidence: number | null;
  total_entities: number;
  entities_with_articles: number;
  entity_coverage_pct: number;
  orphan_entities: number;
}

interface ConfidenceBucket {
  range: string;
  count: number;
}

interface ConfidenceTrendDay {
  day: string;
  avg_conf: number;
  count: number;
}

interface ProjectScore {
  project_slug: string;
  article_count: number;
  avg_confidence: number;
  min_confidence: number;
  above_95: number;
}

interface ArticleTypeRow {
  article_type: string;
  count: number;
  avg_conf: number;
}

interface PipelineRun {
  id?: number;
  started_at?: string;
  finished_at?: string;
  projects_ok?: number;
  projects_err?: number;
  articles_generated?: number;
}

interface QualityDashboardData {
  overall: OverallStats;
  confidence_distribution: ConfidenceBucket[];
  confidence_trend: ConfidenceTrendDay[];
  project_scorecard: ProjectScore[];
  article_types: ArticleTypeRow[];
  pipeline_runs: PipelineRun[];
  error?: string;
}

// ---------------------------------------------------------------------------
// Article type color map (mirrors WikiFilterBar)
// ---------------------------------------------------------------------------

const TYPE_COLORS: Record<string, string> = {
  entity: 'bg-muted-foreground/30',
  meeting: 'bg-blue-500/30',
  cross_project: 'bg-purple-500/30',
  decision_log: 'bg-amber-500/30',
  memory_note: 'bg-emerald-500/30',
  project_summary: 'bg-cyan-500/30',
  digest: 'bg-rose-500/30',
  action_items: 'bg-orange-500/30',
  relationship: 'bg-pink-500/30',
  graph_insight: 'bg-sky-500/30',
};

const TYPE_LABELS: Record<string, string> = {
  entity: 'Entity',
  meeting: 'Meeting',
  cross_project: 'Cross-Project',
  decision_log: 'Decision',
  memory_note: 'Memory',
  project_summary: 'Summary',
  digest: 'Digest',
  action_items: 'Actions',
  relationship: 'Relationship',
  graph_insight: 'Graph Insight',
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function confidenceColor(v: number | null): string {
  if (v === null) return 'text-muted-foreground';
  if (v >= 0.95) return 'text-emerald-400';
  if (v >= 0.90) return 'text-amber-400';
  return 'text-red-400';
}

function confidenceBg(v: number | null): string {
  if (v === null) return 'bg-muted/30';
  if (v >= 0.95) return 'bg-emerald-500/10';
  if (v >= 0.90) return 'bg-amber-500/10';
  return 'bg-red-500/10';
}

function grade(avg: number): { letter: string; color: string } {
  if (avg >= 0.97) return { letter: 'A+', color: 'text-emerald-400' };
  if (avg >= 0.95) return { letter: 'A', color: 'text-emerald-400' };
  if (avg >= 0.90) return { letter: 'B', color: 'text-amber-400' };
  if (avg >= 0.85) return { letter: 'C', color: 'text-orange-400' };
  return { letter: 'D', color: 'text-red-400' };
}

function gradeRowBg(avg: number): string {
  if (avg >= 0.97) return 'bg-emerald-500/5';
  if (avg >= 0.95) return 'bg-emerald-500/[0.03]';
  if (avg >= 0.90) return 'bg-amber-500/5';
  if (avg >= 0.85) return 'bg-orange-500/5';
  return 'bg-red-500/5';
}

function pct(n: number, total: number): string {
  if (total === 0) return '0%';
  return `${Math.round((n / total) * 100)}%`;
}

type SortKey = 'project_slug' | 'article_count' | 'avg_confidence' | 'min_confidence' | 'above_95';

// ---------------------------------------------------------------------------
// Bucket colors for confidence distribution bar
// ---------------------------------------------------------------------------

const BUCKET_COLORS = [
  'bg-red-500',       // 0-50%
  'bg-orange-500',    // 50-70%
  'bg-amber-500',     // 70-85%
  'bg-yellow-400',    // 85-95%
  'bg-emerald-500',   // 95-100%
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function QualityDashboard() {
  const { data, isLoading, error } = useQuery<QualityDashboardData>({
    queryKey: ['knowledge', 'quality', 'dashboard'],
    queryFn: () => apiFetch('/api/knowledge/quality/dashboard'),
    refetchInterval: 60_000,
  });

  const [sortKey, setSortKey] = useState<SortKey>('avg_confidence');
  const [sortAsc, setSortAsc] = useState(true);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground text-sm">
        <svg className="animate-spin h-5 w-5 mr-2" viewBox="0 0 24 24">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        Loading quality metrics...
      </div>
    );
  }

  if (error || !data || data.error) {
    return (
      <div className="flex items-center justify-center h-64 text-red-400 text-sm">
        Failed to load quality dashboard{data?.error ? `: ${data.error}` : ''}
      </div>
    );
  }

  const { overall, confidence_distribution, project_scorecard, article_types, pipeline_runs } = data;
  const totalBucketArticles = confidence_distribution.reduce((s, b) => s + b.count, 0);

  // Sort scorecard
  const sortedProjects = [...project_scorecard].sort((a, b) => {
    const av = a[sortKey] ?? '';
    const bv = b[sortKey] ?? '';
    if (av < bv) return sortAsc ? -1 : 1;
    if (av > bv) return sortAsc ? 1 : -1;
    return 0;
  });

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortAsc(!sortAsc);
    } else {
      setSortKey(key);
      setSortAsc(key === 'project_slug');
    }
  };

  const maxTypeCount = article_types.length > 0 ? Math.max(...article_types.map((t) => t.count)) : 1;

  // Pipeline status
  const lastRun = pipeline_runs[0];
  const pipelineStatus = lastRun
    ? (lastRun.projects_err === 0 ? 'Healthy' : 'Degraded')
    : 'Unknown';
  const pipelineColor = lastRun
    ? (lastRun.projects_err === 0 ? 'text-emerald-400' : 'text-amber-400')
    : 'text-muted-foreground';

  return (
    <div className="space-y-6 p-4">
      {/* ----------------------------------------------------------------- */}
      {/* Section 1: Stat cards */}
      {/* ----------------------------------------------------------------- */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        {/* Total articles */}
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground mb-1">Total Articles</p>
          <p className="text-2xl font-semibold text-foreground">
            {overall.total_articles.toLocaleString()}
          </p>
        </div>

        {/* Avg confidence */}
        <div className={cn('rounded-xl border border-border p-4', confidenceBg(overall.avg_confidence))}>
          <p className="text-xs text-muted-foreground mb-1">Avg Confidence</p>
          <p className={cn('text-2xl font-semibold', confidenceColor(overall.avg_confidence))}>
            {overall.avg_confidence !== null
              ? `${(overall.avg_confidence * 100).toFixed(1)}%`
              : '--'}
          </p>
        </div>

        {/* Entity coverage */}
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground mb-1">Entity Coverage</p>
          <p className="text-2xl font-semibold text-foreground">
            {overall.entity_coverage_pct}%
          </p>
          <p className="text-[10px] text-muted-foreground mt-0.5">
            {overall.entities_with_articles} / {overall.total_entities} entities
          </p>
        </div>

        {/* Pipeline status */}
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-xs text-muted-foreground mb-1">Pipeline</p>
          <p className={cn('text-2xl font-semibold', pipelineColor)}>{pipelineStatus}</p>
          {lastRun?.started_at && (
            <p className="text-[10px] text-muted-foreground mt-0.5">
              Last: {lastRun.started_at.replace('T', ' ').slice(0, 16)}
            </p>
          )}
        </div>
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* Section 2: Confidence distribution bar */}
      {/* ----------------------------------------------------------------- */}
      <div className="rounded-xl border border-border bg-card p-4">
        <h3 className="text-xs font-medium text-muted-foreground mb-3">Confidence Distribution</h3>
        <div className="flex h-10 rounded-lg overflow-hidden">
          {confidence_distribution.map((bucket, i) => {
            const widthPct = totalBucketArticles > 0 ? (bucket.count / totalBucketArticles) * 100 : 0;
            if (widthPct === 0) return null;
            return (
              <div
                key={bucket.range}
                className={cn('flex items-center justify-center text-[10px] font-medium text-white transition-all', BUCKET_COLORS[i])}
                style={{ width: `${widthPct}%` }}
                title={`${bucket.range}: ${bucket.count} articles (${pct(bucket.count, totalBucketArticles)})`}
              >
                {widthPct > 8 && (
                  <span className="truncate px-1">
                    {bucket.count} ({pct(bucket.count, totalBucketArticles)})
                  </span>
                )}
              </div>
            );
          })}
        </div>
        {/* Legend */}
        <div className="flex gap-3 mt-2 flex-wrap">
          {confidence_distribution.map((bucket, i) => (
            <div key={bucket.range} className="flex items-center gap-1.5 text-[10px] text-muted-foreground">
              <span className={cn('inline-block w-2.5 h-2.5 rounded-sm', BUCKET_COLORS[i])} />
              {bucket.range}
              <span className="text-foreground/70">{bucket.count}</span>
            </div>
          ))}
        </div>
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* Section 3: Project scorecard */}
      {/* ----------------------------------------------------------------- */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="px-4 pt-4 pb-2">
          <h3 className="text-xs font-medium text-muted-foreground">Project Scorecard</h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-muted-foreground">
                {([
                  ['project_slug', 'Project'],
                  ['article_count', 'Articles'],
                  ['avg_confidence', 'Avg Conf'],
                  ['min_confidence', 'Min Conf'],
                  ['above_95', 'Above 95%'],
                ] as [SortKey, string][]).map(([key, label]) => (
                  <th
                    key={key}
                    onClick={() => handleSort(key)}
                    className="px-3 py-2 text-left font-medium cursor-pointer hover:text-foreground select-none"
                  >
                    {label}
                    {sortKey === key && (
                      <span className="ml-1">{sortAsc ? '\u2191' : '\u2193'}</span>
                    )}
                  </th>
                ))}
                <th className="px-3 py-2 text-left font-medium">Grade</th>
              </tr>
            </thead>
            <tbody>
              {sortedProjects.map((p) => {
                const g = grade(p.avg_confidence);
                return (
                  <tr key={p.project_slug} className={cn('border-b border-border/50', gradeRowBg(p.avg_confidence))}>
                    <td className="px-3 py-2 font-medium text-foreground">{p.project_slug}</td>
                    <td className="px-3 py-2 text-muted-foreground">{p.article_count}</td>
                    <td className={cn('px-3 py-2', confidenceColor(p.avg_confidence))}>
                      {(p.avg_confidence * 100).toFixed(1)}%
                    </td>
                    <td className={cn('px-3 py-2', confidenceColor(p.min_confidence))}>
                      {(p.min_confidence * 100).toFixed(1)}%
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">{p.above_95}</td>
                    <td className={cn('px-3 py-2 font-bold', g.color)}>{g.letter}</td>
                  </tr>
                );
              })}
              {sortedProjects.length === 0 && (
                <tr>
                  <td colSpan={6} className="px-3 py-6 text-center text-muted-foreground">
                    No project data available
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* ----------------------------------------------------------------- */}
      {/* Section 4: Article type breakdown */}
      {/* ----------------------------------------------------------------- */}
      <div className="rounded-xl border border-border bg-card p-4">
        <h3 className="text-xs font-medium text-muted-foreground mb-3">Article Type Breakdown</h3>
        <div className="space-y-2">
          {article_types.map((t) => {
            const barWidth = (t.count / maxTypeCount) * 100;
            const bgClass = TYPE_COLORS[t.article_type] ?? 'bg-muted-foreground/30';
            const label = TYPE_LABELS[t.article_type] ?? t.article_type;
            return (
              <div key={t.article_type} className="flex items-center gap-3">
                <span className="w-24 text-xs text-muted-foreground truncate shrink-0">{label}</span>
                <div className="flex-1 h-5 bg-muted/30 rounded overflow-hidden relative">
                  <div
                    className={cn('h-full rounded transition-all', bgClass)}
                    style={{ width: `${barWidth}%` }}
                  />
                  <span className="absolute inset-0 flex items-center px-2 text-[10px] font-medium text-foreground/80">
                    {t.count}
                  </span>
                </div>
                <span className={cn('w-14 text-right text-xs shrink-0', confidenceColor(t.avg_conf))}>
                  {(t.avg_conf * 100).toFixed(1)}%
                </span>
              </div>
            );
          })}
          {article_types.length === 0 && (
            <p className="text-xs text-muted-foreground text-center py-4">No article types found</p>
          )}
        </div>
      </div>
    </div>
  );
}

export default QualityDashboard;
