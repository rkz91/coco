import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { PeopleView } from '../PeopleView';
import { createWrapper } from '../../../test/wrapper';

const mockApiFetch = vi.fn();
vi.mock('../../../lib/api', () => ({
  apiFetch: (...args: unknown[]) => mockApiFetch(...args),
}));

const PEOPLE = [
  { gid: 'g1', canonical_name: 'Alice Chen', importance_score: 85, projects: ['ProjectA', 'ProjectB'], project_count: 2, connections: 12 },
  { gid: 'g2', canonical_name: 'Bob Patel', importance_score: 60, projects: ['ProjectA'], project_count: 1, connections: 5 },
  { gid: 'g3', canonical_name: 'Carol Wu', importance_score: 92, projects: ['ProjectC', 'ProjectD', 'ProjectE'], project_count: 3, connections: 20 },
];

beforeEach(() => {
  mockApiFetch.mockReset();
  mockApiFetch.mockResolvedValue({ items: PEOPLE, total: 3 });
});

describe('PeopleView', () => {
  it('fetches and renders people table', async () => {
    render(<PeopleView />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Alice Chen')).toBeInTheDocument();
    });
    expect(screen.getByText('Bob Patel')).toBeInTheDocument();
    expect(screen.getByText('Carol Wu')).toBeInTheDocument();
  });

  it('shows count of people', async () => {
    render(<PeopleView />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('3 of 3 people')).toBeInTheDocument();
    });
  });

  it('filters by search input', async () => {
    const user = userEvent.setup();
    render(<PeopleView />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Alice Chen')).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText(/Search people/), 'bob');

    expect(screen.getByText('Bob Patel')).toBeInTheDocument();
    expect(screen.queryByText('Alice Chen')).not.toBeInTheDocument();
    expect(screen.getByText('1 of 3 people')).toBeInTheDocument();
  });

  it('defaults to importance sort descending', async () => {
    render(<PeopleView />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Carol Wu')).toBeInTheDocument();
    });

    const rows = screen.getAllByRole('row').slice(1); // skip header
    expect(within(rows[0]).getByText('Carol Wu')).toBeInTheDocument();
    expect(within(rows[1]).getByText('Alice Chen')).toBeInTheDocument();
    expect(within(rows[2]).getByText('Bob Patel')).toBeInTheDocument();
  });

  it('sorts by name when header clicked', async () => {
    const user = userEvent.setup();
    render(<PeopleView />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Alice Chen')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: 'Name' }));

    // Name sort defaults to descending first, so Carol > Bob > Alice
    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('Carol Wu')).toBeInTheDocument();
  });

  it('toggles sort direction on second click', async () => {
    const user = userEvent.setup();
    render(<PeopleView />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Alice Chen')).toBeInTheDocument();
    });

    // Click Name twice: first click = desc, second click = asc
    await user.click(screen.getByRole('button', { name: 'Name' }));
    await user.click(screen.getByRole('button', { name: 'Name' }));

    const rows = screen.getAllByRole('row').slice(1);
    expect(within(rows[0]).getByText('Alice Chen')).toBeInTheDocument();
  });

  it('sorts by connections', async () => {
    const user = userEvent.setup();
    render(<PeopleView />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Alice Chen')).toBeInTheDocument();
    });

    await user.click(screen.getByRole('button', { name: 'Connections' }));

    const rows = screen.getAllByRole('row').slice(1);
    // desc: Carol(20) > Alice(12) > Bob(5)
    expect(within(rows[0]).getByText('Carol Wu')).toBeInTheDocument();
  });

  it('calls onSelectGid when row clicked', async () => {
    const onSelectGid = vi.fn();
    render(<PeopleView onSelectGid={onSelectGid} />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Alice Chen')).toBeInTheDocument();
    });

    await userEvent.click(screen.getByText('Alice Chen').closest('tr')!);
    expect(onSelectGid).toHaveBeenCalledWith('g1');
  });

  it('shows loading state', () => {
    mockApiFetch.mockReturnValue(new Promise(() => {})); // never resolves
    render(<PeopleView />, { wrapper: createWrapper() });
    expect(screen.getByText('Loading people graph...')).toBeInTheDocument();
  });

  it('shows empty state when no matches', async () => {
    const user = userEvent.setup();
    render(<PeopleView />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText('Alice Chen')).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText(/Search people/), 'zzzzzzz');
    expect(screen.getByText('No people found')).toBeInTheDocument();
  });

  it('shows pagination notice for > 200 results', async () => {
    const manyPeople = Array.from({ length: 210 }, (_, i) => ({
      gid: `g${i}`,
      canonical_name: `Person ${i}`,
      importance_score: i,
      projects: [],
      project_count: 0,
      connections: i,
    }));
    mockApiFetch.mockResolvedValue({ items: manyPeople, total: 210 });

    render(<PeopleView />, { wrapper: createWrapper() });

    await waitFor(() => {
      expect(screen.getByText(/Showing 200 of 210/)).toBeInTheDocument();
    });
  });
});
