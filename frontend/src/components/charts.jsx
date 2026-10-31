import { Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { tickLabel } from '../utils/format.js';

export const COLORS = { ok: '#16a34a', warn: '#d97706', bad: '#dc2626', idle: '#94a3b8', line: '#2563eb' };

const axis = { stroke: '#94a3b8', fontSize: 12 };

function Frame({ children, height = 260 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      {children}
    </ResponsiveContainer>
  );
}

const withLabels = (series, range) => series.map((p) => ({ ...p, label: tickLabel(p.bucket_start, range) }));

export function ResponseTimeChart({ series, range = '24h' }) {
  return (
    <Frame>
      <LineChart data={withLabels(series, range)} margin={{ top: 8, right: 12, bottom: 0, left: -8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="label" {...axis} minTickGap={24} />
        <YAxis {...axis} unit=" ms" width={64} />
        <Tooltip formatter={(v) => (v == null ? '—' : `${v} ms`)} />
        <Line type="monotone" dataKey="avg_response_ms" name="Avg response" stroke={COLORS.line} strokeWidth={2} dot={false} connectNulls />
      </LineChart>
    </Frame>
  );
}

export function SuccessFailChart({ series, range = '24h' }) {
  return (
    <Frame>
      <BarChart data={withLabels(series, range)} margin={{ top: 8, right: 12, bottom: 0, left: -16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="label" {...axis} minTickGap={24} />
        <YAxis {...axis} allowDecimals={false} />
        <Tooltip />
        <Legend />
        <Bar dataKey="success" name="Successful" stackId="c" fill={COLORS.ok} />
        <Bar dataKey="failed" name="Failed" stackId="c" fill={COLORS.bad} />
      </BarChart>
    </Frame>
  );
}

export function UptimeChart({ series, range = '24h' }) {
  return (
    <Frame>
      <LineChart data={withLabels(series, range)} margin={{ top: 8, right: 12, bottom: 0, left: -8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="label" {...axis} minTickGap={24} />
        <YAxis {...axis} domain={[0, 100]} unit="%" width={48} />
        <Tooltip formatter={(v) => (v == null ? '—' : `${v}%`)} />
        <Line type="monotone" dataKey="uptime_percent" name="Uptime" stroke={COLORS.ok} strokeWidth={2} dot={false} connectNulls />
      </LineChart>
    </Frame>
  );
}

export function IncidentFrequencyChart({ series, range = '24h' }) {
  return (
    <Frame>
      <BarChart data={withLabels(series, range)} margin={{ top: 8, right: 12, bottom: 0, left: -16 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
        <XAxis dataKey="label" {...axis} minTickGap={24} />
        <YAxis {...axis} allowDecimals={false} />
        <Tooltip />
        <Bar dataKey="incidents" name="Incidents" fill={COLORS.bad} />
      </BarChart>
    </Frame>
  );
}

const PIE_COLORS = { healthy: COLORS.ok, slow: COLORS.warn, failed: COLORS.bad, unknown: COLORS.idle };
const PIE_LABELS = { healthy: 'Healthy', slow: 'Slow', failed: 'Failed', unknown: 'Pending' };

export function StatusPie({ distribution }) {
  const data = distribution.filter((d) => d.count > 0).map((d) => ({ ...d, name: PIE_LABELS[d.status] }));
  return (
    <Frame>
      <PieChart>
        <Pie data={data} dataKey="count" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>
          {data.map((d) => (
            <Cell key={d.status} fill={PIE_COLORS[d.status]} />
          ))}
        </Pie>
        <Tooltip />
        <Legend />
      </PieChart>
    </Frame>
  );
}
