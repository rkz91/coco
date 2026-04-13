import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MediaView } from '../MediaView';
import { createWrapper } from '../../../test/wrapper';

const mockApiFetch = vi.fn();
vi.mock('../../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}));

const MEDIA_ITEMS = [
  {
    id: '1',
    title: 'Architecture Diagram',
    description: 'System overview diagram',
    filename: 'arch.png',
    file_path: '/files/arch.png',
    asset_path: '/assets/arch.png',
    media_type: 'image',
    source: 'upload',
    tags: ['architecture', 'system', 'overview', 'design', 'infra'],
    timestamp: '2026-04-10T10:00:00Z',
    score: 0.95,
  },
  {
    id: '2',
    title: 'Meeting Recording',
    description: 'Q1 review call',
    filename: 'q1-review.mp4',
    file_path: '/files/q1.mp4',
    asset_path: '/assets/q1.mp4',
    media_type: 'video',
    source: 'upload',
    tags: ['meeting'],
    timestamp: '2026-04-09T14:00:00Z',
    score: 0.72,
  },
];

beforeEach(() => {
  mockApiFetch.mockReset();
});

describe('MediaView', () => {
  it('renders empty state before search', () => {
    render(<MediaView />, { wrapper: createWrapper() });
    expect(screen.getByText('Search media assets by description or tags')).toBeInTheDocument();
  });

  it('does not fetch until user types', () => {
    render(<MediaView />, { wrapper: createWrapper() });
    expect(mockApiFetch).not.toHaveBeenCalled();
  });

  it('fetches and displays results on search', async () => {
    const user = userEvent.setup();
    mockApiFetch.mockResolvedValue({ items: MEDIA_ITEMS, total: 2, available: true });

    render(<MediaView />, { wrapper: createWrapper() });
    await user.type(screen.getByPlaceholderText(/Search media/), 'arch');

    await waitFor(() => {
      expect(screen.getByText('arch.png')).toBeInTheDocument();
    });
    expect(screen.getByText('q1-review.mp4')).toBeInTheDocument();
    expect(screen.getByText('2 results')).toBeInTheDocument();
  });

  it('shows score percentage', async () => {
    const user = userEvent.setup();
    mockApiFetch.mockResolvedValue({ items: [MEDIA_ITEMS[0]], total: 1, available: true });

    render(<MediaView />, { wrapper: createWrapper() });
    await user.type(screen.getByPlaceholderText(/Search media/), 'arch');

    await waitFor(() => {
      expect(screen.getByText('95%')).toBeInTheDocument();
    });
  });

  it('shows media type badges', async () => {
    const user = userEvent.setup();
    mockApiFetch.mockResolvedValue({ items: MEDIA_ITEMS, total: 2, available: true });

    render(<MediaView />, { wrapper: createWrapper() });
    await user.type(screen.getByPlaceholderText(/Search media/), 'test');

    await waitFor(() => {
      expect(screen.getByText('image')).toBeInTheDocument();
      expect(screen.getByText('video')).toBeInTheDocument();
    });
  });

  it('truncates tags after 4 and shows overflow count', async () => {
    const user = userEvent.setup();
    mockApiFetch.mockResolvedValue({ items: [MEDIA_ITEMS[0]], total: 1, available: true });

    render(<MediaView />, { wrapper: createWrapper() });
    await user.type(screen.getByPlaceholderText(/Search media/), 'arch');

    await waitFor(() => {
      expect(screen.getByText('+1')).toBeInTheDocument();
    });
  });

  it('shows unavailable state when media-memory not configured', async () => {
    const user = userEvent.setup();
    mockApiFetch.mockResolvedValue({ items: [], total: 0, available: false });

    render(<MediaView />, { wrapper: createWrapper() });
    await user.type(screen.getByPlaceholderText(/Search media/), 'test');

    await waitFor(() => {
      expect(screen.getByText('Media memory not configured')).toBeInTheDocument();
    });
  });

  it('shows no results state', async () => {
    const user = userEvent.setup();
    mockApiFetch.mockResolvedValue({ items: [], total: 0, available: true });

    render(<MediaView />, { wrapper: createWrapper() });
    await user.type(screen.getByPlaceholderText(/Search media/), 'zzzzz');

    await waitFor(() => {
      expect(screen.getByText('No media found')).toBeInTheDocument();
    });
  });
});
