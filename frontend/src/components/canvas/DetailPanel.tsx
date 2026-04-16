import { useNavigate } from 'react-router-dom';
import {
  X, User, Users, Monitor, FileText, Briefcase, Box, Building2, Waypoints,
  BookOpen, Network, ChevronRight,
} from 'lucide-react';
import { cn } from '../../lib/utils';

interface Neighbor {
  id: string;
  label: string;
  meta_type: string;
  relation: string;
  confidence: string;
}

interface NodeDetailData {
  id: string;
  label: string;
  meta_type: string;
  degree: number;
  community?: number;
  neighbors: Neighbor[];
  source_file?: string;
  meta_projects?: string;
  [key: string]: unknown;
}

interface DetailPanelProps {
  nodeDetail: NodeDetailData | null;
  isLoading: boolean;
  onClose: () => void;
  onFocusNode: (nodeId: string) => void;
}

const TYPE_ICONS: Record<string, React.ElementType> = {
  person: User,
  team: Users,
  system: Monitor,
  document: FileText,
  role: Briefcase,
  org_unit: Building2,
  module: Box,
  project: Waypoints,
};

const TYPE_BADGE_COLORS: Record<string, string> = {
  person: 'bg-blue-500/20 text-blue-400',
  team: 'bg-purple-500/20 text-purple-400',
  system: 'bg-green-500/20 text-green-400',
  document: 'bg-amber-500/20 text-amber-400',
  role: 'bg-pink-500/20 text-pink-400',
  org_unit: 'bg-teal-500/20 text-teal-400',
  module: 'bg-indigo-500/20 text-indigo-400',
  project: 'bg-cyan-500/20 text-cyan-400',
};

export function DetailPanel({ nodeDetail, isLoading, onClose, onFocusNode }: DetailPanelProps) {
  const navigate = useNavigate();

  if (isLoading) {
    return (
      <div className="w-80 border-l border-border bg-background flex items-center justify-center">
        <div className="h-6 w-6 border-2 border-accent border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (!nodeDetail) {
    return (
      <div className="w-80 border-l border-border bg-background flex flex-col items-center justify-center text-muted-foreground text-sm p-6 text-center">
        <Network className="h-10 w-10 mb-3 opacity-30" />
        <p>Click a node to see details</p>
        <p className="text-xs mt-1">Double-click to expand neighbors</p>
        <p className="text-xs mt-0.5">Right-click for more options</p>
      </div>
    );
  }

  const cleanLabel = nodeDetail.label?.replace(/^\[.*?\]\s*/, '') || nodeDetail.id;
  const Icon = TYPE_ICONS[nodeDetail.meta_type] ?? Box;
  const badgeColor = TYPE_BADGE_COLORS[nodeDetail.meta_type] ?? 'bg-gray-500/20 text-gray-400';

  return (
    <div className="w-80 border-l border-border bg-background flex flex-col overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-start justify-between">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <Icon size={16} className="text-muted-foreground shrink-0" />
              <h3 className="text-sm font-semibold text-foreground truncate">{cleanLabel}</h3>
            </div>
            <div className="flex items-center gap-2 mt-1.5">
              <span className={cn('text-[10px] font-medium px-1.5 py-0.5 rounded-full capitalize', badgeColor)}>
                {nodeDetail.meta_type}
              </span>
              <span className="text-[10px] text-muted-foreground">
                {nodeDetail.degree} connections
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors p-1"
          >
            <X size={14} />
          </button>
        </div>

        {nodeDetail.meta_projects && (
          <p className="text-[11px] text-accent mt-2 truncate">{nodeDetail.meta_projects}</p>
        )}

        {nodeDetail.community != null && (
          <div className="flex items-center gap-1.5 mt-2">
            <div className="w-2.5 h-2.5 rounded-full bg-accent/60" />
            <span className="text-[10px] text-muted-foreground">Community {nodeDetail.community}</span>
          </div>
        )}
      </div>

      {/* Confidence bar */}
      {typeof nodeDetail.degree === 'number' && (
        <div className="px-4 py-3 border-b border-border">
          <div className="flex items-center justify-between text-[10px] text-muted-foreground mb-1">
            <span>Connectivity</span>
            <span>{nodeDetail.degree} edges</span>
          </div>
          <div className="h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full bg-accent rounded-full transition-all"
              style={{ width: `${Math.min(100, (nodeDetail.degree / 30) * 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Action buttons */}
      <div className="px-4 py-3 border-b border-border flex gap-2">
        <button
          onClick={() =>
            navigate(`/knowledge?tab=wiki&q=${encodeURIComponent(cleanLabel)}`)
          }
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-accent/10 text-accent hover:bg-accent/20 transition-colors"
        >
          <BookOpen size={12} />
          Open Full Article
        </button>
        <button
          onClick={() => navigate('/graph')}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-muted text-muted-foreground hover:text-foreground hover:bg-muted/80 transition-colors"
        >
          <Network size={12} />
          Explore in Graph
        </button>
      </div>

      {/* Neighbors list */}
      <div className="flex-1 overflow-y-auto p-4">
        <h4 className="text-xs font-medium text-muted-foreground mb-2">
          Top Neighbors ({Math.min(nodeDetail.neighbors.length, 5)} of {nodeDetail.neighbors.length})
        </h4>
        <div className="space-y-0.5">
          {nodeDetail.neighbors.slice(0, 5).map((nb) => {
            const NbIcon = TYPE_ICONS[nb.meta_type] ?? ChevronRight;
            return (
              <button
                key={nb.id}
                onClick={() => onFocusNode(nb.id)}
                className="w-full text-left px-2 py-1.5 rounded hover:bg-accent/10 flex items-center gap-2 text-xs group transition-colors"
              >
                <NbIcon className="h-3 w-3 text-muted-foreground shrink-0" />
                <span className="text-foreground truncate flex-1 group-hover:text-accent transition-colors">
                  {nb.label?.replace(/^\[.*?\]\s*/, '') || nb.id}
                </span>
                <span className="text-muted-foreground/50 text-[10px] shrink-0">{nb.relation}</span>
              </button>
            );
          })}
        </div>

        {nodeDetail.neighbors.length > 5 && (
          <p className="mt-2 text-center text-[10px] text-muted-foreground">
            +{nodeDetail.neighbors.length - 5} more neighbors
          </p>
        )}
      </div>
    </div>
  );
}
