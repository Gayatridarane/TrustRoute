from datetime import timedelta
from unittest import mock

import requests
from django.test import TestCase
from django.utils import timezone

from monitor.models import Alert, CheckResult, Incident
from monitor.services import analytics
from monitor.services.checker import check_api
from monitor.services.ssrf import HostResolutionError

from .helpers import FakeResponse, make_api, make_user

SEND = "monitor.services.checker._send"
VALIDATE = "monitor.services.checker.validate_public_url"


class CheckerTests(TestCase):
    def setUp(self):
        self.user = make_user()
        self.api = make_api(self.user, response_threshold_ms=500)
        patcher = mock.patch(VALIDATE)
        patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def fake_clock(elapsed_seconds):
        """Replace the checker's `time` module so one request appears to take `elapsed_seconds`."""
        fake_time = mock.MagicMock()
        fake_time.perf_counter.side_effect = [0.0, elapsed_seconds]
        return mock.patch("monitor.services.checker.time", fake_time)

    def run_check(self, response=None, side_effect=None):
        with mock.patch(SEND, return_value=response, side_effect=side_effect):
            return check_api(self.api)

    def test_healthy_endpoint(self):
        result = self.run_check(FakeResponse(200))
        self.assertEqual(result.status, CheckResult.Status.HEALTHY)
        self.assertEqual(result.status_code, 200)
        self.assertIsNotNone(result.response_time_ms)
        self.api.refresh_from_db()
        self.assertEqual(self.api.current_status, "healthy")
        self.assertEqual(CheckResult.objects.count(), 1)
        self.assertEqual(Incident.objects.count(), 0)

    def test_slow_endpoint_creates_slow_alert_once(self):
        with self.fake_clock(2.0):
            first = self.run_check(FakeResponse(200))
        self.assertEqual(first.status, CheckResult.Status.SLOW)
        self.assertGreaterEqual(first.response_time_ms, 2000)
        with self.fake_clock(2.0):
            self.run_check(FakeResponse(200))
        self.assertEqual(Alert.objects.filter(kind=Alert.Kind.SLOW).count(), 1)  # no alert spam
        self.assertEqual(Incident.objects.count(), 0)  # slow is not an outage

    def test_http_500_is_failed(self):
        result = self.run_check(FakeResponse(500))
        self.assertEqual(result.status, CheckResult.Status.FAILED)
        self.assertEqual(result.status_code, 500)
        self.assertIn("500", result.error_message)

    def test_connection_failure(self):
        result = self.run_check(side_effect=requests.exceptions.ConnectionError("Connection refused"))
        self.assertEqual(result.status, CheckResult.Status.FAILED)
        self.assertIsNone(result.status_code)
        self.assertIn("Connection failed", result.error_message)

    def test_timeout(self):
        result = self.run_check(side_effect=requests.exceptions.ReadTimeout())
        self.assertEqual(result.status, CheckResult.Status.FAILED)
        self.assertIn("timed out", result.error_message)

    def test_dns_failure_from_requests(self):
        err = requests.exceptions.ConnectionError("NameResolutionError: Failed to resolve 'nope.invalid'")
        result = self.run_check(side_effect=err)
        self.assertIn("DNS resolution failed", result.error_message)

    def test_dns_failure_from_validator(self):
        with mock.patch(VALIDATE, side_effect=HostResolutionError("x")):
            result = check_api(self.api)
        self.assertEqual(result.status, CheckResult.Status.FAILED)
        self.assertIn("DNS resolution failed", result.error_message)

    def test_redirect_to_private_address_is_blocked(self):
        from monitor.services.ssrf import UnsafeURLError

        def validate(url):
            if "169.254" in url:
                raise UnsafeURLError("private")

        redirect = FakeResponse(302, {"Location": "http://169.254.169.254/latest/meta-data"})
        with mock.patch(VALIDATE, side_effect=validate):
            result = self.run_check(redirect)
        self.assertEqual(result.status, CheckResult.Status.FAILED)
        self.assertIn("Blocked destination", result.error_message)

    def test_incident_created_once_then_recovered(self):
        self.run_check(FakeResponse(500))
        self.run_check(FakeResponse(503))
        self.run_check(FakeResponse(500))
        self.assertEqual(Incident.objects.count(), 1, "one outage must produce one incident")
        incident = Incident.objects.get()
        self.assertEqual(incident.status, Incident.Status.OPEN)
        self.assertIsNone(incident.resolved_at)

        self.run_check(FakeResponse(200))
        incident.refresh_from_db()
        self.assertEqual(incident.status, Incident.Status.RESOLVED)
        self.assertIsNotNone(incident.resolved_at)
        self.assertGreaterEqual(incident.duration_seconds, 0)
        kinds = list(Alert.objects.order_by("id").values_list("kind", flat=True))
        self.assertEqual(kinds, ["failure", "recovery"])

        self.run_check(FakeResponse(500))  # a new outage -> a new incident
        self.assertEqual(Incident.objects.count(), 2)

    def test_deleted_api_returns_none(self):
        api = self.api
        api.delete()
        with mock.patch(SEND, return_value=FakeResponse(200)):
            self.assertIsNone(check_api(api))


class UptimeTests(TestCase):
    def test_uptime_formula(self):
        user = make_user()
        api = make_api(user)
        now = timezone.now()
        for status in ["healthy", "healthy", "healthy", "slow", "failed"]:
            CheckResult.objects.create(api=api, status=status, checked_at=now - timedelta(minutes=5), response_time_ms=100)
        # (3 healthy + 1 slow) / 5 total = 80%
        self.assertEqual(analytics.uptime_percent(CheckResult.objects.filter(api=api)), 80.0)
        data = analytics.api_analytics(api, "24h")
        self.assertEqual(data["summary"]["total_checks"], 5)
        self.assertEqual(data["summary"]["failed_checks"], 1)
        self.assertEqual(data["summary"]["uptime_percent"], 80.0)
        self.assertEqual(sum(b["checks"] for b in data["series"]), 5)

    def test_uptime_is_none_without_checks(self):
        api = make_api(make_user())
        self.assertIsNone(analytics.uptime_percent(CheckResult.objects.filter(api=api)))
