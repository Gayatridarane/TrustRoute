import axios from 'axios';

export const TOKEN_KEY = 'tr_token';

const client = axios.create({ baseURL: '/api', timeout: 30000 });

client.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY);
  if (token) config.headers.Authorization = `Token ${token}`;
  return config;
});

client.interceptors.response.use(
  (response) => response,
  (error) => {
    const url = error.config?.url || '';
    const isAuthCall = url.includes('/auth/login') || url.includes('/auth/register');
    if (error.response?.status === 401 && !isAuthCall) {
      localStorage.removeItem(TOKEN_KEY);
      if (!window.location.pathname.startsWith('/login')) window.location.assign('/login');
    }
    return Promise.reject(error);
  }
);

/** Turn any axios/DRF error into one human-readable sentence. Never exposes stack traces. */
export function errorMessage(error) {
  const data = error?.response?.data;
  if (data) {
    if (typeof data === 'string') return data.length < 300 && !data.includes('<') ? data : 'The server returned an error.';
    if (typeof data.detail === 'string') return data.detail;
    if (typeof data === 'object') {
      const parts = Object.entries(data).map(([field, msgs]) => {
        const text = Array.isArray(msgs) ? msgs.join(' ') : String(msgs);
        return field === 'non_field_errors' ? text : `${field}: ${text}`;
      });
      if (parts.length) return parts.join(' ');
    }
  }
  if (error?.response?.status === 429) return 'Too many requests. Please wait a moment and try again.';
  if (error?.code === 'ECONNABORTED') return 'The request timed out. Please try again.';
  if (error?.request) return 'Cannot reach the TrustRoute server. Is the backend running?';
  return 'Something went wrong. Please try again.';
}

/** Field-level errors from a DRF 400 response, as { field: "message" }. */
export function fieldErrors(error) {
  const data = error?.response?.data;
  if (!data || typeof data !== 'object' || error.response.status !== 400) return {};
  const out = {};
  Object.entries(data).forEach(([field, msgs]) => {
    out[field] = Array.isArray(msgs)
      ? msgs.join(' ')
      : msgs && typeof msgs === 'object'
        ? Object.values(msgs).flat().join(' ')
        : String(msgs);
  });
  return out;
}

const get = (url, params) => client.get(url, { params }).then((r) => r.data);
const post = (url, body) => client.post(url, body).then((r) => r.data);

export const api = {
  login: (body) => post('/auth/login/', body),
  register: (body) => post('/auth/register/', body),
  logout: () => client.post('/auth/logout/'),
  me: () => get('/auth/me/'),

  dashboard: () => get('/dashboard/summary/'),

  listApis: (params) => get('/monitored-apis/', params),
  getApi: (id) => get(`/monitored-apis/${id}/`),
  createApi: (body) => post('/monitored-apis/', body),
  updateApi: (id, body) => client.patch(`/monitored-apis/${id}/`, body).then((r) => r.data),
  deleteApi: (id) => client.delete(`/monitored-apis/${id}/`),
  checkApi: (id) => post(`/monitored-apis/${id}/check/`),
  apiHistory: (id, params) => get(`/monitored-apis/${id}/history/`, params),
  apiAnalytics: (id, range) => get(`/monitored-apis/${id}/analytics/`, { range }),

  incidents: (params) => get('/incidents/', params),
  alerts: (params) => get('/alerts/', params),
  markAlertRead: (id) => post(`/alerts/${id}/mark-read/`),
  markAllAlertsRead: () => post('/alerts/mark-all-read/'),
};

export default client;
