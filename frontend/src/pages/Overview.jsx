import { Link } from 'react-router-dom';
import { Activity, CheckCircle2, Clock, Gauge, Plus, Server, TrendingUp, XCircle } from 'lucide-react';
import { api } from '../api/client.js';
import useAsync from '../hooks/useAsync.js';
import { ChartCard, EmptyState, ErrorState, PageHeader, Spinner, StatCard } from '../components/ui.jsx';
import { ResponseTimeChart, StatusPie } from '../components/charts.jsx';
import IncidentTable from '../components/IncidentTable.jsx';
import { formatMs, formatPercent } from '../utils/format.js';

export default function Overview() {
  const { data, loading, error, reload } = useAsync(() => api.dashboard(), [], { refreshMs: 30000 });

  const header = <PageHeader title="Overview" subtitle="Live reliability summary across all of your monitored APIs." />;

  if (loading && !data) {
    return (
      <>
        {header}
        <Spinner label="Loading dashboard…" />
      </>
    );
  }
  if (error && !data) {
    return (
      <>
        {header}
        <ErrorState message={error} onRetry={reload} />
      </>
    );
  }
  if (data.total_apis === 0) {
    return (
      <>
        {header}
        <EmptyState
          title="No APIs yet"
          description="Add your first API and TrustRoute will start checking it automatically, tracking response times and detecting outages."
          action={
            <Link to="/apis?new=1" className="btn btn-primary">
              <Plus size={16} aria-hidden="true" /> Add your first API
            </Link>
          }
        />
      </>
    );
  }

  const hasTrend = data.response_trend.some((p) => p.avg_response_ms !== null);
  const hasStatus = data.status_distribution.some((d) => d.count > 0);

  return (
    <>
      {header}
      <div className="stats-grid">
        <StatCard label="Total APIs" value={data.total_apis} hint={`${data.active_apis} actively monitored`} icon={Server} />
        <StatCard label="Healthy" value={data.healthy_apis} tone="ok" icon={CheckCircle2} />
        <StatCard label="Slow" value={data.slow_apis} tone="warn" icon={Clock} />
        <StatCard label="Failed" value={data.failed_apis} tone="bad" icon={XCircle} hint={`${data.open_incidents} open incident${data.open_incidents === 1 ? '' : 's'}`} />
        <StatCard label="Avg response (24h)" value={formatMs(data.avg_response_ms)} icon={Gauge} />
        <StatCard label="Uptime (24h)" value={formatPercent(data.uptime_24h)} hint={`${data.checks_24h} checks`} icon={TrendingUp} />
      </div>

      <div className="grid-2">
        <ChartCard title="Response time trend" subtitle="Average per hour, last 24 hours" empty={hasTrend ? null : 'No response-time data yet. Checks will appear here shortly.'}>
          <ResponseTimeChart series={data.response_trend} />
        </ChartCard>
        <ChartCard title="API status distribution" subtitle="Current state of each API" empty={hasStatus ? null : 'No status data yet.'}>
          <StatusPie distribution={data.status_distribution} />
        </ChartCard>
      </div>

      <section className="card">
        <div className="card-head">
          <h2>
            <Activity size={18} aria-hidden="true" /> Recent incidents
          </h2>
          <Link to="/incidents">View all</Link>
        </div>
        {data.recent_incidents.length === 0 ? (
          <p className="muted pad">No incidents recorded. Everything looks quiet.</p>
        ) : (
          <IncidentTable incidents={data.recent_incidents} />
        )}
      </section>
    </>
  );
}
