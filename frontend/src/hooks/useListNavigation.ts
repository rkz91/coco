import { useState, useCallback, useEffect, useRef } from 'react';

interface UseListNavigationOptions<T> {
  onSelect?: (item: T) => void;
  onAction?: (key: string, item: T) => void;
}

interface UseListNavigationResult<T> {
  selectedIndex: number;
  selectedItem: T | null;
  containerRef: React.RefObject<HTMLDivElement | null>;
  getItemProps: (index: number) => {
    'data-list-index': number;
    className?: string;
  };
}

/**
 * Keyboard list navigation hook.
 *
 * - `j` / `ArrowDown` = move down
 * - `k` / `ArrowUp` = move up
 * - `Enter` = select
 * - `a` = action('approve')
 * - `d` = action('dismiss')
 *
 * Only active when the container (or a non-input child) has focus.
 */
export function useListNavigation<T>(
  items: T[],
  options?: UseListNavigationOptions<T>,
): UseListNavigationResult<T> {
  const [selectedIndex, setSelectedIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement | null>(null);

  // Reset selection when items change
  useEffect(() => {
    setSelectedIndex((prev) => {
      if (items.length === 0) return -1;
      if (prev >= items.length) return items.length - 1;
      return prev;
    });
  }, [items.length]);

  // Scroll selected item into view
  useEffect(() => {
    if (selectedIndex < 0 || !containerRef.current) return;
    const el = containerRef.current.querySelector(
      `[data-list-index="${selectedIndex}"]`,
    );
    if (el) {
      el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [selectedIndex]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      // Skip if user is typing in an input/textarea/select
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === 'input' || tag === 'textarea' || tag === 'select') return;

      // Only respond when container or its descendants have focus
      if (
        containerRef.current &&
        !containerRef.current.contains(e.target as Node)
      )
        return;

      const len = items.length;
      if (len === 0) return;

      switch (e.key) {
        case 'j':
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex((i) => Math.min(i + 1, len - 1));
          break;
        case 'k':
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex((i) => Math.max(i - 1, 0));
          break;
        case 'Enter':
          e.preventDefault();
          if (selectedIndex >= 0 && selectedIndex < len) {
            options?.onSelect?.(items[selectedIndex]);
          }
          break;
        case 'a':
          e.preventDefault();
          if (selectedIndex >= 0 && selectedIndex < len) {
            options?.onAction?.('approve', items[selectedIndex]);
          }
          break;
        case 'd':
          e.preventDefault();
          if (selectedIndex >= 0 && selectedIndex < len) {
            options?.onAction?.('dismiss', items[selectedIndex]);
          }
          break;
      }
    },
    [items, selectedIndex, options],
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const getItemProps = useCallback(
    (index: number) => ({
      'data-list-index': index,
    }),
    [],
  );

  return {
    selectedIndex,
    selectedItem: selectedIndex >= 0 ? items[selectedIndex] ?? null : null,
    containerRef,
    getItemProps,
  };
}
