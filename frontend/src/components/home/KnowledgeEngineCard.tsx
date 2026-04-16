import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { BookOpen, Database, Network, Clock, ArrowRight, ChevronDown, ChevronUp } from 'lucide-react';
import { apiFetch } from '../../lib/api';
import { cn, timeAgo } from '../../lib/utils';

interface KnowledgeStats {
  available: boolean;
  articles: {
    total: number;
    perfect: number;
    high: number;
    medium: number;
    avg_confidence: number;
  };
  entities: {
    total: number;
    with_articles: number;
    coverage_pct: number;
  };
  projects: number;
  connections: number;
  last_generation: string | null;
  recent_24h_generated: number;
}

function ConfidenceBar({ perfect, high, medium, total }: { perfect: number; high: number; medium: number; total: number }) {
  if (total === 0) return null;
  const pPct = (perfect / total) * 100;
  const hPct = (high / total) * 100;
  const mPct = (medium / total) * 100;

  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden flex">
        <div
          className="bg-success transition-all"
          style={{ width: `${pPct}%` }}
          title={`${perfect} perfect (1.0)`}
        />
        <div
          className="bg-info transition-all"
          style={{ width: `${hPct}%` }}
          title={`${high} high (0.9)`}
        />
        <div
          className="bg-warning transition-all"
          style={{ width: `${mPct}%` }}
          title={`${medium} medium (0.8)`}
        />
      </div>
      <span className="text-[10px] text-muted-foreground whitespace-nowrap">
        {Math.round(pPct)}% perfect
      </span>
    </div>
  );
}

function Stat({ icon: Icon, label, value, sub }: { icon: React.ElementType; label: string; value: string | number; sub?: string }) {
  return (
    <div className="flex items-center gap-2">
      <Icon className="h-3.5 w-3.5 text-muted-foreground" />
      <div>
        <span className="text-sm font-medium text-foreground">{value}</span>
        <span className="text-xs text-muted-foreground ml-1">{label}</span>
        {sub && <span className="text-[10px] text-muted-foreground/70 ml-1">({sub})</span>}
      </div>
    </div>
  );
}

interface ProgramOverview {
  programs: Array<{
    id: string;
    name: string;
    article_count: number;
    people_count: number;
  }>;
  auditboard?: {
    article_count: number;
  };
}

const PROGRAM_EMOJI: Record<string, string> = {
  'anti-corruption': '\u{1F6E1}\uFE0F',
  'regulatory-compliance': '\u2696\uFE0F',
  'privacy': '\u{1F512}',
  'optimize': '\u{1F4CA}',
};

interface RecentArticle {
  gid: string;
  title: string;
  article_type: string;
  confidence: number;
  generated_at: string;
}

interface RecentArticlesResponse {
  items: RecentArticle[];
  total: number;
}

const TYPE_COLORS: Record<string, string> = {
  meeting: 'text-blue-400',
  cross_project: 'text-purple-400',
  decision_log: 'text-amber-400',
  memory_note: 'text-emerald-400',
  graph_insight: 'text-sky-400',
  project_summary: 'text-cyan-400',
  action_items: 'text-orange-400',
};

export function KnowledgeEngineCard() {
  const [expanded, setExpanded] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['knowledge-stats'],
    queryFn: () => apiFetch<KnowledgeStats>('/knowledge/stats'),
    refetchInterval: 60000,
  });

  const { data: recentData } = useQuery({
    queryKey: ['knowledge-recent'],
    queryFn: () => apiFetch<RecentArticlesResponse>('/knowledge/articles?limit=5&min_confidence=0'),
    enabled: expanded,
  });

  const { data: programsData } = useQuery({
    queryKey: ['knowledge-programs'],
    queryFn: () => apiFetch<ProgramOverview>('/knowledge/programs/overview'),
    refetchInterval: 60000,
  });

  if (isLoading) {
    return (
      <div className="rounded-xl border border-border bg-card p-4 animate-pulse">
        <div className="h-4 bg-muted rounded w-40 mb-3" />
        <div className="h-2 bg-muted rounded w-full mb-2" />
        <div className="h-3 bg-muted rounded w-24" />
      </div>
    );
  }

  if (!data?.available) return null;

  const { articles, entities, projects, connections, last_generation, recent_24h_generated } = data;

  return (
    <div className="rounded-xl border border-border bg-card p-4 space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BookOpen className="h-4 w-4 text-foreground" />
          <h3 className="text-sm font-semibold text-foreground">Knowledge Engine</h3>
          {recent_24h_generated > 0 && (
            <span className="text-[10px] bg-success/20 text-success px-1.5 py-0.5 rounded-full font-medium">
              +{recent_24h_generated} today
            </span>
          )}
        </div>
        <Link
          to="/knowledge?tab=wiki"
          className="text-xs text-muted-foreground hover:text-foreground flex items-center gap-1 transition-colors"
        >
          Browse <ArrowRight className="h-3 w-3" />
        </Link>
      </div>

      {/* Confidence bar */}
      <ConfidenceBar
        perfect={articles.perfect}
        high={articles.high}
        medium={articles.medium}
        total={articles.total}
      />

      {/* Stats row */}
      <div className="flex items-center gap-4 flex-wrap">
        <Stat icon={BookOpen} label="articles" value={articles.total.toLocaleString()} />
        <Stat
          icon={Database}
          label="coverage"
          value={`${entities.coverage_pct}%`}
          sub={`${entities.with_articles.toLocaleString()} / ${entities.total.toLocaleString()}`}
        />
        <Stat icon={Network} label="connections" value={connections.toLocaleString()} />
      </div>

      {/* Program pills */}
      {programsData?.programs && programsData.programs.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          {programsData.programs.map((prog) => (
            <Link
              key={prog.id}
              to={`/knowledge?tab=wiki&program=${prog.id}`}
              className="text-[11px] text-muted-foreground hover:text-foreground bg-muted/50 hover:bg-muted px-2 py-0.5 rounded-full transition-colors whitespace-nowrap"
            >
              {PROGRAM_EMOJI[prog.id] ?? ''} {prog.name} ({prog.article_count})
            </Link>
          ))}
        </div>
      )}

      {/* What's New (expandable) */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-1.5 text-[11px] text-muted-foreground hover:text-foreground transition-colors pt-1"
      >
        {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
        <span className="font-medium">What&apos;s New</span>
      </button>
      {expanded && recentData?.items && (
        <div className="space-y-1">
          {recentData.items.map((article) => (
            <Link
              key={article.gid}
              to={`/knowledge?tab=wiki`}
              className="flex items-center gap-2 px-2 py-1 rounded-lg hover:bg-accent/5 transition-colors"
            >
              <span className={cn('text-[10px] font-semibold w-16 shrink-0', TYPE_COLORS[article.article_type] || 'text-muted-foreground')}>
                {article.article_type.replace('_', ' ')}
              </span>
              <span className="text-xs text-foreground truncate flex-1">{article.title}</span>
              <span className="text-[10px] text-muted-foreground/60 shrink-0">{timeAgo(article.generated_at)}</span>
            </Link>
          ))}
        </div>
      )}

      {/* Footer */}
      <div className="flex items-center gap-3 text-[10px] text-muted-foreground/70 pt-1 border-t border-border/50">
        <span>{projects} projects indexed</span>
        {last_generation && (
          <span className="flex items-center gap-1">
            <Clock className="h-2.5 w-2.5" />
            Last gen: {timeAgo(last_generation)}
          </span>
        )}
        <span>Avg: {Math.round(articles.avg_confidence * 100)}% confidence</span>
        <Link to="/graph" className="ml-auto text-accent hover:text-foreground flex items-center gap-1 transition-colors">
          Graph <ArrowRight className="h-2.5 w-2.5" />
        </Link>
      </div>
    </div>
  );
}
