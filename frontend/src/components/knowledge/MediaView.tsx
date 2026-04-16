import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Search, Image, FileText, Loader2, Tag, AlertCircle } from 'lucide-react';
import { apiFetch } from '../../lib/api';
import { cn } from '../../lib/utils';
import { timeAgo } from '../../lib/utils';

interface MediaItem {
  id: string;
  title: string;
  description: string;
  filename: string;
  file_path: string;
  asset_path: string;
  media_type: string;
  source: string;
  tags: string[];
  timestamp: string;
  score: number;
}

interface MediaResponse {
  items: MediaItem[];
  total: number;
  available: boolean;
}

const MEDIA_TYPE_COLORS: Record<string, string> = {
  image: 'bg-blue-500/10 text-blue-600',
  video: 'bg-purple-500/10 text-purple-600',
  audio: 'bg-amber-500/10 text-amber-600',
  document: 'bg-emerald-500/10 text-emerald-600',
};

function scoreColor(score: number): string {
  if (score >= 0.9) return 'text-success';
  if (score >= 0.7) return 'text-info';
  return 'text-muted-foreground';
}

export function MediaView() {
  const [search, setSearch] = useState('');

  const params = new URLSearchParams();
  if (search) params.set('q', search);
  params.set('limit', '20');

  const { data, isLoading } = useQuery({
    queryKey: ['media', { q: search }],
    queryFn: () => apiFetch<MediaResponse>(`/knowledge/media?${params.toString()}`),
    enabled: search.length > 0,
  });

  // If we got a response and media memory is not available
  if (data && !data.available) {
    return (
      <div className="flex flex-col h-full">
        <div className="flex flex-col items-center justify-center py-20 text-muted-foreground text-sm gap-3">
          <AlertCircle className="h-8 w-8" />
          <p>Media memory not configured</p>
          <p className="text-xs">Set up media-memory to search visual and file assets.</p>
        </div>
      </div>
    );
  }

  const items = data?.items ?? [];

  return (
    <div className="flex flex-col h-full">
      {/* Search bar */}
      <div className="px-4 py-3 border-b border-border">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search media assets by description or tags..."
            className="w-full pl-9 pr-3 py-2 bg-card border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors"
          />
        </div>
        {search && data && (
          <div className="mt-2 text-xs text-muted-foreground">
            {data.total} result{data.total !== 1 ? 's' : ''}
          </div>
        )}
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-20 text-muted-foreground text-sm gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            Searching media...
          </div>
        ) : !search ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground text-sm gap-3">
            <Image className="h-8 w-8" />
            <p>Search media assets by description or tags</p>
            <p className="text-xs">Enter a query above to find images, documents, and other files.</p>
          </div>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 text-muted-foreground text-sm gap-3">
            <Image className="h-8 w-8" />
            <p>No media found</p>
            <p className="text-xs">Try a different search term.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-4">
            {items.map((item) => {
              const Icon = item.media_type === 'image' ? Image : FileText;
              const typeBadgeClass = MEDIA_TYPE_COLORS[item.media_type] ?? 'bg-muted text-muted-foreground';
              return (
                <div
                  key={item.id}
                  className="flex gap-3 p-3 rounded-lg border border-border bg-card hover:bg-accent/5 transition-colors"
                >
                  {/* Icon placeholder */}
                  <div className="flex-shrink-0 w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
                    <Icon className="h-5 w-5 text-muted-foreground" />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-foreground truncate">
                        {item.filename}
                      </span>
                      <span className={cn('text-[10px] font-semibold', scoreColor(item.score))}>
                        {Math.round(item.score * 100)}%
                      </span>
                    </div>

                    {item.description && (
                      <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                        {item.description}
                      </p>
                    )}

                    <div className="flex items-center flex-wrap gap-1.5 mt-1.5">
                      {/* Media type badge */}
                      <span className={cn('px-1.5 py-0.5 rounded-full text-[10px] font-medium', typeBadgeClass)}>
                        {item.media_type}
                      </span>

                      {/* Tags */}
                      {item.tags.slice(0, 4).map((tag) => (
                        <span
                          key={tag}
                          className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-muted text-[10px] text-muted-foreground"
                        >
                          <Tag className="h-2.5 w-2.5" />
                          {tag}
                        </span>
                      ))}
                      {item.tags.length > 4 && (
                        <span className="text-[10px] text-muted-foreground">
                          +{item.tags.length - 4}
                        </span>
                      )}
                    </div>

                    {item.timestamp && (
                      <span className="text-[10px] text-muted-foreground/70 mt-1 block">
                        {timeAgo(item.timestamp)}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
