import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Boxes } from 'lucide-react';
import { cn } from '../../lib/utils';

export type ClusterNodeData = {
  communityId: number;
  label: string;
  memberCount: number;
};

const CLUSTER_COLORS = [
  'border-blue-500/50 bg-blue-950/40',
  'border-red-500/50 bg-red-950/40',
  'border-green-500/50 bg-green-950/40',
  'border-amber-500/50 bg-amber-950/40',
  'border-purple-500/50 bg-purple-950/40',
  'border-pink-500/50 bg-pink-950/40',
  'border-teal-500/50 bg-teal-950/40',
  'border-orange-500/50 bg-orange-950/40',
  'border-indigo-500/50 bg-indigo-950/40',
  'border-cyan-500/50 bg-cyan-950/40',
];

function ClusterNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as ClusterNodeData;
  const colorClass = CLUSTER_COLORS[nodeData.communityId % CLUSTER_COLORS.length];

  return (
    <div
      className={cn(
        'px-4 py-3 rounded-xl border-2 border-dashed shadow-sm min-w-[140px] backdrop-blur-sm transition-all',
        colorClass,
        selected ? 'ring-2 ring-accent shadow-accent/20' : '',
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-accent !w-2 !h-2 !border-0" />
      <div className="flex items-center gap-2">
        <Boxes size={14} className="text-muted-foreground shrink-0" />
        <span className="text-xs font-semibold text-foreground truncate">{nodeData.label}</span>
      </div>
      <div className="text-[10px] text-muted-foreground mt-1">
        {nodeData.memberCount} members
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-accent !w-2 !h-2 !border-0" />
    </div>
  );
}

export const ClusterNode = memo(ClusterNodeComponent);
