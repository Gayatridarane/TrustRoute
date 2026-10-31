import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { Pencil, Play, Plus, Search, Trash2 } from 'lucide-react';
import { api, errorMessage, fieldErrors } from '../api/client.js';
import useAsync from '../hooks/useAsync.js';
import useDebounce from '../hooks/useDebounce.js';
import ApiForm from '../components/ApiForm.jsx';
import { ConfirmDialog, EmptyState, ErrorState, Modal, Notice, PageHeader, Pagination, Spinner, StatusBadge } from '../components/ui.jsx';
import { formatMs, timeAgo } from '../utils/format.js';

const PAGE_SIZE = 10;

export default function Apis() {
  const [params, setParams] = useSearchParams();
  const [search, setSearch] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const debounced = useDebounce(search);
  const [editing, setEditing] = useState(params.get('new') ? 'new' : null);
  const [deleting, setDeleting] = useState(null);
  const [saving, setSaving] = useState(false);
  const [formErrors, setFormErrors] = useState({});
  const [formGeneral, setFormGeneral] = useState('');
  const [busyId, setBusyId] = useState(null);
  const [notice, setNotice] = useState(null);

  useEffect(() => setPage(1), [debounced, status]);

  const { data, loading, error, reload, refresh } = useAsync(
    () => api.listApis({ search: debounced || undefined, current_status: status || undefined, page, page_size: PAGE_SIZE }),
    [debounced, status, page],
    { refreshMs: 30000 }
  );

  const closeForm = () => {
    setEditing(null);
    setFormErrors({});
    setFormGeneral('');
    if (params.get('new')) setParams({}, { replace: true });
  };

  const save = async (values) => {
    setSaving(true);
    setFormErrors({});
    setFormGeneral('');
    try {
      if (editing === 'new') {
        const created = await api.createApi(values);
        setNotice({ type: 'success', text: `“${created.name}” added. The first check runs within a few seconds.` });
      } else {
        await api.updateApi(editing.id, values);
        setNotice({ type: 'success', text: 'Changes saved.' });
      }
      closeForm();
      reload();
    } catch (err) {
      const fields = fieldErrors(err);
      setFormErrors(fields);
      setFormGeneral(Object.keys(fields).length ? '' : errorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  const toggle = async (item) => {
    setBusyId(item.id);
    try {
      await api.updateApi(item.id, { is_active: !item.is_active });
      setNotice({ type: 'success', text: `Monitoring ${item.is_active ? 'paused' : 'enabled'} for “${item.name}”.` });
      refresh();
    } catch (err) {
      setNotice({ type: 'error', text: errorMessage(err) });
    } finally {
      setBusyId(null);
    }
  };

  const runCheck = async (item) => {
    setBusyId(item.id);
    try {
      const r = await api.checkApi(item.id);
      const detail = r.status === 'healthy' ? `healthy in ${formatMs(r.response_time_ms)}` : r.error_message || r.status;
      setNotice({ type: r.status === 'failed' ? 'error' : r.status === 'slow' ? 'warn' : 'success', text: `${item.name}: ${detail}` });
      refresh();
    } catch (err) {
      setNotice({ type: 'error', text: errorMessage(err) });
    } finally {
      setBusyId(null);
    }
  };

  const confirmDelete = async () => {
    setBusyId(deleting.id);
    try {
      await api.deleteApi(deleting.id);
      setNotice({ type: 'success', text: `“${deleting.name}” deleted.` });
      setDeleting(null);
      if (data.results.length === 1 && page > 1) setPage(page - 1);
      else reload();
    } catch (err) {
      setNotice({ type: 'error', text: errorMessage(err) });
      setDeleting(null);
    } finally {
      setBusyId(null);
    }
  };

  const filtering = Boolean(debounced || status);

  return (
    <>
      <PageHeader
        title="Monitored APIs"
        subtitle="Endpoints TrustRoute checks on a schedule."
        actions={
          <button type="button" className="btn btn-primary" onClick={() => setEditing('new')}>
            <Plus size={16} aria-hidden="true" /> Add API
          </button>
        }
      />
      <Notice notice={notice} onDismiss={() => setNotice(null)} />

      <div className="toolbar">
        <div className="search">
          <Search size={16} aria-hidden="true" />
          <input type="search" placeholder="Search by name or URL" aria-label="Search APIs" value={search} onChange={(e) => setSearch(e.target.value)} />
        </div>
        <select aria-label="Filter by status" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="healthy">Healthy</option>
          <option value="slow">Slow</option>
          <option value="failed">Failed</option>
          <option value="unknown">Pending</option>
        </select>
      </div>

      <section className="card">
        {loading && !data ? (
          <Spinner label="Loading APIs…" />
        ) : error && !data ? (
          <ErrorState message={error} onRetry={reload} />
        ) : data.count === 0 ? (
          filtering ? (
            <EmptyState title="No APIs match your filters" description="Try a different search or status." />
          ) : (
            <EmptyState
              title="No APIs yet"
              description="Add an endpoint to start monitoring its availability and response time."
              action={
                <button type="button" className="btn btn-primary" onClick={() => setEditing('new')}>
                  <Plus size={16} aria-hidden="true" /> Add your first API
                </button>
              }
            />
          )
        ) : (
          <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">API</th>
                    <th scope="col">Status</th>
                    <th scope="col">Last response</th>
                    <th scope="col">Last checked</th>
                    <th scope="col">Monitoring</th>
                    <th scope="col">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {data.results.map((item) => (
                    <tr key={item.id}>
                      <td>
                        <Link to={`/apis/${item.id}`} className="strong">
                          {item.name}
                        </Link>
                        <div className="url">
                          <code>{item.method}</code> {item.url}
                        </div>
                      </td>
                      <td>
                        <StatusBadge status={item.is_active ? item.current_status : 'paused'} />
                      </td>
                      <td>{formatMs(item.last_response_time_ms)}</td>
                      <td>{timeAgo(item.last_checked_at)}</td>
                      <td>
                        <button
                          type="button"
                          role="switch"
                          aria-checked={item.is_active}
                          aria-label={`Monitoring for ${item.name}`}
                          className={`switch ${item.is_active ? 'on' : ''}`}
                          disabled={busyId === item.id}
                          onClick={() => toggle(item)}
                        >
                          <span />
                        </button>
                      </td>
                      <td className="actions">
                        <button type="button" className="icon-btn" title="Run check now" aria-label={`Run check now for ${item.name}`} disabled={busyId === item.id} onClick={() => runCheck(item)}>
                          <Play size={16} aria-hidden="true" />
                        </button>
                        <button type="button" className="icon-btn" title="Edit" aria-label={`Edit ${item.name}`} onClick={() => setEditing(item)}>
                          <Pencil size={16} aria-hidden="true" />
                        </button>
                        <button type="button" className="icon-btn danger" title="Delete" aria-label={`Delete ${item.name}`} onClick={() => setDeleting(item)}>
                          <Trash2 size={16} aria-hidden="true" />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={page} count={data.count} pageSize={PAGE_SIZE} onChange={setPage} />
          </>
        )}
      </section>

      {editing && (
        <Modal title={editing === 'new' ? 'Add API' : `Edit ${editing.name}`} onClose={closeForm}>
          <ApiForm initial={editing === 'new' ? null : editing} onSubmit={save} onCancel={closeForm} submitting={saving} errors={formErrors} generalError={formGeneral} />
        </Modal>
      )}
      {deleting && (
        <ConfirmDialog
          title="Delete API?"
          message={`“${deleting.name}” and all of its check history and incidents will be permanently deleted. This cannot be undone.`}
          busy={busyId === deleting.id}
          onConfirm={confirmDelete}
          onCancel={() => setDeleting(null)}
        />
      )}
    </>
  );
}
