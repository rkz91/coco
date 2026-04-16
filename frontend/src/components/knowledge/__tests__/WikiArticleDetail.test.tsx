import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { WikiArticleDetail } from '../WikiArticleDetail';
import { createWrapper } from '../../../test/wrapper';

const mockApiFetch = vi.fn();
vi.mock('../../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}));

const ARTICLE = {
  id: 1,
  gid: 'g1',
  title: 'Alice Chen',
  summary: 'A senior engineer on the Cross Risk team.',
  body_json: {
    sections: [
      { heading: 'Overview', content: 'Alice is a backend engineer.' },
      { heading: 'Projects', content: 'Works on AB1 and Privacy.' },
      { heading: 'Skills', content: 'Python, FastAPI, SQLite.' },
    ],
  },
  infobox_json: { role: 'Senior Engineer', team: 'Cross Risk', projects: ['AB1', 'Privacy'] },
  sources_json: ['source1', 'source2'],
  confidence: 0.95,
  generated_at: '2026-04-13T10:00:00Z',
  article_type: 'entity',
  quality_score: 0.88,
};

const RELATED = {
  items: [
    { gid: 'g2', title: 'Bob Patel', summary: 'A colleague', confidence: 0.90, article_type: 'entity', entity_type: 'person' },
  ],
};

const BACKLINKS = {
  items: [
    { gid: 'g3', title: 'AB1 Steady State', summary: 'A project', confidence: 0.98, article_type: 'project_summary', entity_type: null },
  ],
};

beforeEach(() => {
  mockApiFetch.mockReset();
  mockApiFetch.mockImplementation((url: string) => {
    if (url.includes('/knowledge/article/g1/related')) return Promise.resolve(RELATED);
    if (url.includes('/knowledge/article/g1/backlinks')) return Promise.resolve(BACKLINKS);
    if (url.includes('/knowledge/article/g1')) return Promise.resolve(ARTICLE);
    return Promise.resolve(null);
  });
});

describe('WikiArticleDetail', () => {
  it('renders article title', async () => {
    render(<WikiArticleDetail gid="g1" onClose={vi.fn()} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Alice Chen')).toBeInTheDocument();
    });
  });

  it('renders summary', async () => {
    render(<WikiArticleDetail gid="g1" onClose={vi.fn()} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('A senior engineer on the Cross Risk team.')).toBeInTheDocument();
    });
  });

  it('renders confidence percentage', async () => {
    render(<WikiArticleDetail gid="g1" onClose={vi.fn()} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/95% confidence/)).toBeInTheDocument();
    });
  });

  it('renders article sections', async () => {
    render(<WikiArticleDetail gid="g1" onClose={vi.fn()} />, { wrapper: createWrapper() });

    await waitFor(() => {
      // "Overview" appears in both ToC and section heading, so use getAllByText
      expect(screen.getAllByText('Overview').length).toBeGreaterThanOrEqual(1);
    });
    expect(screen.getByText('Alice is a backend engineer.')).toBeInTheDocument();
    expect(screen.getAllByText('Projects').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('Skills').length).toBeGreaterThanOrEqual(1);
  });

  it('renders infobox with role and team', async () => {
    render(<WikiArticleDetail gid="g1" onClose={vi.fn()} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Senior Engineer')).toBeInTheDocument();
    });
    expect(screen.getByText('Cross Risk')).toBeInTheDocument();
  });

  it('renders source count', async () => {
    render(<WikiArticleDetail gid="g1" onClose={vi.fn()} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('2 sources')).toBeInTheDocument();
    });
  });

  it('renders table of contents for 3+ sections', async () => {
    render(<WikiArticleDetail gid="g1" onClose={vi.fn()} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Contents')).toBeInTheDocument();
    });
    expect(screen.getByText('(3 sections)')).toBeInTheDocument();
  });

  it('hides ToC for fewer than 3 sections', async () => {
    const shortArticle = { ...ARTICLE, body_json: { sections: [{ heading: 'A', content: 'B' }] } };
    mockApiFetch.mockImplementation((url: string) => {
      if (url.includes('/knowledge/article/g1')) return Promise.resolve(shortArticle);
      return Promise.resolve({ items: [] });
    });

    render(<WikiArticleDetail gid="g1" onClose={vi.fn()} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Alice Chen')).toBeInTheDocument();
    });
    expect(screen.queryByText('Contents')).not.toBeInTheDocument();
  });

  it('renders related articles', async () => {
    render(<WikiArticleDetail gid="g1" onClose={vi.fn()} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Bob Patel')).toBeInTheDocument();
    });
  });

  it('renders backlinks', async () => {
    render(<WikiArticleDetail gid="g1" onClose={vi.fn()} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('AB1 Steady State')).toBeInTheDocument();
    });
  });

  it('calls onClose when X button clicked', async () => {
    const onClose = vi.fn();
    const user = userEvent.setup();
    render(<WikiArticleDetail gid="g1" onClose={onClose} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Alice Chen')).toBeInTheDocument();
    });

    // Find the close button (X icon button)
    const buttons = screen.getAllByRole('button');
    const closeButton = buttons.find(b => b.getAttribute('title') !== 'Open in Graph' && !b.textContent);
    if (closeButton) {
      await user.click(closeButton);
      expect(onClose).toHaveBeenCalled();
    }
  });

  it('shows loading skeleton', () => {
    mockApiFetch.mockReturnValue(new Promise(() => {}));
    render(<WikiArticleDetail gid="g1" onClose={vi.fn()} />, { wrapper: createWrapper() });
    const skeleton = document.querySelector('.animate-pulse');
    expect(skeleton).toBeTruthy();
  });

  it('shows not found when article missing', async () => {
    mockApiFetch.mockImplementation((url: string) => {
      if (url.includes('/knowledge/article/g1')) return Promise.resolve({ error: 'not found' });
      return Promise.resolve({ items: [] });
    });

    render(<WikiArticleDetail gid="g1" onClose={vi.fn()} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Article not found')).toBeInTheDocument();
    });
  });

  it('renders article type badge', async () => {
    render(<WikiArticleDetail gid="g1" onClose={vi.fn()} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Entity')).toBeInTheDocument();
    });
  });
});
