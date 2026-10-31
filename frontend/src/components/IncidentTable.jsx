import { Link } from 'react-router-dom';
import { StatusBadge } from './ui.jsx';
import { formatDateTime, formatDuration } from '../utils/format.js';

export default function IncidentTable({ incidents, showApi = true }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            {showApi && <th scope="col">API</th>}
            <th scope="col">Failed at</th>
            <th scope="col">Recovered at</th>
            <th scope="col">Duration</th>
            <th scope="col">Error details</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {incidents.map((i) => (
            <tr key={i.id}>
              {showApi && (
                <td>
                  <Link to={`/apis/${i.api_id}`}>{i.api_name}</Link>
                </td>
              )}
              <td>{formatDateTime(i.started_at)}</td>
              <td>{i.resolved_at ? formatDateTime(i.resolved_at) : '—'}</td>
              <td>{formatDuration(i.duration_seconds)}{i.status === 'open' ? ' (ongoing)' : ''}</td>
              <td className="wrap">
                {i.status_code ? <code>HTTP {i.status_code}</code> : null} {i.reason}
              </td>
              <td>
                <StatusBadge status={i.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
