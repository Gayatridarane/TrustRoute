import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Bell, CheckCheck, LogOut } from 'lucide-react';
import { api, errorMessage } from '../api/client.js';
import { useAuth } from '../auth/AuthContext.jsx';
import useAsync from '../hooks/useAsync.js';
import { EmptyState, ErrorState, Notice, PageHeader, Pagination, Spinner } from '../components/ui.jsx';
import { formatDateTime } from '../utils/format.js';

const KIND = { failure: 'API failure', recovery: 'API recovery', slow: 'Slow response' };

export default function Settings() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const [notice, setNotice] = useState(null);
  const alerts = useAsync(() => api.alerts({ page, page_size: 10 }), [page], { refreshMs: 30000 });
  const cfg = user?.config;

  const markRead = async (id) => {
    try {
      await api.markAlertRead(id);
      alerts.refresh();
    } catch (err) {
      setNotice({ type: 'error', text: errorMessage(err) });
    }
  };
  const markAll = async () => {
    try {
      await api.markAllAlertsRead();
      alerts.refresh();
    } catch (err) {
      setNotice({ type: 'error', text: errorMessage(err) });
    }
  };

  return (
    <>
      <PageHeader title="Settings" subtitle="Your account, alerts and how TrustRoute calculates reliability." />
      <Notice notice={notice} onDismiss={() => setNotice(null)} />

      <div className="grid-2">
        <section className="card pad" aria-label="Account">
          <h2>Account</h2>
          <dl className="kv">
            <dt>Username</dt>
            <dd>{user?.username}</dd>
            <dt>Email</dt>
            <dd>{user?.email || <span className="muted">Not set</span>}</dd>
            <dt>Email alerts</dt>
            <dd>{cfg?.email_alerts_enabled ? 'Enabled on this server' : 'Disabled (set ALERT_EMAIL_ENABLED and SMTP variables in backend/.env)'}</dd>
            <dt>Minimum interval</dt>
            <dd>{cfg?.min_check_interval_seconds}s</dd>
            <dt>API limit</dt>
            <dd>{cfg?.max_apis_per_user} per account</dd>
            <dt>History retention</dt>
            <dd>{cfg?.retention_days} days</dd>
          </dl>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={async () => {
              await logout();
              navigate('/login');
            }}
          >
            <LogOut size={16} aria-hidden="true" /> Sign out
          </button>
        </section>

        <section className="card pad" aria-label="How uptime is calculated">
          <h2>How uptime is calculated</h2>
          <p>
            <strong>Check-based uptime = successful checks ÷ total completed checks × 100.</strong>
          </p>
          <p className="muted">
            A check is successful when the endpoint returns the expected HTTP status — even if it was slow. It fails on timeouts, DNS or connection errors, or an unexpected status code. This measures what
            TrustRoute observed, not wall-clock availability between checks.
          </p>
        </section>
      </div>

      <section className="card" id="alerts" aria-label="Alerts">
        <div className="card-head">
          <h2>
            <Bell size={18} aria-hidden="true" /> Alerts
          </h2>
          <button type="button" className="btn btn-secondary btn-sm" onClick={markAll}>
            <CheckCheck size={16} aria-hidden="true" /> Mark all read
          </button>
        </div>
        {alerts.loading && !alerts.data ? (
          <Spinner label="Loading alerts…" />
        ) : alerts.error && !alerts.data ? (
          <ErrorState message={alerts.error} onRetry={alerts.reload} />
        ) : alerts.data.count === 0 ? (
          <EmptyState title="No alerts" description="You'll be notified here when an API fails, recovers or responds slowly." />
        ) : (
          <>
            <ul className="alert-list">
              {alerts.data.results.map((a) => (
                <li key={a.id} className={a.is_read ? 'read' : 'unread'}>
                  <span className={`kind kind-${a.kind}`}>{KIND[a.kind]}</span>
                  <span className="alert-msg">{a.message}</span>
                  <time dateTime={a.created_at}>{formatDateTime(a.created_at)}</time>
                  {!a.is_read && (
                    <button type="button" className="btn btn-secondary btn-sm" onClick={() => markRead(a.id)}>
                      Mark read
                    </button>
                  )}
                </li>
              ))}
            </ul>
            <Pagination page={page} count={alerts.data.count} pageSize={10} onChange={setPage} />
          </>
        )}
      </section>
    </>
  );
}
