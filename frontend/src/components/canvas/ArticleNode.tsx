import { memo } from 'react';
import { Handle, Position, type NodeProps } from '@xyflow/react';
import { FileText, BookOpen, Newspaper, File } from 'lucide-react';
import { cn } from '../../lib/utils';

export type ArticleNodeData = {
  title: string;
  gid: string;
  summary: string;
  confidence: number;
  articleType: string;
};

const ARTICLE_TYPE_ICONS: Record<string, React.ElementType> = {
  wiki: BookOpen,
  email: Newspaper,
  document: FileText,
};

function ArticleNodeComponent({ data, selected }: NodeProps) {
  const nodeData = data as unknown as ArticleNodeData;
  const Icon = ARTICLE_TYPE_ICONS[nodeData.articleType] ?? File;

  return (
    <div
      className={cn(
        'px-3 py-2 rounded-lg border shadow-md min-w-[160px] max-w-[240px] backdrop-blur-sm transition-all',
        'bg-card/90 border-border',
        selected ? 'ring-2 ring-accent border-accent shadow-accent/20' : '',
      )}
    >
      <Handle type="target" position={Position.Top} className="!bg-accent !w-2 !h-2 !border-0" />
      <div className="flex items-center gap-1.5">
        <Icon size={12} className="text-accent shrink-0" />
        <span className="text-xs font-medium text-foreground truncate">{nodeData.title}</span>
      </div>
      {nodeData.summary && (
        <p className="text-[10px] text-muted-foreground mt-1 line-clamp-2 leading-relaxed">
          {nodeData.summary}
        </p>
      )}
      <div className="flex items-center gap-1.5 mt-1">
        <span className="text-[10px] text-muted-foreground/60 capitalize">{nodeData.articleType}</span>
        {nodeData.confidence > 0 && (
          <span className="text-[10px] text-muted-foreground/60 ml-auto">
            {Math.round(nodeData.confidence * 100)}%
          </span>
        )}
      </div>
      <Handle type="source" position={Position.Bottom} className="!bg-accent !w-2 !h-2 !border-0" />
    </div>
  );
}

export const ArticleNode = memo(ArticleNodeComponent);
