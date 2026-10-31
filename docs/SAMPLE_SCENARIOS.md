# Example API configurations and test scenarios

Use these in the UI (**Monitored APIs → Add API**) or Postman. They use `httpbin.org`, a public
service built for testing HTTP clients. Intervals below are the minimum (30s) so you can see results quickly.

| Scenario | Name | URL | Expected status | Threshold | What you should see |
|---|---|---|---|---|---|
| Healthy | `Healthy 200` | `https://httpbin.org/status/200` | 200 | 1500 ms | Green, uptime stays 100% |
| Slow | `Slow 3s` | `https://httpbin.org/delay/3` | 200 | 1000 ms | Amber "Slow" + one slow alert; no incident |
| HTTP 500 | `Always 500` | `https://httpbin.org/status/500` | 200 | 1000 ms | Red; **one** incident opens, further failed checks add no duplicates |
| Expected non-200 | `Expects 404` | `https://httpbin.org/status/404` | 404 | 1000 ms | Green (404 is the expected answer) |
| DNS failure | `Bad DNS` | `https://this-host-does-not-exist-12345.example.com` | 200 | 1000 ms | Red, "DNS resolution failed" |
| Timeout | `Timeout` | `https://httpbin.org/delay/10` | 200 | 1000 ms | Set timeout to 3 s → Red, "Request timed out" |
| Redirect | `Redirect` | `https://httpbin.org/redirect/2` | 200 | 1500 ms | Green (redirects are followed and each hop is re-validated) |

## Verifying incident open → recover

1. Add `Flaky` pointing at `https://httpbin.org/status/500`. An incident opens and a failure alert appears (bell icon / Settings → Alerts).
2. Edit `Flaky`, set the URL to `https://httpbin.org/status/200`, and click **Run check now**.
3. The incident closes with a recovery time and duration, and a recovery alert is created.

## Verifying SSRF protection

Try to add any of these; each must be rejected with a validation error:

- `http://127.0.0.1:8000/admin/`
- `http://localhost/`
- `http://169.254.169.254/latest/meta-data/` (cloud metadata)
- `http://10.0.0.5/` or `http://192.168.1.1/`
- `ftp://example.com/file`

## Monitoring your own local server (demo only)

By default private addresses are blocked. To demo against a server on your own machine, set
`ALLOW_PRIVATE_URLS=True` in `backend/.env` and restart. **Never enable this on a shared or public deployment.**

## Google AI Studio (Gemini) with a header key

1. Add API: URL `https://generativelanguage.googleapis.com/v1beta/models`, method GET, expected status 200.
2. Headers box: `x-goog-api-key: YOUR_KEY` (stored encrypted; not shown again).
3. Run check now → green. A wrong key returns 400/403 → red + incident.
4. For a real prompt use POST to `.../models/<model>:generateContent` with a JSON body (see README).
