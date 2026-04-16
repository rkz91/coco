import { useQuery } from '@tanstack/react-query';
import { Shield, Scale, Lock, Layers, Building2, FileText, Users, Loader2, ArrowRight } from 'lucide-react';
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

interface AuditBoard {
  name: string;
  tagline: string;
  description: string;
  instances: { id: string; teams: string[]; modules: string[] }[];
  budget: { spend_2025: string; budget_2026: string; agreement: string };
  project_slugs: string[];
  teams_served: number;
  products_managed: number;
  article_count?: number;
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
  auditboard: AuditBoard | null;
  stakeholder_teams?: string[];
  error?: string;
}

const PROGRAM_ICONS: Record<string, React.ReactNode> = {
  'anti-corruption': <Shield className="h-5 w-5" />,
  'regulatory-compliance': <Scale className="h-5 w-5" />,
  'privacy': <Lock className="h-5 w-5" />,
  'optimize': <Layers className="h-5 w-5" />,
};

const PROGRAM_COLORS: Record<string, string> = {
  'anti-corruption': 'text-red-500',
  'regulatory-compliance': 'text-blue-500',
  'privacy': 'text-emerald-500',
  'optimize': 'text-amber-500',
};

function projectDisplayName(p: ProjectItem): string {
  if (p.description && p.description.length < 80) return p.description;
  return p.slug.replace(/-/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

interface ProgramDashboardProps {
  onSelectProgram: (programId: string) => void;
  onNavigateWiki: (project: string) => void;
}

export function ProgramDashboard({ onSelectProgram, onNavigateWiki }: ProgramDashboardProps) {
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

  const programs = programsData?.programs ?? [];
  const auditboard = programsData?.auditboard;
  const allProjects = (projectsData?.items ?? []).filter((p) => p.article_count > 0);

  return (
    <div className="p-4 overflow-y-auto h-full space-y-6">
      {/* Program Cards */}
      <div>
        <h2 className="text-lg font-semibold text-foreground mb-3">Programs</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {programs.map((prog) => (
            <button
              key={prog.id}
              onClick={() => onSelectProgram(prog.id)}
              className="text-left border border-border rounded-lg p-4 bg-card hover:border-accent/50 transition-colors cursor-pointer group"
            >
              <div className="flex items-center gap-3 mb-3">
                <span className={cn('shrink-0', PROGRAM_COLORS[prog.id] || 'text-foreground')}>
                  {PROGRAM_ICONS[prog.id] || <FileText className="h-5 w-5" />}
                </span>
                <div className="min-w-0">
                  <div className="font-semibold text-foreground text-sm">{prog.name}</div>
                  <div className="text-xs text-muted-foreground truncate">{prog.tagline}</div>
                </div>
                <ArrowRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity ml-auto shrink-0" />
              </div>

              {/* Metrics */}
              <div className="flex flex-wrap gap-1.5 mb-3">
                {prog.metrics.slice(0, 3).map((m, i) => (
                  <span key={i} className="text-[11px] bg-accent/5 px-2 py-0.5 rounded-full text-muted-foreground">
                    <span className="font-semibold text-foreground">{m.value}</span> {m.label}
                  </span>
                ))}
              </div>

              {/* Products */}
              <div className="text-xs text-muted-foreground mb-2 truncate">
                Products: {prog.products.slice(0, 4).join(', ')}
                {prog.products.length > 4 && ` +${prog.products.length - 4}`}
              </div>

              {/* Counts */}
              <div className="flex gap-4 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <FileText className="h-3 w-3" />
                  <span className="font-semibold text-foreground">{prog.article_count}</span> articles
                </span>
                <span className="flex items-center gap-1">
                  <Users className="h-3 w-3" />
                  <span className="font-semibold text-foreground">{prog.people_count}</span> people
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* AuditBoard Card */}
      {auditboard && (
        <div>
          <button
            onClick={() => onNavigateWiki('audit-board')}
            className="w-full text-left border border-border rounded-lg p-4 bg-card hover:border-accent/50 transition-colors cursor-pointer"
          >
            <div className="flex items-center gap-3 mb-2">
              <Building2 className="h-5 w-5 text-indigo-500 shrink-0" />
              <div>
                <div className="font-semibold text-foreground text-sm">AuditBoard Platform</div>
                <div className="text-xs text-muted-foreground">Cross-Cutting GRC Platform -- audit, risk, and compliance management</div>
              </div>
            </div>
            <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
              <span><span className="font-semibold text-foreground">2</span> instances (AB1 + AB2)</span>
              <span><span className="font-semibold text-foreground">4</span> modules</span>
              <span><span className="font-semibold text-foreground">{auditboard.teams_served}</span> teams served</span>
              <span><span className="font-semibold text-foreground">{auditboard.article_count ?? 0}</span> articles</span>
              <span>Budget: {auditboard.budget.budget_2026}</span>
            </div>
          </button>
        </div>
      )}

      {/* All Projects Grid */}
      <div>
        <h2 className="text-lg font-semibold text-foreground mb-3">All Projects</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          {allProjects
            .sort((a, b) => b.article_count - a.article_count)
            .map((proj) => (
              <button
                key={proj.slug}
                onClick={() => onNavigateWiki(proj.slug)}
                className="text-left border border-border rounded-md px-3 py-2.5 bg-card hover:border-accent/50 transition-colors cursor-pointer"
              >
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-foreground truncate">
                    {projectDisplayName(proj)}
                  </span>
                  <span className="text-xs text-muted-foreground whitespace-nowrap ml-2">
                    {proj.article_count} articles / {proj.entity_count} entities
                  </span>
                </div>
              </button>
            ))}
        </div>
      </div>
    </div>
  );
}
