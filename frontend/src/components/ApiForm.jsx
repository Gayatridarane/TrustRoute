import { useState } from 'react';

const DEFAULTS = {
  name: '',
  url: '',
  method: 'GET',
  expected_status: 200,
  interval_seconds: 60,
  response_threshold_ms: 1000,
  timeout_seconds: 10,
  is_active: true,
  headersText: '',
  removeHeaders: false,
  request_body: '',
};

/** Parse "Name: value" lines into an object. Returns { headers } or { error }. */
function parseHeaders(text) {
  const headers = {};
  for (const raw of text.split('\n')) {
    const line = raw.trim();
    if (!line) continue;
    const i = line.indexOf(':');
    if (i < 1 || !line.slice(i + 1).trim()) return { error: `Header line must look like "Name: value" — got "${line.slice(0, 40)}".` };
    headers[line.slice(0, i).trim()] = line.slice(i + 1).trim();
  }
  return { headers };
}

function Field({ id, label, hint, error, children }) {
  return (
    <div className={`field ${error ? 'field-error' : ''}`}>
      <label htmlFor={id}>{label}</label>
      {children}
      {hint && !error && <small className="muted">{hint}</small>}
      {error && (
        <small className="error-text" id={`${id}-error`} role="alert">
          {error}
        </small>
      )}
    </div>
  );
}

export default function ApiForm({ initial, onSubmit, onCancel, submitting, errors = {}, generalError }) {
  const [values, setValues] = useState({ ...DEFAULTS, ...(initial || {}) });
  const set = (name) => (e) => {
    const v = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
    setValues((prev) => ({ ...prev, [name]: v }));
  };
  const props = (name) => ({
    id: `f-${name}`,
    value: values[name],
    onChange: set(name),
    'aria-invalid': Boolean(errors[name]),
    'aria-describedby': errors[name] ? `f-${name}-error` : undefined,
  });

  const [localError, setLocalError] = useState('');
  const savedHeaderNames = initial?.header_names || [];

  const submit = (e) => {
    e.preventDefault();
    setLocalError('');
    const payload = {
      name: values.name.trim(),
      url: values.url.trim(),
      method: values.method,
      expected_status: Number(values.expected_status),
      interval_seconds: Number(values.interval_seconds),
      response_threshold_ms: Number(values.response_threshold_ms),
      timeout_seconds: Number(values.timeout_seconds),
      is_active: values.is_active,
      request_body: values.method === 'POST' ? values.request_body : '',
    };
    if (values.headersText.trim()) {
      const parsed = parseHeaders(values.headersText);
      if (parsed.error) {
        setLocalError(parsed.error);
        return;
      }
      payload.headers = parsed.headers; // replaces any saved headers
    } else if (values.removeHeaders) {
      payload.headers = {}; // removes saved headers
    } // otherwise omitted: saved headers are kept
    onSubmit(payload);
  };

  return (
    <form onSubmit={submit} noValidate>
      {generalError && (
        <div className="notice notice-error" role="alert">
          {generalError}
        </div>
      )}
      <Field id="f-name" label="Name" error={errors.name}>
        <input type="text" required maxLength={120} placeholder="Payments API" {...props('name')} />
      </Field>
      <Field id="f-url" label="URL" error={errors.url} hint="Public http(s) endpoints only. Localhost and private networks are blocked.">
        <input type="url" required placeholder="https://api.example.com/health" {...props('url')} />
      </Field>
      <div className="form-grid">
        <Field id="f-method" label="HTTP method" error={errors.method}>
          <select {...props('method')}>
            {['GET', 'HEAD', 'POST', 'OPTIONS'].map((m) => (
              <option key={m}>{m}</option>
            ))}
          </select>
        </Field>
        <Field id="f-expected_status" label="Expected status code" error={errors.expected_status}>
          <input type="number" min="100" max="599" {...props('expected_status')} />
        </Field>
        <Field id="f-interval_seconds" label="Check interval (seconds)" error={errors.interval_seconds}>
          <input type="number" min="30" max="86400" {...props('interval_seconds')} />
        </Field>
        <Field id="f-response_threshold_ms" label="Slow threshold (ms)" error={errors.response_threshold_ms}>
          <input type="number" min="1" max="60000" {...props('response_threshold_ms')} />
        </Field>
        <Field id="f-timeout_seconds" label="Request timeout (seconds)" error={errors.timeout_seconds} hint="Must be shorter than the interval.">
          <input type="number" min="1" max="30" {...props('timeout_seconds')} />
        </Field>
      </div>
      <Field
        id="f-headersText"
        label="Request headers (optional)"
        error={localError || errors.headers}
        hint={
          savedHeaderNames.length
            ? `Saved headers: ${savedHeaderNames.join(', ')} (values hidden). Leave blank to keep them, or enter new lines to replace them.`
            : 'One per line as Name: value, e.g. x-goog-api-key: YOUR_KEY. Values are stored encrypted and never shown again.'
        }
      >
        <textarea
          id="f-headersText"
          rows={3}
          spellCheck={false}
          autoComplete="off"
          placeholder="x-goog-api-key: YOUR_KEY"
          value={values.headersText}
          onChange={set('headersText')}
          aria-invalid={Boolean(localError || errors.headers)}
        />
      </Field>
      {savedHeaderNames.length > 0 && !values.headersText.trim() && (
        <label className="check-row">
          <input type="checkbox" checked={values.removeHeaders} onChange={set('removeHeaders')} />
          Remove saved headers
        </label>
      )}
      {values.method === 'POST' && (
        <Field id="f-request_body" label="Request body (optional)" error={errors.request_body} hint="Sent as JSON unless you set a Content-Type header.">
          <textarea id="f-request_body" rows={4} spellCheck={false} placeholder='{"contents":[{"parts":[{"text":"ping"}]}]}' {...props('request_body')} />
        </Field>
      )}
      {errors.non_field_errors && <p className="error-text">{errors.non_field_errors}</p>}
      <label className="check-row">
        <input type="checkbox" checked={values.is_active} onChange={set('is_active')} />
        Enable monitoring
      </label>
      <div className="modal-actions">
        <button type="button" className="btn btn-secondary" onClick={onCancel} disabled={submitting}>
          Cancel
        </button>
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? 'Saving…' : initial?.id ? 'Save changes' : 'Add API'}
        </button>
      </div>
    </form>
  );
}
