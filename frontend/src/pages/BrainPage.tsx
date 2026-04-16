import { useCallback, useEffect, useMemo, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Scale, Calendar, CheckSquare } from 'lucide-react';
import { cn } from '../lib/utils';
import { BrainStatsBar } from '../components/brain/BrainStatsBar';
import { BrainSearchBar } from '../components/brain/BrainSearchBar';
import { BrainDecisionList } from '../components/brain/BrainDecisionList';
import { BrainEventTimeline } from '../components/brain/BrainEventTimeline';
import { BrainTaskView } from '../components/brain/BrainTaskView';
import { useBrainSearch } from '../hooks/useBrainSearch';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type BrainTab = 'decisions' | 'events' | 'tasks';

const TABS: { id: BrainTab; label: string; icon: React.ReactNode }[] = [
  { id: 'decisions', label: 'Decisions', icon: <Scale className="h-4 w-4" /> },
  { id: 'events', label: 'Events', icon: <Calendar className="h-4 w-4" /> },
  { id: 'tasks', label: 'Tasks', icon: <CheckSquare className="h-4 w-4" /> },
];

function resolveTab(raw: string | null): BrainTab {
  if (raw === 'decisions' || raw === 'events' || raw === 'tasks') return raw;
  return 'decisions';
}

// ---------------------------------------------------------------------------
// BrainPage
// ---------------------------------------------------------------------------

export default function BrainPage() {
  const [searchParams, setSearchParams] = useSearchParams();

  // Derive tab from URL
  const activeTab = useMemo(
    () => resolveTab(searchParams.get('tab')),
    [searchParams],
  );

  // Search: sync URL <-> local state via useBrainSearch hook for debounce
  const { query, setQuery, debouncedQuery } = useBrainSearch(300);

  // Seed local query from URL on first mount (if ?q= is present)
  const seeded = useRef(false);
  useEffect(() => {
    if (seeded.current) return;
    const urlQ = searchParams.get('q');
    if (urlQ) setQuery(urlQ);
    seeded.current = true;
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ---------------------------------------------------------------------------
  // URL helpers
  // ---------------------------------------------------------------------------

  const handleTabChange = useCallback(
    (tab: BrainTab) => {
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        next.set('tab', tab);
        return next;
      });
    },
    [setSearchParams],
  );

  const handleSearchChange = useCallback(
    (q: string) => {
      setQuery(q);
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        if (q) next.set('q', q);
        else next.delete('q');
        return next;
      });
    },
    [setQuery, setSearchParams],
  );

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="flex flex-col h-full p-6 space-y-4">
      {/* Header */}
      <header>
        <h1 className="text-2xl font-bold text-foreground">Brain</h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          Project decisions, events, and tasks
        </p>
      </header>

      {/* Stats bar (clickable cards also navigate tabs) */}
      <BrainStatsBar onTabChange={handleTabChange} activeTab={activeTab} />

      {/* Search */}
      <BrainSearchBar value={query} onChange={handleSearchChange} />

      {/* Tab bar */}
      <div
        className="flex items-center gap-1 border-b border-border"
        role="tablist"
        aria-label="Brain sections"
      >
        {TABS.map((tab) => (
          <button
            key={tab.id}
            id={`brain-tab-${tab.id}`}
            role="tab"
            aria-selected={activeTab === tab.id}
            aria-controls={`brain-tabpanel-${tab.id}`}
            onClick={() => handleTabChange(tab.id)}
            className={cn(
              'flex items-center gap-2 px-4 py-2.5 text-sm font-medium transition-colors border-b-2 -mb-px',
              activeTab === tab.id
                ? 'border-foreground text-foreground'
                : 'border-transparent text-muted-foreground hover:text-foreground hover:border-border',
            )}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'decisions' && (
          <div
            id="brain-tabpanel-decisions"
            role="tabpanel"
            aria-labelledby="brain-tab-decisions"
            className="h-full overflow-auto"
          >
            <BrainDecisionList search={debouncedQuery} />
          </div>
        )}

        {activeTab === 'events' && (
          <div
            id="brain-tabpanel-events"
            role="tabpanel"
            aria-labelledby="brain-tab-events"
            className="h-full overflow-auto"
          >
            <BrainEventTimeline search={debouncedQuery} />
          </div>
        )}

        {activeTab === 'tasks' && (
          <div
            id="brain-tabpanel-tasks"
            role="tabpanel"
            aria-labelledby="brain-tab-tasks"
            className="h-full overflow-auto"
          >
            <BrainTaskView search={debouncedQuery} />
          </div>
        )}
      </div>
    </div>
  );
}
