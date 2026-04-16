import { useQuery } from '@tanstack/react-query';
import { Shield, Scale, Lock, Layers, FileText, Users, ArrowLeft, Loader2, ExternalLink } from 'lucide-react';
import { apiFetch } from '../../lib/api';
import { cn } from '../../lib/utils';

interface ProgramMetric {
  label: string;
  value: string;
}

interface Program {
  id: string;
  name: string;
  tagline: string;
  icon: string;
  color: string;
  mission: string;
  products: string[];
  metrics: ProgramMetric[];
  systems: string[];
  project_slugs: string[];
  teams: string[];
  article_count: number;
  entity_count: number;
  people_count: number;
}

interface ProjectItem {
  slug: string;
  description: string | null;
  temperature: string | null;
  article_count: number;
  entity_count: number;
  avg_confidence: number;
}

interface ProgramsResponse {
  programs: Program[];
  auditboard: unknown;
  error?: string;
}

const PROGRAM_ICONS: Record<string, React.ReactNode> = {
  'anti-corruption': <Shield className="h-6 w-6" />,
  'regulatory-compliance': <Scale className="h-6 w-6" />,
  'privacy': <Lock className="h-6 w-6" />,
  'optimize': <Layers className="h-6 w-6" />,
};

const PROGRAM_COLORS: Record<string, string> = {
  'anti-corruption': 'text-red-500',
  'regulatory-compliance': 'text-blue-500',
  'privacy': 'text-emerald-500',
  'optimize': 'text-amber-500',
};

function projectDisplayName(slug: string, description: string | null): string {
  if (description && description.length < 80) return description;
  return slug.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

interface ProgramDetailProps {
  programId: string;
  onBack: () => void;
  onNavigateWiki: (project: string) => void;
}

export function ProgramDetail({ programId, onBack, onNavigateWiki }: ProgramDetailProps) {
  const { data: programsData, isLoading: programsLoading } = useQuery({
    queryKey: ['programs-overview'],
    queryFn: () => apiFetch<ProgramsResponse>('/knowledge/programs/overview'),
  });

  const { data: projectsData } = useQuery({
    queryKey: ['knowledge-projects'],
    queryFn: () => apiFetch<{ items: ProjectItem[] }>('/knowledge/projects'),
  });

  if (programsLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const prog = programsData?.programs?.find((p) => p.id === programId);
  if (!prog) {
    return (
      <div className="p-4">
        <button onClick={onBack} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4">
          <ArrowLeft className="h-4 w-4" /> Back to Programs
        </button>
        <p className="text-sm text-muted-foreground">Program not found.</p>
      </div>
    );
  }

  const allProjects = projectsData?.items ?? [];
  const programProjects = prog.project_slugs
    .map((slug) => allProjects.find((p) => p.slug === slug))
    .filter(Boolean) as ProjectItem[];

  return (
    <div className="p-4 overflow-y-auto h-full space-y-6">
      {/* Back button */}
      <button onClick={onBack} className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground transition-colors">
        <ArrowLeft className="h-4 w-4" /> Back to Programs
      </button>

      {/* Header */}
      <div className="flex items-start gap-4">
        <span className={cn('shrink-0 mt-1', PROGRAM_COLORS[prog.id] || 'text-foreground')}>
          {PROGRAM_ICONS[prog.id] || <FileText className="h-6 w-6" />}
        </span>
        <div>
          <h1 className="text-xl font-semibold text-foreground">{prog.name}</h1>
          <p className="text-sm text-muted-foreground">{prog.tagline}</p>
        </div>
      </div>

      {/* Mission */}
      <div className="border-l-2 border-accent/30 pl-3">
        <p className="text-sm text-foreground leading-relaxed italic">{prog.mission}</p>
      </div>

      {/* Key Metrics */}
      <div>
        <h2 className="text-sm font-semibold text-foreground mb-3 uppercase tracking-wider">Key Metrics</h2>
        <div className="flex flex-wrap gap-3">
          {prog.metrics.map((m, i) => (
            <div key={i} className="border border-border rounded-lg px-4 py-3 bg-card text-center min-w-[120px]">
              <div className="text-xl font-bold text-foreground">{m.value}</div>
              <div className="text-[11px] text-muted-foreground">{m.label}</div>
            </div>
          ))}
          <div className="border border-border rounded-lg px-4 py-3 bg-card text-center min-w-[120px]">
            <div className="text-xl font-bold text-foreground">{prog.article_count}</div>
            <div className="text-[11px] text-muted-foreground">Wiki Articles</div>
          </div>
          <div className="border border-border rounded-lg px-4 py-3 bg-card text-center min-w-[120px]">
            <div className="text-xl font-bold text-foreground">{prog.people_count}</div>
            <div className="text-[11px] text-muted-foreground">People</div>
          </div>
        </div>
      </div>

      {/* Products & Projects side by side */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Products */}
        <div className="border border-border rounded-lg bg-card">
          <div className="px-4 py-2.5 border-b border-border bg-accent/5 rounded-t-lg">
            <h3 className="text-sm font-semibold text-foreground">Products</h3>
          </div>
          <ul className="px-4 py-3 space-y-1.5">
            {prog.products.map((p) => (
              <li key={p} className="text-sm text-foreground">{p}</li>
            ))}
          </ul>
        </div>

        {/* Projects */}
        <div className="border border-border rounded-lg bg-card">
          <div className="px-4 py-2.5 border-b border-border bg-accent/5 rounded-t-lg">
            <h3 className="text-sm font-semibold text-foreground">Projects</h3>
          </div>
          <ul className="px-4 py-3 space-y-1.5">
            {programProjects.length > 0 ? (
              programProjects.map((proj) => (
                <li key={proj.slug} className="flex items-center justify-between">
                  <button
                    onClick={() => onNavigateWiki(proj.slug)}
                    className="text-sm text-foreground hover:text-accent transition-colors flex items-center gap-1"
                  >
                    {projectDisplayName(proj.slug, proj.description)}
                    <ExternalLink className="h-3 w-3 opacity-50" />
                  </button>
                  <span className="text-xs text-muted-foreground">
                    {proj.article_count} articles, {proj.entity_count} entities
                  </span>
                </li>
              ))
            ) : (
              prog.project_slugs.map((slug) => (
                <li key={slug}>
                  <button
                    onClick={() => onNavigateWiki(slug)}
                    className="text-sm text-foreground hover:text-accent transition-colors"
                  >
                    {slug.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
                  </button>
                </li>
              ))
            )}
          </ul>
        </div>
      </div>

      {/* Systems & Integrations */}
      <div>
        <h2 className="text-sm font-semibold text-foreground mb-2 uppercase tracking-wider">Systems & Integrations</h2>
        <div className="flex flex-wrap gap-2">
          {prog.systems.map((s) => (
            <span key={s} className="text-xs bg-accent/5 border border-border px-2.5 py-1 rounded-full text-foreground">
              {s}
            </span>
          ))}
        </div>
      </div>

      {/* Teams */}
      {prog.teams.length > 0 && (
        <div>
          <h2 className="text-sm font-semibold text-foreground mb-2 uppercase tracking-wider">Teams</h2>
          <div className="flex flex-wrap gap-2">
            {prog.teams.map((t) => (
              <span key={t} className="text-xs bg-accent/5 border border-border px-2.5 py-1 rounded-full text-foreground flex items-center gap-1">
                <Users className="h-3 w-3" /> {t}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
