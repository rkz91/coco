import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, BookOpen, Loader2, User, Users, Monitor, FileText, Building2, Briefcase, Box, Package, Sparkles, Type } from 'lucide-react';
import { apiFetch } from '../../lib/api';
import { cn } from '../../lib/utils';

export interface WikiArticle {
  id: number;
  gid: string;
  title: string;
  summary: string | null;
  confidence: number;
  generated_at: string;
  article_type: string;
  entity_type: string | null;
  canonical_name: string | null;
  infobox_json?: string | null;
}

interface WikiArticlesResponse {
  items: WikiArticle[];
  total: number;
}

const ENTITY_ICONS: Record<string, React.ElementType> = {
  person: User,
  team: Users,
  system: Monitor,
  document: FileText,
  org_unit: Building2,
  role: Briefcase,
  module: Box,
  product: Package,
};

function confidenceColor(c: number): string {
  if (c >= 1.0) return 'text-success';
  if (c >= 0.9) return 'text-info';
  return 'text-warning';
}

function confidenceBg(c: number): string {
  if (c >= 1.0) return 'bg-success/10';
  if (c >= 0.9) return 'bg-info/10';
  return 'bg-warning/10';
}

import type { WikiFilters } from './WikiFilterBar';
import { articleTypeBadge } from './WikiFilterBar';

interface WikiArticleListProps {
  selectedGid: string | null;
  onSelect: (article: WikiArticle) => void;
  filters?: WikiFilters;
}

interface SemanticResult {
  id: string;
  gid: string;
  title: string;
  summary?: string;
  text?: string;
  snippet?: string;
  score: number;
  rrf_score?: number;
  confidence?: number;
  source: string;
  generated_at?: string;
}

interface SemanticResponse {
  items: SemanticResult[];
  total: number;
  mode?: string;
}

export function WikiArticleList({ selectedGid, onSelect, filters }: WikiArticleListProps) {
  const [search, setSearch] = useState('');
  const [offset, setOffset] = useState(0);
  const [searchMode, setSearchMode] = useState<'keyword' | 'semantic'>('keyword');
  const limit = 50;

  // Keyword search (existing FTS5)
  const keywordParams = new URLSearchParams();
  if (search) keywordParams.set('q', search);
  if (filters?.project) keywordParams.set('project', filters.project);
  if (filters?.articleType) keywordParams.set('article_type', filters.articleType);
  if (filters?.entityType) keywordParams.set('entity_type', filters.entityType);
  if (filters?.minConfidence) keywordParams.set('min_confidence', String(filters.minConfidence / 100));
  keywordParams.set('limit', String(limit));
  keywordParams.set('offset', String(offset));

  const { data, isLoading } = useQuery({
    queryKey: ['wiki-articles', { q: search, offset, ...filters }],
    queryFn: () => apiFetch<WikiArticlesResponse>(`/knowledge/articles?${keywordParams.toString()}`),
    enabled: searchMode === 'keyword',
  });

  // Semantic search (RRF merge)
  const semanticParams = new URLSearchParams();
  if (search) semanticParams.set('q', search);
  semanticParams.set('limit', String(limit));

  const { data: semanticData, isLoading: semanticLoading } = useQuery({
    queryKey: ['wiki-semantic', { q: search }],
    queryFn: () => apiFetch<SemanticResponse>(`/knowledge/semantic?${semanticParams.toString()}`),
    enabled: searchMode === 'semantic' && search.length > 0,
  });

  // Normalize semantic results to WikiArticle shape
  const semanticItems: WikiArticle[] = (semanticData?.items ?? []).map((r) => ({
    id: 0,
    gid: r.gid,
    title: r.title,
    summary: r.snippet || r.summary || r.text || null,
    confidence: r.confidence ?? 0.5,
    generated_at: r.generated_at ?? '',
    article_type: r.source === 'knowledge_semantic' ? 'semantic' : 'fts',
    entity_type: null,
    canonical_name: null,
    _rrf_score: r.rrf_score,
  } as WikiArticle & { _rrf_score?: number }));

  const isSearchActive = searchMode === 'semantic' && search.length > 0;
  const rawItems = isSearchActive ? semanticItems : (data?.items ?? []);
  const total = isSearchActive ? (semanticData?.total ?? 0) : (data?.total ?? 0);

  // Parse infobox team names once per data change, not on every render (M1 fix)
  const teamMap = useMemo(() => {
    const map = new Map<string, string>();
    for (const a of rawItems) {
      if (a.infobox_json) {
        try {
          const team = JSON.parse(a.infobox_json)?.team;
          if (typeof team === 'string') map.set(a.gid, team);
        } catch { /* skip */ }
      }
    }
    return map;
  }, [rawItems]);
  // Deduplicate by gid — backend may return the same article from multiple sources
  const items = useMemo(() => {
    const seen = new Set<string>();
    return rawItems.filter((a) => {
      if (seen.has(a.gid)) return false;
      seen.add(a.gid);
      return true;
    });
  }, [rawItems]);
  const loading = isSearchActive ? semanticLoading : isLoading;
  const page = Math.floor(offset / limit) + 1;
  const totalPages = Math.ceil(total / limit);

  return (
    <div className="flex flex-col h-full">
      {/* Search bar + mode toggle */}
      <div className="px-4 py-3 border-b border-border">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setOffset(0); }}
            placeholder={searchMode === 'semantic' ? 'Semantic search (conceptual)...' : 'Search wiki articles...'}
            className="w-full pl-9 pr-3 py-2 bg-card border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors"
          />
        </div>
        <div className="mt-2 flex items-center justify-between">
          <span className="text-xs text-muted-foreground">
            {total.toLocaleString()} article{total !== 1 ? 's' : ''}
            {searchMode === 'semantic' && search && semanticData?.mode && (
              <span className="ml-1 text-accent">({semanticData.mode})</span>
            )}
          </span>
          <div className="flex items-center gap-1 bg-card border border-border rounded-lg p-0.5">
            <button
              onClick={() => setSearchMode('keyword')}
              className={cn(
                'flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors',
                searchMode === 'keyword'
                  ? 'bg-accent/15 text-accent'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <Type className="h-3 w-3" />
              Keyword
            </button>
            <button
              onClick={() => setSearchMode('semantic')}
              className={cn(
                'flex items-center gap-1 px-2 py-1 rounded text-xs font-medium transition-colors',
                searchMode === 'semantic'
                  ? 'bg-accent/15 text-accent'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              <Sparkles className="h-3 w-3" />
              Semantic
            </button>
          </div>
        </div>
      </div>

      {/* Article list */}
      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex items-center justify-center py-20 text-muted-foreground text-sm gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            {searchMode === 'semantic' ? 'Searching semantically...' : 'Loading articles...'}
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground text-sm gap-3">
            <BookOpen className="h-8 w-8" />
            <p>No wiki articles found</p>
            <p className="text-xs">
              {search ? 'Try a different search term.' : 'The Knowledge Engine hasn\'t generated articles yet.'}
            </p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {items.map((article) => {
              const Icon = ENTITY_ICONS[article.entity_type ?? ''] ?? BookOpen;
              return (
                <button
                  key={article.gid}
                  onClick={() => onSelect(article)}
                  className={cn(
                    'w-full text-left px-4 py-3 hover:bg-accent/5 transition-colors',
                    selectedGid === article.gid && 'bg-accent/10 border-l-2 border-l-accent',
                  )}
                >
                  <div className="flex items-start gap-3">
                    <div className={cn('mt-0.5 p-1.5 rounded-lg', confidenceBg(article.confidence))}>
                      <Icon className="h-3.5 w-3.5 text-foreground" />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-foreground truncate">
                          {article.title}
                        </span>
                        <span className={cn('text-[10px] font-semibold', confidenceColor(article.confidence))}>
                          {Math.round(article.confidence * 100)}%
                        </span>
                      </div>
                      {article.summary && (
                        <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                          {article.summary}
                        </p>
                      )}
                      <div className="flex items-center gap-2 mt-1 text-[10px] text-muted-foreground/70">
                        {article.entity_type && <span>{article.entity_type}</span>}
                        {article.article_type && article.article_type !== 'entity' && (
                          <span className={cn('px-1.5 py-0.5 rounded-full font-medium', articleTypeBadge(article.article_type).className)}>
                            {articleTypeBadge(article.article_type).label}
                          </span>
                        )}
                        {teamMap.get(article.gid) && (
                          <span className="px-1.5 py-0.5 rounded-full bg-accent/15 text-accent font-medium">{teamMap.get(article.gid)}</span>
                        )}
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Pagination */}
      {total > limit && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-border text-sm text-muted-foreground">
          <span>Page {page} of {totalPages}</span>
          <div className="flex gap-2">
            <button
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - limit))}
              className={cn(
                'px-3 py-1.5 rounded-lg text-sm border border-border bg-card',
                offset === 0 ? 'opacity-40 cursor-not-allowed' : 'hover:bg-accent/50 text-foreground',
              )}
            >
              Previous
            </button>
            <button
              disabled={offset + limit >= total}
              onClick={() => setOffset(offset + limit)}
              className={cn(
                'px-3 py-1.5 rounded-lg text-sm border border-border bg-card',
                offset + limit >= total ? 'opacity-40 cursor-not-allowed' : 'hover:bg-accent/50 text-foreground',
              )}
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
