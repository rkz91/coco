import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import GraphPage from '../GraphPage';
import { createWrapper } from '../../test/wrapper';

// ── Mock vis-network (canvas-based, can't run in jsdom) ─────────────────
const mockOn = vi.fn();
const mockDestroy = vi.fn();
const mockFit = vi.fn();
const mockFocus = vi.fn();
const mockSelectNodes = vi.fn();

vi.mock('vis-network', () => {
  return {
    Network: class MockNetwork {
      constructor() {
        mockOn.mockClear();
      }
      on = mockOn;
      destroy = mockDestroy;
      fit = mockFit;
      focus = mockFocus;
      selectNodes = mockSelectNodes;
    },
  };
});

vi.mock('vis-data', () => {
  return {
    DataSet: class MockDataSet {
      private store = new Map<string, unknown>();
      add(items: any) {
        const arr = Array.isArray(items) ? items : [items];
        arr.forEach((item: any) => this.store.set(item.id, item));
      }
      clear() { this.store.clear(); }
      get(id: string) { return this.store.get(id) ?? null; }
    },
  };
});

// ── Mock API ────────────────────────────────────────────────────────────
const mockApiFetch = vi.fn();
vi.mock('../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}));

const GOD_NODES = {
  items: [
    { id: 'alice', label: 'Alice Chen', meta_type: 'person', community: 0, degree: 15 },
    { id: 'system-x', label: 'System X', meta_type: 'system', community: 1, degree: 8 },
    { id: 'proj-a', label: 'Project Alpha', meta_type: 'project', community: 0, degree: 10 },
  ],
};

const NODE_DETAIL = {
  id: 'alice',
  label: 'Alice Chen',
  meta_type: 'person',
  degree: 15,
  community: 0,
  meta_projects: 'ProjectA, ProjectB',
  neighbors: [
    { id: 'bob', label: 'Bob Patel', meta_type: 'person', relation: 'works_with', confidence: '0.9' },
    { id: 'system-x', label: 'System X', meta_type: 'system', relation: 'owns', confidence: '0.85' },
  ],
};

const COMMUNITIES = {
  items: [
    { id: 0, size: 5, top_members: [{ id: 'alice', label: 'Alice Chen', degree: 15 }] },
    { id: 1, size: 3, top_members: [{ id: 'system-x', label: 'System X', degree: 8 }] },
  ],
  total: 2,
};

const SEARCH_RESULTS = {
  items: [
    { id: 'dave', label: 'Dave Kim', meta_type: 'person', degree: 6 },
  ],
  total: 1,
};

beforeEach(() => {
  mockApiFetch.mockReset();
  mockOn.mockReset();
  mockDestroy.mockReset();
  mockFit.mockReset();

  mockApiFetch.mockImplementation((url: string) => {
    if (url.includes('/graph/god-nodes')) return Promise.resolve(GOD_NODES);
    if (url.includes('/graph/communities')) return Promise.resolve(COMMUNITIES);
    if (url.includes('/graph/node/')) return Promise.resolve(NODE_DETAIL);
    if (url.includes('/graph/nodes?q=')) return Promise.resolve(SEARCH_RESULTS);
    return Promise.resolve({ items: [] });
  });
});

describe('GraphPage', () => {
  it('renders type filter pills', async () => {
    render(<GraphPage />, { wrapper: createWrapper() });

    expect(screen.getByRole('button', { name: 'All' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'person' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'system' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'project' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'document' })).toBeInTheDocument();
  });

  it('shows placeholder text when no node selected', () => {
    render(<GraphPage />, { wrapper: createWrapper() });
    expect(screen.getByText('Click a node to see details')).toBeInTheDocument();
    expect(screen.getByText('Double-click to expand its neighbors')).toBeInTheDocument();
  });

  it('renders search input', () => {
    render(<GraphPage />, { wrapper: createWrapper() });
    expect(screen.getByPlaceholderText('Search graph...')).toBeInTheDocument();
  });

  it('shows search results when query >= 2 chars', async () => {
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: createWrapper() });

    await user.type(screen.getByPlaceholderText('Search graph...'), 'da');

    await waitFor(() => {
      expect(screen.getByText('Dave Kim')).toBeInTheDocument();
    });
  });

  it('does not show search results for single char', async () => {
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: createWrapper() });

    await user.type(screen.getByPlaceholderText('Search graph...'), 'd');

    // Wait a tick and verify no results
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText('Dave Kim')).not.toBeInTheDocument();
  });

  it('initializes vis-network on mount', () => {
    render(<GraphPage />, { wrapper: createWrapper() });
    // Network constructor calls on() to register event handlers
    expect(mockOn).toHaveBeenCalled();
  });

  it('registers click and doubleClick handlers on network', () => {
    render(<GraphPage />, { wrapper: createWrapper() });
    const eventNames = mockOn.mock.calls.map((c: unknown[]) => c[0]);
    expect(eventNames).toContain('click');
    expect(eventNames).toContain('doubleClick');
  });

  it('renders community legend after data loads', async () => {
    render(<GraphPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Communities')).toBeInTheDocument();
    });
    expect(screen.getByText('Alice Chen')).toBeInTheDocument();
  });

  it('activates type filter pill on click', async () => {
    const user = userEvent.setup();
    render(<GraphPage />, { wrapper: createWrapper() });

    const personBtn = screen.getByRole('button', { name: 'person' });
    await user.click(personBtn);

    // After clicking, the pill should have the active styling class
    expect(personBtn.className).toContain('accent');
  });

  it('fetches god nodes on mount', async () => {
    render(<GraphPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalledWith(
        expect.stringContaining('/graph/god-nodes'),
      );
    });
  });

  it('fetches communities on mount', async () => {
    render(<GraphPage />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalledWith(
        expect.stringContaining('/graph/communities'),
      );
    });
  });
});
