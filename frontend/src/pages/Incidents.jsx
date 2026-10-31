import { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { api } from '../api/client.js';
import useAsync from '../hooks/useAsync.js';
import useDebounce from '../hooks/useDebounce.js';
import IncidentTable from '../components/IncidentTable.jsx';
import { EmptyState, ErrorState, PageHeader, Pagination, Spinner } from '../components/ui.jsx';

const PAGE_SIZE = 15;

export default function Incidents() {
  const [search, setSearch] = useState('');
  const [apiId, setApiId] = useState('');
  const [status, setStatus] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [page, setPage] = useState(1);
  const debounced = useDebounce(search);

  useEffect(() => setPage(1), [debounced, apiId, status, dateFrom, dateTo]);

  const apis = useAsync(() => api.listApis({ page_size: 100 }), []);
  const { data, loading, error, reload } = useAsync(
    () =>
      api.incidents({
        search: debounced || undefined,
        api: apiId || undefined,
        status: status || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        page,
        page_size: PAGE_SIZE,
      }),
    [debounced, apiId, status, dateFrom, dateTo, page],
    { refreshMs: 30000 }
  );

  const filtering = Boolean(debounced || apiId || status || dateFrom || dateTo);
  const clear = () => {
    setSearch('');
    setApiId('');
    setStatus('');
    setDateFrom('');
    setDateTo('');
  };

  return (
    <>
      <PageHeader title="Incidents" subtitle="Outages detected automatically when an API moves to a failed state." />
      <div className="toolbar toolbar-wrap">
        <div className="search">
          <Search size={16} aria-hidden="true" />
          <input type="search" placeholder="Search API or error" aria-label="Search incidents" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <select aria-label="Filter by API" value={apiId} onChange={(e) => setApiId(e.target.value)}>
          <option value="">All APIs</option>
          {(apis.data?.results || []).map((a) => (
            <option key={a.id} value={a.id}>
              {a.name}
            </option>
          ))}
        </select>
        <select aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="open">Open</option>
          <option value="resolved">Resolved</option>
        </select>
        <label className="inline-field">
          From
          <input type="date" value={dateFrom} max={dateTo || undefined} onChange={(e) => setDateFrom(e.target.value)} />
        </label>
        <label className="inline-field">
          To
          <input type="date" value={dateTo} min={dateFrom || undefined} onChange={(e) => setDateTo(e.target.value)} />
        </label>
        {filtering && (
          <button type="button" className="btn btn-secondary btn-sm" onClick={clear}>
            Clear filters
          </button>
        )}
      </div>

      <section className="card">
        {loading && !data ? (
          <Spinner label="Loading incidents…" />
        ) : error && !data ? (
          <ErrorState message={error} onRetry={reload} />
        ) : data.count === 0 ? (
          <EmptyState
            title={filtering ? 'No incidents match your filters' : 'No incidents yet'}
            description={filtering ? 'Try widening the date range or clearing filters.' : 'When a monitored API fails, an incident will appear here and close automatically on recovery.'}
          />
        ) : (
          <>
            <IncidentTable incidents={data.results} />
            <Pagination page={page} count={data.count} pageSize={PAGE_SIZE} onChange={setPage} />
          </>
        )}
      </section>
    </>
  );
}
