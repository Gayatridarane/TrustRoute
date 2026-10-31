import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/client.js';
import useAsync from '../hooks/useAsync.js';
import { ChartCard, EmptyState, ErrorState, PageHeader, Spinner, StatCard } from '../components/ui.jsx';
import { IncidentFrequencyChart, ResponseTimeChart, SuccessFailChart, UptimeChart } from '../components/charts.jsx';
import { formatMs, formatPercent } from '../utils/format.js';

export default function Analytics() {
  const apis = useAsync(() => api.listApis({ page_size: 100 }), []);
  const [apiId, setApiId] = useState('');
  const [range, setRange] = useState('24h');

  const list = apis.data?.results || [];
  useEffect(() => {
    if (!apiId && list.length) setApiId(String(list[0].id));
  }, [list, apiId]);

  const stats = useAsync(() => (apiId ? api.apiAnalytics(apiId, range) : Promise.resolve(null)), [apiId, range], { refreshMs: 60000 });

  const header = <PageHeader title="Analytics" subtitle="Performance and reliability trends for a single API." />;

  if (apis.loading && !apis.data) {
    return (
      <>
        {header}
        <Spinner label="Loading…" />
      </>
    );
  }
  if (apis.error && !apis.data) {
    return (
      <>
        {header}
        <ErrorState message={apis.error} onRetry={apis.reload} />
      </>
    );
  }
  if (list.length === 0) {
    return (
      <>
        {header}
        <EmptyState
          title="Nothing to analyze yet"
          description="Add an API and let a few checks run, then charts will appear here."
          action={
            <Link to="/apis?new=1" className="btn btn-primary">
              Add an API
            </Link>
          }
        />
      </>
    );
  }

  const s = stats.data?.summary;
  const series = stats.data?.series || [];
  const hasData = s && s.total_checks > 0;
  const emptyMsg = stats.loading ? 'Loading chart…' : hasData ? null : 'No checks in this period yet.';

  return (
    <>
      {header}
      <div className="toolbar">
        <label className="inline-field">
          API
          <select value={apiId} onChange={(e) => setApiId(e.target.value)} aria-label="Select API">
            {list.map((a) => (
              <option key={a.id} value={a.id}>
                {a.name}
              </option>
            ))}
          </select>
        </label>
        <div className="range-toggle" role="group" aria-label="Time range">
          {['24h', '7d'].map((r) => (
            <button key={r} type="button" className={`btn btn-sm ${range === r ? 'btn-primary' : 'btn-secondary'}`} aria-pressed={range === r} onClick={() => setRange(r)}>
              {r === '24h' ? 'Last 24 hours' : 'Last 7 days'}
            </button>
          ))}
        </div>
      </div>

      {stats.error && !stats.data ? (
        <ErrorState message={stats.error} onRetry={stats.reload} />
      ) : (
        <>
          <div className="stats-grid">
            <StatCard label="Uptime" value={formatPercent(s?.uptime_percent)} hint="successful ÷ total checks" />
            <StatCard label="Total checks" value={s?.total_checks ?? '—'} hint={s ? `${s.failed_checks} failed` : undefined} />
            <StatCard label="Avg response" value={formatMs(s?.avg_response_ms)} />
            <StatCard label="Slowest" value={formatMs(s?.max_response_ms)} />
            <StatCard label="Incidents" value={s?.incident_count ?? '—'} />
          </div>
          <div className="grid-2">
            <ChartCard title="Response time over time" empty={emptyMsg}>
              <ResponseTimeChart series={series} range={range} />
            </ChartCard>
            <ChartCard title="Successful vs failed checks" empty={emptyMsg}>
              <SuccessFailChart series={series} range={range} />
            </ChartCard>
            <ChartCard title="Uptime percentage" subtitle="Successful ÷ total checks per interval" empty={emptyMsg}>
              <UptimeChart series={series} range={range} />
            </ChartCard>
            <ChartCard title="Incident frequency" empty={emptyMsg}>
              <IncidentFrequencyChart series={series} range={range} />
            </ChartCard>
          </div>
        </>
      )}
    </>
  );
}
