import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { KnowledgeEngineCard } from '../KnowledgeEngineCard';
import { createWrapper } from '../../../test/wrapper';

const mockApiFetch = vi.fn();
vi.mock('../../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}));

vi.mock('../../../lib/utils', async () => {
  const actual = await vi.importActual('../../../lib/utils');
  return {
    ...actual,
    timeAgo: () => '2m ago',
  };
});

const STATS = {
  available: true,
  articles: { total: 2392, perfect: 1200, high: 800, medium: 392, avg_confidence: 0.946 },
  entities: { total: 7375, with_articles: 2100, coverage_pct: 28 },
  projects: 21,
  connections: 2739,
  last_generation: '2026-04-13T10:00:00Z',
  recent_24h_generated: 45,
};

const PROGRAMS = {
  programs: [
    { id: 'anti-corruption', name: 'Anti-Corruption', article_count: 78, people_count: 12 },
    { id: 'privacy', name: 'Privacy', article_count: 65, people_count: 8 },
  ],
  auditboard: { article_count: 50 },
};

beforeEach(() => {
  mockApiFetch.mockReset();
  mockApiFetch.mockImplementation((url: string) => {
    if (url.includes('/knowledge/stats')) return Promise.resolve(STATS);
    if (url.includes('/knowledge/programs/overview')) return Promise.resolve(PROGRAMS);
    if (url.includes('/knowledge/articles')) return Promise.resolve({ items: [], total: 0 });
    return Promise.resolve(null);
  });
});

describe('KnowledgeEngineCard', () => {
  it('renders card with article count', async () => {
    render(<KnowledgeEngineCard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('2,392')).toBeInTheDocument();
    });
  });

  it('shows Knowledge Engine title', async () => {
    render(<KnowledgeEngineCard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Knowledge Engine')).toBeInTheDocument();
    });
  });

  it('shows +N today badge when recent articles exist', async () => {
    render(<KnowledgeEngineCard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('+45 today')).toBeInTheDocument();
    });
  });

  it('shows entity coverage', async () => {
    render(<KnowledgeEngineCard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('28%')).toBeInTheDocument();
    });
    expect(screen.getByText('coverage')).toBeInTheDocument();
  });

  it('shows connections count', async () => {
    render(<KnowledgeEngineCard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('2,739')).toBeInTheDocument();
    });
    expect(screen.getByText('connections')).toBeInTheDocument();
  });

  it('shows project count in footer', async () => {
    render(<KnowledgeEngineCard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('21 projects indexed')).toBeInTheDocument();
    });
  });

  it('shows avg confidence in footer', async () => {
    render(<KnowledgeEngineCard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Avg: 95% confidence')).toBeInTheDocument();
    });
  });

  it('renders program pills', async () => {
    render(<KnowledgeEngineCard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/Anti-Corruption \(78\)/)).toBeInTheDocument();
    });
    expect(screen.getByText(/Privacy \(65\)/)).toBeInTheDocument();
  });

  it('has Browse link to knowledge wiki', async () => {
    render(<KnowledgeEngineCard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Browse')).toBeInTheDocument();
    });
    const link = screen.getByText('Browse').closest('a');
    expect(link?.getAttribute('href')).toBe('/knowledge?tab=wiki');
  });

  it('has Graph link in footer', async () => {
    render(<KnowledgeEngineCard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Graph')).toBeInTheDocument();
    });
    const link = screen.getByText('Graph').closest('a');
    expect(link?.getAttribute('href')).toBe('/graph');
  });

  it('shows loading skeleton initially', () => {
    mockApiFetch.mockReturnValue(new Promise(() => {}));
    render(<KnowledgeEngineCard />, { wrapper: createWrapper() });
    const skeleton = document.querySelector('.animate-pulse');
    expect(skeleton).toBeTruthy();
  });

  it('returns null when not available', async () => {
    mockApiFetch.mockImplementation((url: string) => {
      if (url.includes('/knowledge/stats')) return Promise.resolve({ available: false });
      return Promise.resolve(null);
    });
    const { container } = render(<KnowledgeEngineCard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(container.querySelector('.animate-pulse')).toBeNull();
    });
    // Should render nothing
    expect(container.firstChild).toBeNull();
  });

  it('toggles What\'s New section', async () => {
    const user = userEvent.setup();
    render(<KnowledgeEngineCard />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText("What's New")).toBeInTheDocument();
    });

    await user.click(screen.getByText("What's New"));
    // After clicking, it should try to fetch recent articles
    await waitFor(() => {
      const calls = mockApiFetch.mock.calls.map((c: unknown[]) => c[0] as string);
      expect(calls.some(url => url.includes('/knowledge/articles'))).toBe(true);
    });
  });
});
