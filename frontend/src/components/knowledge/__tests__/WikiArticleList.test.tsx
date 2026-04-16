import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { WikiArticleList } from '../WikiArticleList';
import { createWrapper } from '../../../test/wrapper';

const mockApiFetch = vi.fn();
vi.mock('../../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}));

const ARTICLES = [
  { id: 1, gid: 'g1', title: 'Alice Chen', summary: 'A person', confidence: 0.95, generated_at: '2026-04-13', article_type: 'entity', entity_type: 'person', canonical_name: 'Alice Chen' },
  { id: 2, gid: 'g2', title: 'Bridger System', summary: 'A system entity', confidence: 1.0, generated_at: '2026-04-12', article_type: 'entity', entity_type: 'system', canonical_name: 'Bridger System' },
  { id: 3, gid: 'g3', title: 'Weekly Digest', summary: 'A digest article', confidence: 0.88, generated_at: '2026-04-11', article_type: 'digest', entity_type: null, canonical_name: null },
];

beforeEach(() => {
  mockApiFetch.mockReset();
  mockApiFetch.mockResolvedValue({ items: ARTICLES, total: 3 });
});

describe('WikiArticleList', () => {
  it('renders articles after loading', async () => {
    render(<WikiArticleList selectedGid={null} onSelect={vi.fn()} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Alice Chen')).toBeInTheDocument();
    });
    expect(screen.getByText('Bridger System')).toBeInTheDocument();
    expect(screen.getByText('Weekly Digest')).toBeInTheDocument();
  });

  it('shows loading state', () => {
    mockApiFetch.mockReturnValue(new Promise(() => {}));
    render(<WikiArticleList selectedGid={null} onSelect={vi.fn()} />, { wrapper: createWrapper() });
    expect(screen.getByText('Loading articles...')).toBeInTheDocument();
  });

  it('shows article count', async () => {
    render(<WikiArticleList selectedGid={null} onSelect={vi.fn()} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/3 articles/)).toBeInTheDocument();
    });
  });

  it('shows empty state when no results', async () => {
    mockApiFetch.mockResolvedValue({ items: [], total: 0 });
    render(<WikiArticleList selectedGid={null} onSelect={vi.fn()} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('No wiki articles found')).toBeInTheDocument();
    });
  });

  it('highlights selected article', async () => {
    render(<WikiArticleList selectedGid="g1" onSelect={vi.fn()} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Alice Chen')).toBeInTheDocument();
    });

    const button = screen.getByText('Alice Chen').closest('button');
    expect(button?.className).toContain('bg-accent/10');
  });

  it('calls onSelect when article clicked', async () => {
    const onSelect = vi.fn();
    render(<WikiArticleList selectedGid={null} onSelect={onSelect} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Alice Chen')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('Alice Chen').closest('button')!);
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ gid: 'g1', title: 'Alice Chen' }));
  });

  it('shows confidence percentage', async () => {
    render(<WikiArticleList selectedGid={null} onSelect={vi.fn()} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('95%')).toBeInTheDocument();
    });
    expect(screen.getByText('100%')).toBeInTheDocument();
    expect(screen.getByText('88%')).toBeInTheDocument();
  });

  it('shows article summary', async () => {
    render(<WikiArticleList selectedGid={null} onSelect={vi.fn()} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('A person')).toBeInTheDocument();
    });
    expect(screen.getByText('A system entity')).toBeInTheDocument();
  });

  it('passes filters to API query', async () => {
    const filters = { articleType: 'meeting', entityType: 'person', minConfidence: 90, project: 'ab1' };
    render(<WikiArticleList selectedGid={null} onSelect={vi.fn()} filters={filters} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(mockApiFetch).toHaveBeenCalled();
    });

    const url = mockApiFetch.mock.calls[0][0] as string;
    expect(url).toContain('article_type=meeting');
    expect(url).toContain('entity_type=person');
    expect(url).toContain('min_confidence=0.9');
    expect(url).toContain('project=ab1');
  });

  it('resets offset when search changes', async () => {
    const user = userEvent.setup();
    render(<WikiArticleList selectedGid={null} onSelect={vi.fn()} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Alice Chen')).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText(/Search wiki/), 'test');

    // Should include the search query in API call
    await waitFor(() => {
      const lastCall = mockApiFetch.mock.calls[mockApiFetch.mock.calls.length - 1][0] as string;
      expect(lastCall).toContain('q=');
    });
  });

  it('shows keyword/semantic toggle', async () => {
    render(<WikiArticleList selectedGid={null} onSelect={vi.fn()} />, { wrapper: createWrapper() });

    expect(screen.getByRole('button', { name: /Keyword/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Semantic/ })).toBeInTheDocument();
  });
});
