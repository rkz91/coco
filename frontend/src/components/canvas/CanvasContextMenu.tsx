import { useEffect, useRef } from 'react';
import { Expand, ExternalLink, Trash2, Pin } from 'lucide-react';
import { cn } from '../../lib/utils';

export interface ContextMenuState {
  nodeId: string;
  nodeType: string;
  x: number;
  y: number;
}

interface CanvasContextMenuProps {
  menu: ContextMenuState;
  onClose: () => void;
  onExpandNeighbors: (nodeId: string) => void;
  onOpenArticle: (nodeId: string) => void;
  onRemoveFromCanvas: (nodeId: string) => void;
  onPinPosition: (nodeId: string) => void;
}

export function CanvasContextMenu({
  menu,
  onClose,
  onExpandNeighbors,
  onOpenArticle,
  onRemoveFromCanvas,
  onPinPosition,
}: CanvasContextMenuProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    }
    function handleEscape(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose();
    }
    document.addEventListener('mousedown', handleClick);
    document.addEventListener('keydown', handleEscape);
    return () => {
      document.removeEventListener('mousedown', handleClick);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [onClose]);

  const items = [
    {
      label: 'Expand Neighbors',
      icon: Expand,
      onClick: () => { onExpandNeighbors(menu.nodeId); onClose(); },
    },
    ...(menu.nodeType === 'entity' || menu.nodeType === 'article'
      ? [{
          label: 'Open Article',
          icon: ExternalLink,
          onClick: () => { onOpenArticle(menu.nodeId); onClose(); },
        }]
      : []),
    {
      label: 'Pin Position',
      icon: Pin,
      onClick: () => { onPinPosition(menu.nodeId); onClose(); },
    },
    {
      label: 'Remove from Canvas',
      icon: Trash2,
      onClick: () => { onRemoveFromCanvas(menu.nodeId); onClose(); },
      danger: true,
    },
  ];

  return (
    <div
      ref={ref}
      className="fixed z-50 min-w-[180px] rounded-lg border border-border bg-card shadow-xl animate-fade-in py-1"
      style={{ left: menu.x, top: menu.y }}
    >
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <button
            key={item.label}
            onClick={item.onClick}
            className={cn(
              'w-full flex items-center gap-2 px-3 py-2 text-xs transition-colors',
              'danger' in item && item.danger
                ? 'text-destructive hover:bg-destructive/10'
                : 'text-foreground hover:bg-accent/10',
            )}
          >
            <Icon size={14} className="shrink-0" />
            {item.label}
          </button>
        );
      })}
    </div>
  );
}
