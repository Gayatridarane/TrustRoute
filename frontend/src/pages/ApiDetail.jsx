import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, Pencil, Play } from 'lucide-react';
import { api, errorMessage, fieldErrors } from '../api/client.js';
import useAsync from '../hooks/useAsync.js';
import ApiForm from '../components/ApiForm.jsx';
import IncidentTable from '../components/IncidentTable.jsx';
import { ChartCard, ErrorState, Modal, Notice, PageHeader, Pagination, Spinner, StatCard, StatusBadge } from '../components/ui.jsx';
import { ResponseTimeChart, SuccessFailChart } from '../components/charts.jsx';
import { formatDateTime, formatMs, formatPercent, timeAgo } from '../utils/format.js';

export default function ApiDetail() {
  const { id } = useParams();
  const [range, setRange] = useState('24h');
  const [historyPage, setHistoryPage] = useState(1);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [formErrors, setFormErrors] = useState({});
  const [formGeneral, setFormGeneral] = useState('');
  const [checking, setChecking] = useState(false);
  const [notice, setNotice] = useState(null);

  const item = useAsync(() => api.getApi(id), [id], { refreshMs: 30000 });
  const analytics = useAsync(() => api.apiAnalytics(id, range), [id, range], { refreshMs: 60000 });
  const history = useAsync(() => api.apiHistory(id, { page: historyPage, page_size: 10 }), [id, historyPage], { refreshMs: 30000 });
  const incidents = useAsync(() => api.incidents({ api: id, page_size: 10 }), [id], { refreshMs: 60000 });

  if (item.loading && !item.data) return <Spinner label="Loading API…" />;
  if (item.error && !item.data) {
    return (
      <>
        <Link to="/apis" className="back-link">
          <ArrowLeft size={16} aria-hidden="true" /> Back to APIs
        </Link>
        <ErrorState message={item.error} onRetry={item.reload} />
      </>
    );
  }
  const a = item.data;

  const refreshAll = () => {
    item.refresh();
    analytics.refresh();
    history.refresh();
    incidents.refresh();
  };

  const runCheck = async () => {
    setChecking(true);
    try {
      const r = await api.checkApi(id);
      const text = r.status === 'healthy' ? `Healthy in ${formatMs(r.response_time_ms)}.` : r.error_message || r.status;
      setNotice({ type: r.status === 'failed' ? 'error' : r.status === 'slow' ? 'warn' : 'success', text });
      setHistoryPage(1);
      refreshAll();
    } catch (err) {
      setNotice({ type: 'error', text: errorMessage(err) });
    } finally {
      setChecking(false);
    }
  };

  const save = async (values) => {
    setSaving(true);
    setFormErrors({});
    setFormGeneral('');
    try {
      await api.updateApi(id, values);
      setEditing(false);
      setNotice({ type: 'success', text: 'Changes saved.' });
      refreshAll();
    } catch (err) {
      const fields = fieldErrors(err);
      setFormErrors(fields);
      setFormGeneral(Object.keys(fields).length ? '' : errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const summary = analytics.data?.summary;
  const series = analytics.data?.series || [];
  const hasData = summary && summary.total_checks > 0;

  return (
    <>
      <Link to="/apis" className="back-link">
        <ArrowLeft size={16} aria-hidden="true" /> Back to APIs
      </Link>
      <PageHeader
        title={a.name}
        subtitle={
          <>
            <code>{a.method}</code> {a.url}
          </>
        }
        actions={
          <>
            <StatusBadge status={a.is_active ? a.current_status : 'paused'} />
            <button type="button" className="btn btn-secondary" onClick={() => setEditing(true)}>
              <Pencil size={16} aria-hidden="true" /> Edit
            </button>
            <button type="button" className="btn btn-primary" onClick={runCheck} disabled={checking}>
              <Play size={16} aria-hidden="true" /> {checking ? 'Checking…' : 'Run check now'}
            </button>
          </>
        }
      />
      <Notice notice={notice} onDismiss={() => setNotice(null)} />

      <div className="stats-grid">
        <StatCard label="Latest response" value={formatMs(a.last_response_time_ms)} hint={`Checked ${timeAgo(a.last_checked_at)}`} />
        <StatCard label="Uptime (24h)" value={formatPercent(analytics.data?.uptime_24h)} />
        <StatCard label="Uptime (7d)" value={formatPercent(analytics.data?.uptime_7d)} />
        <StatCard label="Check interval" value={`${a.interval_seconds}s`} hint={`Timeout ${a.timeout_seconds}s`} />
        <StatCard label="Slow threshold" value={formatMs(a.response_threshold_ms)} hint={`Expects HTTP ${a.expected_status}`} />
      </div>

      <div className="range-toggle" role="group" aria-label="Chart range">
        {['24h', '7d'].map((r) => (
          <button key={r} type="button" className={`btn btn-sm ${range === r ? 'btn-primary' : 'btn-secondary'}`} aria-pressed={range === r} onClick={() => setRange(r)}>
            {r === '24h' ? 'Last 24 hours' : 'Last 7 days'}
          </button>
        ))}
      </div>

      {analytics.error && !analytics.data ? (
        <ErrorState message={analytics.error} onRetry={analytics.reload} />
      ) : (
        <div className="grid-2">
          <ChartCard title="Response time" empty={analytics.loading ? 'Loading chart…' : hasData ? null : 'No checks in this period yet.'}>
            <ResponseTimeChart series={series} range={range} />
          </ChartCard>
          <ChartCard title="Successful vs failed checks" empty={analytics.loading ? 'Loading chart…' : hasData ? null : 'No checks in this period yet.'}>
            <SuccessFailChart series={series} range={range} />
          </ChartCard>
        </div>
      )}

      <section className="card">
        <div className="card-head">
          <h2>Recent checks</h2>
        </div>
        {history.loading && !history.data ? (
          <Spinner label="Loading history…" />
        ) : history.error && !history.data ? (
          <ErrorState message={history.error} onRetry={history.reload} />
        ) : history.data.count === 0 ? (
          <p className="muted pad">No checks yet. Use “Run check now” or wait for the next scheduled check.</p>
        ) : (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">Time</th>
                    <th scope="col">Result</th>
                    <th scope="col">HTTP</th>
                    <th scope="col">Response</th>
                    <th scope="col">Details</th>
                  </tr>
                </thead>
                <tbody>
                  {history.data.results.map((c) => (
                    <tr key={c.id}>
                      <td>
                        {formatDateTime(c.checked_at)} {c.is_manual && <span className="tag">manual</span>}
                      </td>
                      <td>
                        <StatusBadge status={c.status} />
                      </td>
                      <td>{c.status_code ?? '—'}</td>
                      <td>{formatMs(c.response_time_ms)}</td>
                      <td className="wrap">{c.error_message || '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={historyPage} count={history.data.count} pageSize={10} onChange={setHistoryPage} />
          </>
        )}
      </section>

      <section className="card">
        <div className="card-head">
          <h2>Incident history</h2>
        </div>
        {incidents.loading && !incidents.data ? (
          <Spinner label="Loading incidents…" />
        ) : incidents.error && !incidents.data ? (
          <ErrorState message={incidents.error} onRetry={incidents.reload} />
        ) : incidents.data.count === 0 ? (
          <p className="muted pad">No incidents for this API.</p>
        ) : (
          <IncidentTable incidents={incidents.data.results} showApi={false} />
        )}
      </section>

      {editing && (
        <Modal title={`Edit ${a.name}`} onClose={() => setEditing(false)}>
          <ApiForm initial={a} onSubmit={save} onCancel={() => setEditing(false)} submitting={saving} errors={formErrors} generalError={formGeneral} />
        </Modal>
      )}
    </>
  );
}
