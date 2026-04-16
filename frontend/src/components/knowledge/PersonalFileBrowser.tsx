import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Search, Loader2, Plane, DollarSign, Scale, Heart, Briefcase, Home,
  FileText, X, ChevronRight, File, AlertCircle,
} from 'lucide-react';
import { apiFetch } from '../../lib/api';
import { cn } from '../../lib/utils';

interface PersonalFile {
  id: number;
  name: string;
  ext: string;
  file_path: string;
  file_type: string;
  file_size_bytes: number;
  char_count: number;
  extracted_at: string;
  preview: string;
  pages: number | null;
}

interface CategorySummary {
  summary: string | null;
  sections: { heading: string; content: string }[];
  gid: string;
}

interface FileCategory {
  slug: string;
  label: string;
  icon: string;
  file_count: number;
  summary: CategorySummary | null;
  files: PersonalFile[];
}

interface FilesResponse {
  categories: FileCategory[];
  total: number;
}

interface FileDetail {
  id: number;
  name: string;
  brain_slug: string;
  ext: string;
  file_path: string;
  file_type: string;
  file_size_bytes: number;
  char_count: number;
  extracted_at: string;
  pages: number | null;
  content_text: string;
  error?: string;
}

const CATEGORY_ICONS: Record<string, React.ReactNode> = {
  'Plane': <Plane className="h-4 w-4" />,
  'DollarSign': <DollarSign className="h-4 w-4" />,
  'Scale': <Scale className="h-4 w-4" />,
  'Heart': <Heart className="h-4 w-4" />,
  'Briefcase': <Briefcase className="h-4 w-4" />,
  'Home': <Home className="h-4 w-4" />,
};

const CATEGORY_COLORS: Record<string, string> = {
  'personal-immigration': 'text-blue-500',
  'personal-finance': 'text-emerald-500',
  'personal-legal': 'text-purple-500',
  'personal-medical': 'text-red-500',
  'personal-career': 'text-amber-500',
  'personal-housing': 'text-teal-500',
};

function formatSize(bytes: number): string {
  if (!bytes) return '--';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

const FILE_TYPE_COLORS: Record<string, string> = {
  pdf: 'bg-red-500/10 text-red-600',
  xlsx: 'bg-emerald-500/10 text-emerald-600',
  xls: 'bg-emerald-500/10 text-emerald-600',
  docx: 'bg-blue-500/10 text-blue-600',
  doc: 'bg-blue-500/10 text-blue-600',
  csv: 'bg-amber-500/10 text-amber-600',
  html: 'bg-purple-500/10 text-purple-600',
  msg: 'bg-indigo-500/10 text-indigo-600',
  eml: 'bg-indigo-500/10 text-indigo-600',
  txt: 'bg-zinc-500/10 text-zinc-600',
};

export function PersonalFileBrowser() {
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<{ slug: string; id: number } | null>(null);

  const params = new URLSearchParams();
  if (search) params.set('q', search);

  const { data, isLoading } = useQuery({
    queryKey: ['personal-files', search],
    queryFn: () => apiFetch<FilesResponse>(`/knowledge/personal/files?${params.toString()}`),
  });

  const { data: fileDetail, isLoading: detailLoading } = useQuery({
    queryKey: ['personal-file-detail', selectedFile?.slug, selectedFile?.id],
    queryFn: () =>
      apiFetch<FileDetail>(`/knowledge/personal/file/${selectedFile!.slug}/${selectedFile!.id}`),
    enabled: !!selectedFile,
  });

  const categories = data?.categories ?? [];
  const total = data?.total ?? 0;
  const visibleCategories = activeCategory
    ? categories.filter((c) => c.slug === activeCategory)
    : categories.filter((c) => c.file_count > 0);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (total === 0 && !search) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-muted-foreground text-sm gap-3">
        <AlertCircle className="h-8 w-8" />
        <p>No personal files found</p>
        <p className="text-xs">Personal brain databases not available at ~/Downloads/brains/</p>
      </div>
    );
  }

  return (
    <div className="flex h-full">
      {/* Main panel */}
      <div className={cn('flex-1 overflow-y-auto', selectedFile && 'max-w-[50%]')}>
        <div className="p-4 space-y-4">
          {/* Search + Category tabs */}
          <div className="space-y-3">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search files by name or content..."
                className="w-full pl-9 pr-3 py-2 bg-card border border-border rounded-lg text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-accent/20 focus:border-accent transition-colors"
              />
            </div>

            {/* Category tabs */}
            <div className="flex flex-wrap gap-1.5">
              <button
                onClick={() => setActiveCategory(null)}
                className={cn(
                  'px-3 py-1.5 text-xs font-medium rounded-full border transition-colors',
                  !activeCategory
                    ? 'bg-foreground text-background border-foreground'
                    : 'bg-card text-muted-foreground border-border hover:text-foreground',
                )}
              >
                All ({total})
              </button>
              {categories.filter((c) => c.file_count > 0).map((cat) => (
                <button
                  key={cat.slug}
                  onClick={() => setActiveCategory(activeCategory === cat.slug ? null : cat.slug)}
                  className={cn(
                    'px-3 py-1.5 text-xs font-medium rounded-full border transition-colors flex items-center gap-1.5',
                    activeCategory === cat.slug
                      ? 'bg-foreground text-background border-foreground'
                      : 'bg-card text-muted-foreground border-border hover:text-foreground',
                  )}
                >
                  <span className={cn(activeCategory === cat.slug ? '' : CATEGORY_COLORS[cat.slug])}>
                    {CATEGORY_ICONS[cat.icon] || <File className="h-3 w-3" />}
                  </span>
                  {cat.label} ({cat.file_count})
                </button>
              ))}
            </div>
          </div>

          {/* File count */}
          <div className="text-xs text-muted-foreground">
            {search ? `${total} matching files` : `${total} files across ${categories.filter((c) => c.file_count > 0).length} categories`}
          </div>

          {/* Categories */}
          {visibleCategories.map((cat) => (
            <div key={cat.slug} className="space-y-2">
              <h2 className="text-sm font-semibold text-foreground flex items-center gap-2 border-b border-border pb-1.5">
                <span className={CATEGORY_COLORS[cat.slug]}>
                  {CATEGORY_ICONS[cat.icon] || <File className="h-4 w-4" />}
                </span>
                {cat.label}
                <span className="text-xs font-normal text-muted-foreground">{cat.file_count} files</span>
              </h2>

              {/* Category summary */}
              {cat.summary?.summary && (
                <div className="rounded-lg bg-accent/5 border border-border p-3 text-xs text-muted-foreground leading-relaxed">
                  {cat.summary.summary}
                </div>
              )}

              {/* File list */}
              <div className="space-y-0.5">
                {cat.files.map((f) => (
                  <button
                    key={`${cat.slug}-${f.id}`}
                    onClick={() => setSelectedFile({ slug: cat.slug, id: f.id })}
                    className={cn(
                      'w-full text-left px-3 py-2 rounded-lg transition-colors flex items-center gap-3',
                      selectedFile?.slug === cat.slug && selectedFile?.id === f.id
                        ? 'bg-accent/10'
                        : 'hover:bg-accent/5',
                    )}
                  >
                    <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-medium text-foreground truncate">{f.name}</div>
                      <div className="text-xs text-muted-foreground truncate">{f.preview}</div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded uppercase', FILE_TYPE_COLORS[f.ext] || 'bg-zinc-500/10 text-zinc-600')}>
                        {f.ext}
                      </span>
                      <span className="text-[11px] text-muted-foreground">{formatSize(f.file_size_bytes)}</span>
                      <ChevronRight className="h-3 w-3 text-muted-foreground" />
                    </div>
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Detail panel */}
      {selectedFile && (
        <div className="flex-1 border-l border-border bg-card overflow-y-auto">
          {detailLoading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : fileDetail && !fileDetail.error ? (
            <div>
              {/* Header */}
              <div className="sticky top-0 bg-card border-b border-border px-4 py-3 flex items-center justify-between z-10">
                <h2 className="text-sm font-semibold text-foreground truncate">{fileDetail.name}</h2>
                <button
                  onClick={() => setSelectedFile(null)}
                  className="p-1.5 rounded-lg hover:bg-accent/10 text-muted-foreground hover:text-foreground transition-colors"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="p-4 space-y-4">
                {/* Metadata */}
                <div className="rounded-lg border border-border bg-accent/5 p-3">
                  <table>
                    <tbody className="text-xs">
                      <tr>
                        <td className="pr-3 py-1 text-muted-foreground font-medium whitespace-nowrap">Type</td>
                        <td className="py-1 text-foreground">{fileDetail.ext.toUpperCase()}</td>
                      </tr>
                      <tr>
                        <td className="pr-3 py-1 text-muted-foreground font-medium whitespace-nowrap">Size</td>
                        <td className="py-1 text-foreground">{formatSize(fileDetail.file_size_bytes)}</td>
                      </tr>
                      {fileDetail.pages && (
                        <tr>
                          <td className="pr-3 py-1 text-muted-foreground font-medium whitespace-nowrap">Pages</td>
                          <td className="py-1 text-foreground">{fileDetail.pages}</td>
                        </tr>
                      )}
                      <tr>
                        <td className="pr-3 py-1 text-muted-foreground font-medium whitespace-nowrap">Characters</td>
                        <td className="py-1 text-foreground">{fileDetail.char_count.toLocaleString()}</td>
                      </tr>
                      {fileDetail.extracted_at && (
                        <tr>
                          <td className="pr-3 py-1 text-muted-foreground font-medium whitespace-nowrap">Extracted</td>
                          <td className="py-1 text-foreground">{fileDetail.extracted_at.slice(0, 19).replace('T', ' ')}</td>
                        </tr>
                      )}
                      {fileDetail.file_path && (
                        <tr>
                          <td className="pr-3 py-1 text-muted-foreground font-medium whitespace-nowrap align-top">Path</td>
                          <td className="py-1 text-foreground break-all text-[10px]">{fileDetail.file_path}</td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Content */}
                <div>
                  <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">Extracted Content</h3>
                  <div className="text-sm text-foreground/90 leading-relaxed whitespace-pre-wrap bg-accent/5 border border-border rounded-lg p-4 max-h-[60vh] overflow-y-auto">
                    {fileDetail.content_text}
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center py-20">
              <p className="text-sm text-muted-foreground">File not found</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
