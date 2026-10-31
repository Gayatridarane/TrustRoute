import { useEffect, useRef } from 'react';
import { AlertCircle, ChevronLeft, ChevronRight, Inbox, Loader2 } from 'lucide-react';

export function Spinner({ label = 'Loading…' }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <Loader2 className="spin" size={22} aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="state state-error" role="alert">
      <AlertCircle size={22} aria-hidden="true" />
      <p>{message || 'Something went wrong.'}</p>
      {onRetry && (
        <button type="button" className="btn btn-secondary" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, description, action }) {
  return (
    <div className="state">
      <Inbox size={28} aria-hidden="true" />
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {action}
    </div>
  );
}

const STATUS = {
  healthy: { label: 'Healthy', cls: 'ok' },
  slow: { label: 'Slow', cls: 'warn' },
  failed: { label: 'Failed', cls: 'bad' },
  unknown: { label: 'Pending', cls: 'idle' },
  paused: { label: 'Paused', cls: 'idle' },
  open: { label: 'Open', cls: 'bad' },
  resolved: { label: 'Resolved', cls: 'ok' },
};

export function StatusBadge({ status }) {
  const s = STATUS[status] || STATUS.unknown;
  return (
    <span className={`badge badge-${s.cls}`}>
      <span className="dot" aria-hidden="true" />
      {s.label}
    </span>
  );
}

export function StatCard({ label, value, hint, tone, icon: Icon }) {
  return (
    <div className={`card stat ${tone ? `stat-${tone}` : ''}`}>
      <div className="stat-top">
        <span className="stat-label">{label}</span>
        {Icon && <Icon size={18} aria-hidden="true" />}
      </div>
      <div className="stat-value">{value}</div>
      {hint && <div className="stat-hint">{hint}</div>}
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="page-header">
      <div>
        <h1>{title}</h1>
        {subtitle && <p className="muted">{subtitle}</p>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </div>
  );
}

export function Pagination({ page, count, pageSize, onChange }) {
  const pages = Math.max(1, Math.ceil(count / pageSize));
  if (count === 0) return null;
  const from = (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, count);
  return (
    <nav className="pagination" aria-label="Pagination">
      <span className="muted">
        Showing {from}–{to} of {count}
      </span>
      <div>
        <button type="button" className="btn btn-secondary btn-sm" disabled={page <= 1} onClick={() => onChange(page - 1)} aria-label="Previous page">
          <ChevronLeft size={16} aria-hidden="true" />
        </button>
        <span className="page-num">
          {page} / {pages}
        </span>
        <button type="button" className="btn btn-secondary btn-sm" disabled={page >= pages} onClick={() => onChange(page + 1)} aria-label="Next page">
          <ChevronRight size={16} aria-hidden="true" />
        </button>
      </div>
    </nav>
  );
}

export function Modal({ title, onClose, children, size = 'md' }) {
  const ref = useRef(null);

  useEffect(() => {
    const previous = document.activeElement;
    const node = ref.current;
    const focusables = () =>
      node.querySelectorAll('button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])');
    (focusables()[0] || node).focus();

    const onKey = (e) => {
      if (e.key === 'Escape') {
        e.stopPropagation();
        onClose();
      } else if (e.key === 'Tab') {
        const items = focusables();
        if (!items.length) return;
        const first = items[0];
        const last = items[items.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('keydown', onKey);
      previous?.focus?.();
    };
  }, [onClose]);

  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`modal modal-${size}`} role="dialog" aria-modal="true" aria-label={title} ref={ref} tabIndex={-1}>
        <div className="modal-head">
          <h2>{title}</h2>
          <button type="button" className="icon-btn" onClick={onClose} aria-label="Close dialog">
            ×
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function ConfirmDialog({ title, message, confirmLabel = 'Delete', busy, onConfirm, onCancel }) {
  return (
    <Modal title={title} onClose={onCancel} size="sm">
      <p>{message}</p>
      <div className="modal-actions">
        <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
        <button type="button" className="btn btn-danger" onClick={onConfirm} disabled={busy}>
          {busy ? 'Working…' : confirmLabel}
        </button>
      </div>
    </Modal>
  );
}

export function ChartCard({ title, subtitle, children, empty }) {
  return (
    <section className="card chart-card" aria-label={title}>
      <h3>{title}</h3>
      {subtitle && <p className="muted small">{subtitle}</p>}
      {empty ? <div className="chart-empty muted">{empty}</div> : <div className="chart-body">{children}</div>}
    </section>
  );
}

export function Notice({ notice, onDismiss }) {
  if (!notice) return null;
  return (
    <div className={`notice notice-${notice.type || 'info'}`} role="status">
      <span>{notice.text}</span>
      <button type="button" className="icon-btn" onClick={onDismiss} aria-label="Dismiss message">
        ×
      </button>
    </div>
  );
}
