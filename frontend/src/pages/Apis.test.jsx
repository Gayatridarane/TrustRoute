import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Apis from './Apis.jsx';
import { api } from '../api/client.js';

vi.mock('../api/client.js', async () => {
  const actual = await vi.importActual('../api/client.js');
  return { ...actual, api: { listApis: vi.fn(), createApi: vi.fn(), updateApi: vi.fn(), deleteApi: vi.fn(), checkApi: vi.fn() } };
});

const renderPage = () =>
  render(
    <MemoryRouter>
      <Apis />
    </MemoryRouter>
  );

const item = { id: 1, name: 'Payments', url: 'https://api.example.com/health', method: 'GET', is_active: true, current_status: 'healthy', last_response_time_ms: 120, last_checked_at: null };

describe('Monitored APIs page states', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows loading', () => {
    api.listApis.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByRole('status')).toHaveTextContent(/loading apis/i);
  });

  it('shows the empty state with an add button that opens the form', async () => {
    api.listApis.mockResolvedValue({ count: 0, results: [] });
    renderPage();
    expect(await screen.findByText('No APIs yet')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /add your first api/i }));
    expect(screen.getByRole('dialog', { name: /add api/i })).toBeInTheDocument();
  });

  it('shows an error state', async () => {
    api.listApis.mockRejectedValue({ response: { status: 500, data: { detail: 'An unexpected server error occurred.' } } });
    renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent('An unexpected server error occurred.');
  });

  it('lists APIs and asks for confirmation before deleting', async () => {
    api.listApis.mockResolvedValue({ count: 1, results: [item] });
    renderPage();
    expect(await screen.findByText('Payments')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: /delete payments/i }));
    expect(screen.getByRole('dialog', { name: /delete api/i })).toBeInTheDocument();
    expect(api.deleteApi).not.toHaveBeenCalled();
  });
});
