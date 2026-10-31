import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Overview from './Overview.jsx';
import { api } from '../api/client.js';

vi.mock('../api/client.js', async () => {
  const actual = await vi.importActual('../api/client.js');
  return { ...actual, api: { dashboard: vi.fn() } };
});

const renderPage = () =>
  render(
    <MemoryRouter>
      <Overview />
    </MemoryRouter>
  );

const summary = {
  total_apis: 4,
  active_apis: 3,
  healthy_apis: 2,
  slow_apis: 1,
  failed_apis: 1,
  unknown_apis: 0,
  avg_response_ms: 245.5,
  uptime_24h: 98.75,
  checks_24h: 120,
  open_incidents: 1,
  status_distribution: [
    { status: 'healthy', count: 2 },
    { status: 'slow', count: 1 },
    { status: 'failed', count: 1 },
    { status: 'unknown', count: 0 },
  ],
  response_trend: [{ bucket_start: '2026-10-26T10:00:00Z', avg_response_ms: 200, success: 5, failed: 0, checks: 5, uptime_percent: 100, incidents: 0 }],
  recent_incidents: [
    { id: 1, api_id: 9, api_name: 'Payments', api_url: 'https://x.test', started_at: '2026-10-26T09:00:00Z', resolved_at: null, duration_seconds: 120, reason: 'Unexpected HTTP status 500', status_code: 500, status: 'open' },
  ],
};

describe('Overview page states', () => {
  beforeEach(() => vi.clearAllMocks());

  it('shows a loading indicator while fetching', () => {
    api.dashboard.mockReturnValue(new Promise(() => {}));
    renderPage();
    expect(screen.getByRole('status')).toHaveTextContent(/loading dashboard/i);
  });

  it('shows a helpful empty state when no APIs exist', async () => {
    api.dashboard.mockResolvedValue({ ...summary, total_apis: 0 });
    renderPage();
    expect(await screen.findByText('No APIs yet')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /add your first api/i })).toHaveAttribute('href', '/apis?new=1');
  });

  it('shows an error message with a working retry button', async () => {
    api.dashboard.mockRejectedValueOnce({ request: {} }).mockResolvedValueOnce(summary);
    renderPage();
    expect(await screen.findByRole('alert')).toHaveTextContent(/cannot reach the trustroute server/i);
    await userEvent.click(screen.getByRole('button', { name: /try again/i }));
    await waitFor(() => expect(screen.getByText('Total APIs')).toBeInTheDocument());
  });

  it('renders real metrics from the backend response', async () => {
    api.dashboard.mockResolvedValue(summary);
    renderPage();
    expect(await screen.findByText('Total APIs')).toBeInTheDocument();
    expect(screen.getByText('4')).toBeInTheDocument();
    expect(screen.getByText('246 ms')).toBeInTheDocument();
    expect(screen.getByText('98.75%')).toBeInTheDocument();
    expect(screen.getByText('Payments')).toBeInTheDocument();
  });
});
