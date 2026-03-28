import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import * as Dialog from '@radix-ui/react-dialog';
import { ChevronRight, ArrowUp, Folder, Check, X } from 'lucide-react';
import { apiFetch } from '../../lib/api';

interface FolderPickerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelect: (path: string) => void;
  initialPath?: string;
}

interface BrowseResult {
  path: string;
  exists: boolean;
  dirs: { name: string; path: string }[];
  parent: string | null;
}

export function FolderPickerDialog({ open, onOpenChange, onSelect, initialPath = '~' }: FolderPickerProps) {
  const [currentPath, setCurrentPath] = useState(initialPath);

  const { data, isLoading } = useQuery<BrowseResult>({
    queryKey: ['filesystem-browse', currentPath],
    queryFn: () => apiFetch(`/filesystem/browse?path=${encodeURIComponent(currentPath)}`),
    enabled: open,
    staleTime: 5_000,
  });

  // Reset path when dialog opens
  useMemo(() => {
    if (open) setCurrentPath(initialPath || '~');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const pathParts = (data?.path ?? '').split('/').filter(Boolean);

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 bg-black/30 backdrop-blur-sm z-40" />
        <Dialog.Content className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 w-full max-w-lg rounded-2xl border border-border bg-card shadow-2xl flex flex-col" style={{ maxHeight: '70vh' }}>
          <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
            <Dialog.Title className="text-sm font-semibold text-foreground">Select Folder</Dialog.Title>
            <Dialog.Close className="text-muted-foreground hover:text-foreground p-1 rounded-lg hover:bg-accent/50 transition-colors">
              <X size={18} />
            </Dialog.Close>
          </div>

          <div className="flex items-center gap-1 px-5 py-2 border-b border-border text-xs text-muted-foreground overflow-x-auto shrink-0">
            <button onClick={() => setCurrentPath('/')} className="hover:text-foreground transition-colors shrink-0">/</button>
            {pathParts.map((part, i) => (
              <span key={i} className="flex items-center gap-1 shrink-0">
                <ChevronRight size={10} className="text-muted-foreground/50" />
                <button
                  onClick={() => setCurrentPath('/' + pathParts.slice(0, i + 1).join('/'))}
                  className="hover:text-foreground transition-colors"
                >{part}</button>
              </span>
            ))}
          </div>

          <div className="flex-1 overflow-y-auto px-2 py-2">
            {data?.parent && (
              <button
                onClick={() => setCurrentPath(data.parent!)}
                className="w-full flex items-center gap-3 px-3 py-2 text-sm rounded-lg hover:bg-accent/30 transition-colors text-muted-foreground"
              >
                <ArrowUp size={14} />
                <span>..</span>
              </button>
            )}

            {isLoading ? (
              <div className="space-y-1 p-2">
                {[1, 2, 3, 4, 5].map(i => (
                  <div key={i} className="h-8 bg-muted/50 rounded animate-pulse" />
                ))}
              </div>
            ) : data?.dirs.length === 0 ? (
              <p className="text-xs text-muted-foreground text-center py-8">No subdirectories</p>
            ) : (
              data?.dirs.map(dir => (
                <button
                  key={dir.path}
                  onClick={() => setCurrentPath(dir.path)}
                  className="w-full flex items-center gap-3 px-3 py-2 text-sm rounded-lg hover:bg-accent/30 transition-colors text-foreground"
                >
                  <Folder size={14} className="text-muted-foreground shrink-0" />
                  <span className="truncate">{dir.name}</span>
                </button>
              ))
            )}
          </div>

          <div className="flex items-center gap-3 px-5 py-3 border-t border-border shrink-0">
            <div className="flex-1 text-xs text-muted-foreground font-mono truncate">
              {data?.path ?? currentPath}
            </div>
            <button
              onClick={() => onSelect(data?.path ?? currentPath)}
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-medium bg-primary text-primary-foreground rounded-lg hover:opacity-90 transition-opacity"
            >
              <Check size={14} />
              Select This Folder
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
